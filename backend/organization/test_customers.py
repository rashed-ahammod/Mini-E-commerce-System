"""Tests for the organization customer API at /api/org/customers/.

Two claims matter most: the spend figures are arithmetically right (someone
will decide something from them), and the endpoint cannot be turned on
organization accounts — including the caller's own.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import Role, profile_for
from catalog.models import Category, Product
from orders.models import Order, OrderStatus

User = get_user_model()

PASSWORD = "StrongPass!234"


class CustomerApiTestCase(APITestCase):
    """Two customers with different spend, plus staff and an admin.

        cara  2 x 999.00 = 1998.00  delivered
              1 x 999.00 =  999.00  pending
              1 x 999.00 =  999.00  cancelled   <- not counted as spend
              => order_count 3, total_spent 2997.00

        dan   no orders  => order_count 0, total_spent 0.00
    """

    def setUp(self):
        self.staff = User.objects.create_user("sam", password=PASSWORD)
        profile = profile_for(self.staff)
        profile.role = Role.STAFF
        profile.save()
        self.staff_token = Token.objects.create(user=self.staff)

        self.cara = User.objects.create_user(
            "cara", email="cara@example.com", password=PASSWORD
        )
        self.cara_token = Token.objects.create(user=self.cara)
        self.dan = User.objects.create_user("dan", password=PASSWORD)

        self.category = Category.objects.create(name="Phones")
        self.product = Product.objects.create(
            name="Flagship Phone",
            price=Decimal("999.00"),
            stock=50,
            category=self.category,
        )

        self.order(self.cara, 2, OrderStatus.DELIVERED)
        self.order(self.cara, 1, OrderStatus.PENDING)
        self.order(self.cara, 1, OrderStatus.CANCELLED)

    def order(self, user, quantity, order_status):
        return Order.objects.create(
            user=user,
            product=self.product,
            quantity=quantity,
            unit_price=self.product.price,
            status=order_status,
        )

    def as_staff(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.staff_token.key}")

    def as_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.cara_token.key}")

    def detail_url(self, user):
        return reverse("org-customer-detail", args=[user.id])

    def deactivate_url(self, user):
        return reverse("org-customer-deactivate", args=[user.id])

    def activate_url(self, user):
        return reverse("org-customer-activate", args=[user.id])


class AccessTests(CustomerApiTestCase):
    def test_anonymous_gets_401(self):
        response = self.client.get(reverse("org-customer-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_customer_cannot_browse_other_customers(self):
        self.as_customer()

        response = self.client.get(reverse("org-customer-list"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_a_customer_cannot_deactivate_anyone(self):
        self.as_customer()

        response = self.client.post(
            self.deactivate_url(self.dan), {"reason": "mischief"}, format="json"
        )

        self.dan.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(self.dan.is_active)

    def test_organization_users_are_allowed_in(self):
        self.as_staff()

        response = self.client.get(reverse("org-customer-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ListTests(CustomerApiTestCase):
    def test_only_customers_are_listed(self):
        """Staff and superusers run the shop; they are not its clientele."""
        User.objects.create_superuser("root", password=PASSWORD)
        self.as_staff()

        response = self.client.get(reverse("org-customer-list"))

        usernames = {row["username"] for row in response.data["results"]}
        self.assertEqual(usernames, {"cara", "dan"})

    def test_order_count_and_spend(self):
        self.as_staff()

        response = self.client.get(reverse("org-customer-list"))
        rows = {row["username"]: row for row in response.data["results"]}

        self.assertEqual(rows["cara"]["order_count"], 3)
        # 1998.00 + 999.00; the cancelled 999.00 is not spend.
        self.assertEqual(rows["cara"]["total_spent"], "2997.00")

    def test_a_customer_with_no_orders_reports_zero_not_null(self):
        self.as_staff()

        response = self.client.get(reverse("org-customer-list"))
        rows = {row["username"]: row for row in response.data["results"]}

        self.assertEqual(rows["dan"]["order_count"], 0)
        self.assertEqual(rows["dan"]["total_spent"], "0.00")
        self.assertIsNone(rows["dan"]["last_order_at"])

    def test_the_list_never_exposes_a_password(self):
        self.as_staff()

        response = self.client.get(reverse("org-customer-list"))

        for row in response.data["results"]:
            self.assertNotIn("password", row)

    def test_search_by_username_or_email(self):
        self.as_staff()

        by_name = self.client.get(reverse("org-customer-list"), {"search": "cara"})
        by_email = self.client.get(
            reverse("org-customer-list"), {"search": "cara@example.com"}
        )

        self.assertEqual(by_name.data["count"], 1)
        self.assertEqual(by_email.data["count"], 1)

    def test_filter_by_whether_they_have_ordered(self):
        self.as_staff()

        buyers = self.client.get(reverse("org-customer-list"), {"has_orders": "true"})
        browsers = self.client.get(
            reverse("org-customer-list"), {"has_orders": "false"}
        )

        self.assertEqual([r["username"] for r in buyers.data["results"]], ["cara"])
        self.assertEqual([r["username"] for r in browsers.data["results"]], ["dan"])

    def test_filter_by_minimum_orders(self):
        self.as_staff()

        response = self.client.get(reverse("org-customer-list"), {"min_orders": 3})

        self.assertEqual(response.data["count"], 1)

    def test_filter_by_active_state(self):
        self.dan.is_active = False
        self.dan.save()
        self.as_staff()

        response = self.client.get(reverse("org-customer-list"), {"is_active": "false"})

        self.assertEqual([r["username"] for r in response.data["results"]], ["dan"])

    def test_order_by_spend(self):
        self.as_staff()

        response = self.client.get(
            reverse("org-customer-list"), {"ordering": "-total_spent"}
        )

        self.assertEqual(response.data["results"][0]["username"], "cara")

    def test_the_list_does_not_scale_with_the_number_of_customers(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.as_staff()
        with CaptureQueriesContext(connection) as baseline:
            self.client.get(reverse("org-customer-list"))

        for index in range(15):
            User.objects.create_user(f"extra{index}", password=PASSWORD)

        with CaptureQueriesContext(connection) as after:
            self.client.get(reverse("org-customer-list"))

        self.assertEqual(
            len(after.captured_queries), len(baseline.captured_queries)
        )


class DetailTests(CustomerApiTestCase):
    def test_detail_includes_recent_orders(self):
        self.as_staff()

        response = self.client.get(self.detail_url(self.cara))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["recent_orders"]), 3)
        self.assertEqual(response.data["order_count"], 3)
        self.assertEqual(response.data["total_spent"], "2997.00")

    def test_recent_orders_are_newest_first(self):
        self.as_staff()

        response = self.client.get(self.detail_url(self.cara))

        ids = [order["id"] for order in response.data["recent_orders"]]
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_an_organization_account_is_not_reachable_here(self):
        """Staff are not customers, so this endpoint cannot suspend one."""
        self.as_staff()

        response = self.client.get(self.detail_url(self.staff))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_the_caller_cannot_reach_their_own_account(self):
        self.as_staff()

        response = self.client.post(
            self.deactivate_url(self.staff), {"reason": "oops"}, format="json"
        )

        self.staff.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(self.staff.is_active)


class DeactivationTests(CustomerApiTestCase):
    def test_deactivating_blocks_sign_in(self):
        self.as_staff()

        response = self.client.post(
            self.deactivate_url(self.cara), {"reason": "fraudulent orders"}, format="json"
        )

        self.cara.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(self.cara.is_active)
        self.assertFalse(response.data["is_active"])

        self.client.credentials()
        login = self.client.post(
            reverse("login"),
            {"username": "cara", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_400_BAD_REQUEST)

    def test_an_existing_token_stops_working(self):
        """Deactivating has to end the session, not just future logins."""
        self.as_staff()
        self.client.post(
            self.deactivate_url(self.cara), {"reason": "fraud"}, format="json"
        )

        self.as_customer()
        response = self.client.get(reverse("me"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_reason_is_required(self):
        self.as_staff()

        response = self.client.post(self.deactivate_url(self.cara), {}, format="json")

        self.cara.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", response.data)
        self.assertTrue(self.cara.is_active)

    def test_their_orders_are_left_alone(self):
        """Suspending an account must not erase the sales history."""
        self.as_staff()

        self.client.post(
            self.deactivate_url(self.cara), {"reason": "fraud"}, format="json"
        )

        self.assertEqual(Order.objects.filter(user=self.cara).count(), 3)

    def test_deactivating_twice_is_refused(self):
        self.as_staff()
        self.client.post(
            self.deactivate_url(self.cara), {"reason": "first"}, format="json"
        )

        response = self.client.post(
            self.deactivate_url(self.cara), {"reason": "again"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reactivating_lets_them_back_in(self):
        self.as_staff()
        self.client.post(
            self.deactivate_url(self.cara), {"reason": "mistake"}, format="json"
        )

        response = self.client.post(self.activate_url(self.cara), {}, format="json")

        self.cara.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(self.cara.is_active)

        self.client.credentials()
        login = self.client.post(
            reverse("login"),
            {"username": "cara", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)

    def test_activating_an_active_account_is_refused(self):
        self.as_staff()

        response = self.client.post(self.activate_url(self.cara), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_the_response_carries_the_full_customer(self):
        self.as_staff()

        response = self.client.post(
            self.deactivate_url(self.cara), {"reason": "fraud"}, format="json"
        )

        self.assertEqual(response.data["order_count"], 3)
        self.assertEqual(response.data["total_spent"], "2997.00")
        self.assertIn("recent_orders", response.data)


class NoEditingTests(CustomerApiTestCase):
    def test_customers_cannot_be_created_edited_or_deleted_here(self):
        self.as_staff()

        created = self.client.post(
            reverse("org-customer-list"),
            {"username": "invented", "password": PASSWORD},
            format="json",
        )
        edited = self.client.patch(
            self.detail_url(self.cara), {"username": "renamed"}, format="json"
        )
        deleted = self.client.delete(self.detail_url(self.cara))

        for response in (created, edited, deleted):
            self.assertEqual(
                response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
            )
        self.cara.refresh_from_db()
        self.assertEqual(self.cara.username, "cara")
