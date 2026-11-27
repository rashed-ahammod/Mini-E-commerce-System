"""Tests for the organization order API at /api/org/orders/.

The two claims worth reading first: an organization user sees *every*
customer's orders (the opposite of the customer endpoint), and a customer
cannot reach any of it.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import Role, profile_for
from catalog.models import Category, Product
from orders.models import Order, OrderStatus

User = get_user_model()

PASSWORD = "StrongPass!234"


class OrgOrderTestCase(APITestCase):
    """Two customers with orders, one organization user, one plain customer."""

    def setUp(self):
        self.staff = User.objects.create_user("sam", password=PASSWORD)
        profile = profile_for(self.staff)
        profile.role = Role.STAFF
        profile.save()
        self.staff_token = Token.objects.create(user=self.staff)

        self.cara = User.objects.create_user("cara", password=PASSWORD)
        self.cara_token = Token.objects.create(user=self.cara)
        self.dan = User.objects.create_user("dan", password=PASSWORD)

        self.category = Category.objects.create(name="Phones")
        self.product = Product.objects.create(
            name="Flagship Phone",
            price=Decimal("999.00"),
            stock=20,
            category=self.category,
        )
        self.other_product = Product.objects.create(
            name="Budget Phone",
            price=Decimal("199.00"),
            stock=50,
            category=self.category,
        )

        self.cara_order = self.place(self.cara, self.product, 2)
        self.dan_order = self.place(self.dan, self.other_product, 1)

    def place(self, user, product, quantity, order_status=OrderStatus.PENDING):
        order = Order.objects.create(
            user=user,
            product=product,
            quantity=quantity,
            unit_price=product.price,
            status=order_status,
        )
        product.stock -= quantity
        product.save(update_fields=["stock"])
        return order

    def as_staff(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.staff_token.key}")

    def as_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.cara_token.key}")

    def status_url(self, order):
        return reverse("org-order-status", args=[order.id])

    def cancel_url(self, order):
        return reverse("org-order-cancel", args=[order.id])


class AccessTests(OrgOrderTestCase):
    def test_anonymous_callers_get_401(self):
        response = self.client.get(reverse("org-order-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customers_get_403(self):
        """A valid token, but the wrong kind of account."""
        self.as_customer()

        for url in (
            reverse("org-order-list"),
            reverse("org-order-detail", args=[self.cara_order.id]),
            self.status_url(self.cara_order),
            self.cancel_url(self.cara_order),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn(
                    response.status_code,
                    (status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED),
                )

        # The write actions specifically must be refused, not just unlisted.
        response = self.client.post(
            self.cancel_url(self.cara_order), {"reason": "nope"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_organization_users_are_allowed_in(self):
        self.as_staff()

        response = self.client.get(reverse("org-order-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_superusers_are_allowed_in(self):
        root = User.objects.create_superuser("root", password=PASSWORD)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=root).key}"
        )

        response = self.client.get(reverse("org-order-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ListTests(OrgOrderTestCase):
    def test_every_customers_orders_are_listed(self):
        """The opposite of the customer endpoint, which shows only your own."""
        self.as_staff()

        response = self.client.get(reverse("org-order-list"))

        self.assertEqual(response.data["count"], 2)
        usernames = {row["customer"]["username"] for row in response.data["results"]}
        self.assertEqual(usernames, {"cara", "dan"})

    def test_each_row_identifies_the_customer(self):
        self.as_staff()

        response = self.client.get(reverse("org-order-list"))
        row = response.data["results"][0]

        self.assertIn("customer", row)
        self.assertIn("username", row["customer"])
        self.assertIn("status", row)

    def test_filter_by_status(self):
        self.place(self.cara, self.product, 1, OrderStatus.SHIPPED)
        self.as_staff()

        response = self.client.get(reverse("org-order-list"), {"status": "shipped"})

        self.assertEqual(response.data["count"], 1)

    def test_filter_by_several_statuses(self):
        self.place(self.cara, self.product, 1, OrderStatus.SHIPPED)
        self.as_staff()

        response = self.client.get(
            reverse("org-order-list"), {"status__in": "pending,shipped"}
        )

        self.assertEqual(response.data["count"], 3)

    def test_filter_open_orders(self):
        self.place(self.cara, self.product, 1, OrderStatus.DELIVERED)
        self.as_staff()

        open_orders = self.client.get(reverse("org-order-list"), {"open": "true"})
        finished = self.client.get(reverse("org-order-list"), {"open": "false"})

        self.assertEqual(open_orders.data["count"], 2)
        self.assertEqual(finished.data["count"], 1)

    def test_filter_by_customer(self):
        self.as_staff()

        by_id = self.client.get(reverse("org-order-list"), {"customer": self.cara.id})
        by_name = self.client.get(
            reverse("org-order-list"), {"customer_username": "DAN"}
        )

        self.assertEqual(by_id.data["count"], 1)
        self.assertEqual(by_name.data["count"], 1)
        self.assertEqual(by_name.data["results"][0]["customer"]["username"], "dan")

    def test_filter_by_order_total(self):
        self.as_staff()

        response = self.client.get(reverse("org-order-list"), {"min_total": "500"})

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["total_price"], "1998.00")

    def test_search_by_customer_or_product(self):
        self.as_staff()

        by_product = self.client.get(reverse("org-order-list"), {"search": "Budget"})
        by_customer = self.client.get(reverse("org-order-list"), {"search": "cara"})

        self.assertEqual(by_product.data["count"], 1)
        self.assertEqual(by_customer.data["count"], 1)

    def test_ordering_by_total(self):
        self.as_staff()

        response = self.client.get(
            reverse("org-order-list"), {"ordering": "total_price"}
        )

        totals = [row["total_price"] for row in response.data["results"]]
        self.assertEqual(totals, sorted(totals, key=Decimal))


class DetailTests(OrgOrderTestCase):
    def test_detail_includes_history_and_next_statuses(self):
        self.cara_order.transition_to(
            OrderStatus.CONFIRMED, changed_by=self.staff, note="paid"
        )
        self.as_staff()

        response = self.client.get(
            reverse("org-order-detail", args=[self.cara_order.id])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["events"]), 1)
        self.assertEqual(response.data["events"][0]["note"], "paid")
        self.assertEqual(response.data["events"][0]["changed_by"], "sam")
        self.assertIn("processing", response.data["next_statuses"])
        self.assertTrue(response.data["is_open"])


class StatusActionTests(OrgOrderTestCase):
    def test_advancing_the_status(self):
        self.as_staff()

        response = self.client.post(
            self.status_url(self.cara_order),
            {"status": "confirmed", "note": "payment cleared"},
            format="json",
        )

        self.cara_order.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.cara_order.status, OrderStatus.CONFIRMED)
        self.assertEqual(response.data["status"], "confirmed")

    def test_the_response_carries_the_whole_order(self):
        """So a client can re-render without a second request."""
        self.as_staff()

        response = self.client.post(
            self.status_url(self.cara_order), {"status": "confirmed"}, format="json"
        )

        self.assertIn("events", response.data)
        self.assertIn("next_statuses", response.data)
        self.assertEqual(response.data["customer"]["username"], "cara")

    def test_an_invalid_jump_is_refused_with_an_explanation(self):
        self.as_staff()

        response = self.client.post(
            self.status_url(self.cara_order), {"status": "delivered"}, format="json"
        )

        self.cara_order.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirmed", str(response.data["status"]))
        self.assertEqual(self.cara_order.status, OrderStatus.PENDING)

    def test_an_unknown_status_is_refused(self):
        self.as_staff()

        response = self.client.post(
            self.status_url(self.cara_order), {"status": "teleported"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancelling_through_the_status_action_is_redirected(self):
        """Cancelling needs a reason, so it has its own action."""
        self.as_staff()

        response = self.client.post(
            self.status_url(self.cara_order), {"status": "cancelled"}, format="json"
        )

        self.cara_order.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cancel action", str(response.data["status"]))
        self.assertEqual(self.cara_order.status, OrderStatus.PENDING)

    def test_the_workflow_can_be_read_from_the_api(self):
        self.as_staff()

        response = self.client.get(reverse("org-order-statuses"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        by_status = {row["status"]: row for row in response.data}
        self.assertEqual(
            sorted(by_status["pending"]["next_statuses"]), ["cancelled", "confirmed"]
        )
        self.assertEqual(by_status["delivered"]["next_statuses"], [])


class CancelActionTests(OrgOrderTestCase):
    def test_cancelling_returns_the_stock(self):
        self.product.refresh_from_db()
        stock_while_ordered = self.product.stock
        self.as_staff()

        response = self.client.post(
            self.cancel_url(self.cara_order),
            {"reason": "customer changed their mind"},
            format="json",
        )

        self.product.refresh_from_db()
        self.cara_order.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.product.stock, stock_while_ordered + 2)
        self.assertEqual(self.cara_order.status, OrderStatus.CANCELLED)
        self.assertEqual(
            self.cara_order.cancellation_reason, "customer changed their mind"
        )

    def test_a_reason_is_required(self):
        self.as_staff()

        response = self.client.post(self.cancel_url(self.cara_order), {}, format="json")

        self.cara_order.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", response.data)
        self.assertEqual(self.cara_order.status, OrderStatus.PENDING)

    def test_a_shipped_order_cannot_be_cancelled(self):
        shipped = self.place(self.cara, self.product, 2, OrderStatus.SHIPPED)
        self.product.refresh_from_db()
        stock_before = self.product.stock
        self.as_staff()

        response = self.client.post(
            self.cancel_url(shipped), {"reason": "too late"}, format="json"
        )

        self.product.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.product.stock, stock_before)

    def test_cancelling_twice_is_refused_and_stock_stays_correct(self):
        self.as_staff()
        self.client.post(
            self.cancel_url(self.cara_order), {"reason": "first"}, format="json"
        )
        self.product.refresh_from_db()
        stock_after_first = self.product.stock

        response = self.client.post(
            self.cancel_url(self.cara_order), {"reason": "second"}, format="json"
        )

        self.product.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.product.stock, stock_after_first)

    def test_the_cancellation_is_attributed_to_the_staff_member(self):
        self.as_staff()

        response = self.client.post(
            self.cancel_url(self.cara_order), {"reason": "fraud check"}, format="json"
        )

        last_event = response.data["events"][-1]
        self.assertEqual(last_event["changed_by"], "sam")
        self.assertEqual(last_event["to_status"], "cancelled")
        self.assertEqual(last_event["note"], "fraud check")


class CustomerVisibilityTests(OrgOrderTestCase):
    def test_a_customer_sees_the_status_of_their_own_order(self):
        self.cara_order.transition_to(OrderStatus.CONFIRMED, changed_by=self.staff)
        self.as_customer()

        response = self.client.get(reverse("order-detail", args=[self.cara_order.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "confirmed")
        self.assertEqual(response.data["status_display"], "Confirmed")

    def test_a_customer_cannot_change_the_status_of_their_own_order(self):
        self.as_customer()

        response = self.client.patch(
            reverse("order-detail", args=[self.cara_order.id]),
            {"status": "delivered"},
            format="json",
        )

        self.cara_order.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.cara_order.status, OrderStatus.PENDING)


class OrgSeesDeliveryDetailsTests(OrgOrderTestCase):
    """Staff have to know where an order goes, and how to reach the customer.

    The order's address is a snapshot taken when it was placed; the profile
    holds the customer's current one. Both are shown, because they answer
    different questions — "where was this sent" and "how do I reach them
    today" — and they can legitimately differ.
    """

    DELIVERED_TO = "House 12, Road 5, Dhanmondi, Dhaka 1205"
    MOVED_TO = "Plot 7, Sector 11, Uttara, Dhaka 1230"

    def setUp(self):
        super().setUp()
        self.cara_order.delivery_address = self.DELIVERED_TO
        self.cara_order.delivery_phone = "+880 1711 123456"
        self.cara_order.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.staff_token.key}")

    def test_the_order_list_carries_the_destination(self):
        """So a picking list does not need a request per row."""
        response = self.client.get(reverse("org-order-list"))

        rows = {row["id"]: row for row in response.data["results"]}
        self.assertEqual(
            rows[self.cara_order.id]["delivery_address"], self.DELIVERED_TO
        )
        self.assertEqual(
            rows[self.cara_order.id]["delivery_phone"], "+880 1711 123456"
        )

    def test_the_order_detail_carries_the_destination(self):
        response = self.client.get(
            reverse("org-order-detail", args=[self.cara_order.id])
        )

        self.assertEqual(response.data["delivery_address"], self.DELIVERED_TO)

    def test_the_customers_current_contact_details_come_too(self):
        profile = profile_for(self.cara)
        profile.phone = "+880 1999 888777"
        profile.address = self.MOVED_TO
        profile.save()

        response = self.client.get(
            reverse("org-order-detail", args=[self.cara_order.id])
        )

        # Where it went, and where they live now — both, and distinctly.
        self.assertEqual(response.data["delivery_address"], self.DELIVERED_TO)
        self.assertEqual(response.data["customer"]["address"], self.MOVED_TO)
        self.assertEqual(response.data["customer"]["phone"], "+880 1999 888777")

    def test_a_customer_still_cannot_read_any_of_it(self):
        """Delivery addresses are the last thing that should leak."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.cara_token.key}")

        listed = self.client.get(reverse("org-order-list"))
        detail = self.client.get(
            reverse("org-order-detail", args=[self.dan_order.id])
        )

        self.assertEqual(listed.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(detail.status_code, status.HTTP_403_FORBIDDEN)

    def test_the_list_does_not_cost_a_query_per_customer(self):
        """The customer's profile is joined, not fetched row by row.

        This asserts the query count is *the same* for a short page and a
        longer one, rather than pinning an exact number: the exact figure is
        an implementation detail a new prefetch could legitimately change,
        while "it does not grow with the number of orders" is the property
        worth defending. Without select_related("user__profile") in the
        viewset, reading each customer's phone costs a query per row and
        these two figures diverge.
        """

        def query_count(expected_rows):
            with CaptureQueriesContext(connection) as captured:
                response = self.client.get(
                    reverse("org-order-list"), {"page_size": 50}
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(len(response.data["results"]), expected_rows)
            return len(captured)

        short_page = query_count(2)

        for index in range(8):
            buyer = User.objects.create_user(f"buyer{index}", password=PASSWORD)
            self.place(buyer, self.product, 1)

        long_page = query_count(10)

        self.assertEqual(
            short_page,
            long_page,
            f"{short_page} queries for 2 orders but {long_page} for 10: "
            "something is being fetched once per row.",
        )


class QueueOffersTheRightActionsTests(OrgOrderTestCase):
    """The order list carries each order's allowed transitions.

    Staff move orders along from the queue, so the rows need to know what
    the server will accept. The point of sending it rather than hard-coding
    it in the frontend is that the two can never disagree: these tests pin
    the list's answer to the model's own rules.
    """

    def setUp(self):
        super().setUp()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.staff_token.key}")

    def rows(self):
        response = self.client.get(reverse("org-order-list"), {"page_size": 50})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {row["id"]: row for row in response.data["results"]}

    def test_a_pending_order_offers_confirm_and_cancel(self):
        row = self.rows()[self.cara_order.id]

        self.assertEqual(sorted(row["next_statuses"]), ["cancelled", "confirmed"])
        self.assertTrue(row["is_open"])

    def test_the_list_matches_the_model_for_every_status(self):
        """Whatever the rules say, the queue says the same."""
        for order_status in OrderStatus:
            with self.subTest(status=order_status):
                order = self.place(self.cara, self.product, 1)
                Order.objects.filter(pk=order.pk).update(status=order_status)
                order.refresh_from_db()

                row = self.rows()[order.id]

                self.assertEqual(row["next_statuses"], order.next_statuses)
                self.assertEqual(row["is_open"], order.is_open)

    def test_a_finished_order_offers_nothing(self):
        order = self.place(self.cara, self.product, 1)
        Order.objects.filter(pk=order.pk).update(status=OrderStatus.DELIVERED)

        row = self.rows()[order.id]

        self.assertEqual(row["next_statuses"], [])
        self.assertFalse(row["is_open"])

    def test_acting_on_a_row_uses_the_same_rules_as_the_detail_page(self):
        """An action offered by the queue is one the server accepts."""
        row = self.rows()[self.cara_order.id]
        offered = [s for s in row["next_statuses"] if s != "cancelled"][0]

        response = self.client.post(
            reverse("org-order-status", args=[self.cara_order.id]),
            {"status": offered},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], offered)

    def test_a_customer_still_cannot_read_the_queue(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.cara_token.key}")

        response = self.client.get(reverse("org-order-list"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
