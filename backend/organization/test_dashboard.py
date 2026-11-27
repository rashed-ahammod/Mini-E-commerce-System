"""Tests for the organization dashboard.

These assert the arithmetic, not just the shape. A dashboard that returns
the right keys with wrong numbers is worse than no dashboard: somebody will
make a decision from it.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import Role, profile_for
from catalog.models import Category, Product
from orders.models import Order, OrderStatus

User = get_user_model()

PASSWORD = "StrongPass!234"


class DashboardTestCase(APITestCase):
    """A small but deliberate dataset, so every total can be checked by hand.

        cara  2 x Flagship (999.00)  = 1998.00  delivered
        cara  1 x Flagship (999.00)  =  999.00  pending
        dan   3 x Budget   (199.00)  =  597.00  shipped
        dan   1 x Budget   (199.00)  =  199.00  cancelled   <- excluded

        booked   = 1998 + 999 + 597 = 3594.00   (everything not cancelled)
        realised = 1998.00                       (delivered only)
        lost     =  199.00
    """

    url = reverse("org-dashboard")

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
        self.flagship = Product.objects.create(
            name="Flagship Phone",
            price=Decimal("999.00"),
            stock=10,
            category=self.category,
        )
        self.budget = Product.objects.create(
            name="Budget Phone",
            price=Decimal("199.00"),
            stock=3,
            category=self.category,
        )
        self.sold_out = Product.objects.create(
            name="Sold Out Phone",
            price=Decimal("499.00"),
            stock=0,
            category=self.category,
        )

        self.order(self.cara, self.flagship, 2, OrderStatus.DELIVERED)
        self.order(self.cara, self.flagship, 1, OrderStatus.PENDING)
        self.order(self.dan, self.budget, 3, OrderStatus.SHIPPED)
        self.order(self.dan, self.budget, 1, OrderStatus.CANCELLED)

    def order(self, user, product, quantity, order_status):
        return Order.objects.create(
            user=user,
            product=product,
            quantity=quantity,
            unit_price=product.price,
            status=order_status,
        )

    def as_staff(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.staff_token.key}")

    def get_dashboard(self, **params):
        self.as_staff()
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data


class AccessTests(DashboardTestCase):
    def test_anonymous_gets_401(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_gets_403(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.cara_token.key}")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_organization_user_gets_200(self):
        self.as_staff()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class OrderCountTests(DashboardTestCase):
    def test_order_counts(self):
        data = self.get_dashboard()["orders"]

        self.assertEqual(data["total"], 4)
        self.assertEqual(data["delivered"], 1)
        self.assertEqual(data["cancelled"], 1)
        # pending + shipped are still being worked on.
        self.assertEqual(data["open"], 2)

    def test_todays_orders_are_counted(self):
        data = self.get_dashboard()["orders"]

        self.assertEqual(data["today"], 4)


class RevenueTests(DashboardTestCase):
    def test_booked_revenue_excludes_cancelled_orders(self):
        data = self.get_dashboard()["revenue"]

        self.assertEqual(data["booked"], "3594.00")

    def test_realised_revenue_counts_only_delivered_orders(self):
        data = self.get_dashboard()["revenue"]

        self.assertEqual(data["realised"], "1998.00")

    def test_cancelled_value_is_reported_separately(self):
        data = self.get_dashboard()["revenue"]

        self.assertEqual(data["lost_to_cancellations"], "199.00")

    def test_average_order_value_is_over_non_cancelled_orders(self):
        data = self.get_dashboard()["revenue"]

        # 3594.00 over 3 orders, not 4.
        self.assertEqual(data["average_order_value"], "1198.00")

    def test_revenue_is_zero_rather_than_null_with_no_orders(self):
        Order.objects.all().delete()

        data = self.get_dashboard()["revenue"]

        self.assertEqual(data["booked"], "0.00")
        self.assertEqual(data["average_order_value"], "0.00")


class StatusBreakdownTests(DashboardTestCase):
    def test_every_status_appears_even_with_no_orders(self):
        """So a dashboard renders a zero rather than a gap."""
        data = self.get_dashboard()["orders_by_status"]

        statuses = [row["status"] for row in data]
        self.assertEqual(statuses, [s.value for s in OrderStatus])

    def test_counts_and_values_per_status(self):
        by_status = {row["status"]: row for row in self.get_dashboard()["orders_by_status"]}

        self.assertEqual(by_status["delivered"]["count"], 1)
        self.assertEqual(by_status["delivered"]["value"], "1998.00")
        self.assertEqual(by_status["confirmed"]["count"], 0)
        self.assertEqual(by_status["confirmed"]["value"], "0.00")
        self.assertEqual(by_status["pending"]["label"], "Pending")


class CatalogTests(DashboardTestCase):
    def test_catalog_counts(self):
        data = self.get_dashboard()["catalog"]

        self.assertEqual(data["products"], 3)
        self.assertEqual(data["categories"], 1)
        self.assertEqual(data["out_of_stock"], 1)
        # Budget Phone has 3, which is at or below the default threshold of 5.
        self.assertEqual(data["low_stock"], 1)
        self.assertEqual(data["units_in_stock"], 13)

    def test_low_stock_threshold_can_be_raised(self):
        data = self.get_dashboard(low_stock_threshold=10)["catalog"]

        # Flagship (10) now counts as low too; the sold-out one never does,
        # because it is reported as out of stock instead.
        self.assertEqual(data["low_stock"], 2)


class CustomerTests(DashboardTestCase):
    def test_organization_users_are_not_counted_as_customers(self):
        data = self.get_dashboard()["customers"]

        self.assertEqual(data["total"], 2)  # cara and dan, not sam

    def test_customers_with_orders(self):
        User.objects.create_user("never-ordered", password=PASSWORD)

        data = self.get_dashboard()["customers"]

        self.assertEqual(data["total"], 3)
        self.assertEqual(data["with_orders"], 2)

    def test_inactive_customers_are_counted(self):
        self.dan.is_active = False
        self.dan.save()

        data = self.get_dashboard()["customers"]

        self.assertEqual(data["inactive"], 1)


class TopProductTests(DashboardTestCase):
    def test_best_sellers_are_ranked_by_units(self):
        data = self.get_dashboard()["top_products"]

        self.assertEqual(data[0]["name"], "Flagship Phone")
        self.assertEqual(data[0]["units_sold"], 3)  # 2 + 1
        self.assertEqual(data[0]["order_count"], 2)
        self.assertEqual(data[0]["revenue"], "2997.00")

    def test_cancelled_orders_do_not_count_towards_best_sellers(self):
        """Those units came back; counting them misdirects restocking."""
        data = {row["name"]: row for row in self.get_dashboard()["top_products"]}

        # Budget Phone: 3 shipped + 1 cancelled, so 3 units, not 4.
        self.assertEqual(data["Budget Phone"]["units_sold"], 3)
        self.assertEqual(data["Budget Phone"]["revenue"], "597.00")

    def test_products_never_ordered_are_absent(self):
        names = [row["name"] for row in self.get_dashboard()["top_products"]]

        self.assertNotIn("Sold Out Phone", names)


class NeedsAttentionTests(DashboardTestCase):
    def test_low_stock_products_are_listed_lowest_first(self):
        data = self.get_dashboard()["needs_attention"]["low_stock_products"]

        self.assertEqual(data[0]["name"], "Sold Out Phone")
        self.assertEqual(data[0]["stock"], 0)
        self.assertEqual(data[1]["name"], "Budget Phone")

    def test_pending_orders_are_listed_oldest_first(self):
        data = self.get_dashboard()["needs_attention"]["orders_awaiting_action"]

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["customer"], "cara")
        self.assertEqual(data[0]["product"], "Flagship Phone")


class TrendTests(DashboardTestCase):
    def test_the_series_has_one_entry_per_day(self):
        data = self.get_dashboard(days=7)

        self.assertEqual(data["window_days"], 7)
        self.assertEqual(len(data["daily"]), 7)

    def test_quiet_days_are_zero_rather_than_missing(self):
        """A gap would let a chart draw a line implying activity."""
        daily = self.get_dashboard(days=7)["daily"]

        self.assertEqual(daily[0]["orders"], 0)
        self.assertEqual(daily[0]["revenue"], "0.00")

    def test_todays_activity_lands_on_the_last_entry(self):
        daily = self.get_dashboard(days=7)["daily"]

        self.assertEqual(daily[-1]["date"], timezone.localdate())
        self.assertEqual(daily[-1]["orders"], 4)
        self.assertEqual(daily[-1]["revenue"], "3594.00")

    def test_an_out_of_range_window_is_rejected(self):
        self.as_staff()

        too_big = self.client.get(self.url, {"days": 400})
        too_small = self.client.get(self.url, {"days": 0})

        self.assertEqual(too_big.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(too_small.status_code, status.HTTP_400_BAD_REQUEST)


class QueryCountTests(DashboardTestCase):
    def test_the_dashboard_does_not_scale_with_the_number_of_orders(self):
        """Aggregates, not loops: adding orders must not add queries.

        The absolute number is not asserted — it would change for innocent
        reasons — only that it stays the same as the data grows.
        """
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        self.as_staff()
        with CaptureQueriesContext(connection) as baseline:
            self.client.get(self.url)
        before = len(baseline.captured_queries)

        for _ in range(25):
            self.order(self.cara, self.flagship, 1, OrderStatus.DELIVERED)

        with CaptureQueriesContext(connection) as after:
            self.client.get(self.url)

        self.assertEqual(len(after.captured_queries), before)
        # A loop over orders would be far above this; a sanity ceiling.
        self.assertLess(before, 20)


class OlderDataTests(DashboardTestCase):
    def test_orders_outside_the_window_are_excluded_from_window_figures(self):
        old = self.order(self.cara, self.flagship, 1, OrderStatus.DELIVERED)
        Order.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=60)
        )

        data = self.get_dashboard(days=30)

        # The lifetime totals see it...
        self.assertEqual(data["orders"]["total"], 5)
        # ...but the 30-day window does not.
        self.assertEqual(data["orders"]["in_window"], 4)
        self.assertEqual(data["revenue"]["in_window"], "3594.00")
