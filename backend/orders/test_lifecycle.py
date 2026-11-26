"""Tests for the order lifecycle: status transitions and stock restoration.

These test the model rather than the API, because `transition_to()` is what
every caller goes through — the organization API, the admin, a shell, and
anything added later. If the rules only held in a view, the next caller
would be able to sidestep them.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Category, Product

from .models import (
    ALLOWED_TRANSITIONS,
    InvalidTransition,
    Order,
    OrderStatus,
    OrderStatusEvent,
)

User = get_user_model()


class LifecycleTestCase(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user("cara", password="StrongPass!234")
        self.staff = User.objects.create_user("sam", password="StrongPass!234")
        self.category = Category.objects.create(name="Phones")
        self.product = Product.objects.create(
            name="Flagship Phone",
            price=Decimal("999.00"),
            stock=10,
            category=self.category,
        )

    def make_order(self, quantity=2, status=OrderStatus.PENDING):
        order = Order.objects.create(
            user=self.customer,
            product=self.product,
            quantity=quantity,
            unit_price=self.product.price,
            status=status,
        )
        # Orders placed through the API reduce stock; mirror that here so
        # restoration can be checked against a realistic starting point.
        self.product.stock -= quantity
        self.product.save(update_fields=["stock"])
        self.product.refresh_from_db()
        return order


class DefaultStatusTests(LifecycleTestCase):
    def test_a_new_order_is_pending(self):
        order = self.make_order()

        self.assertEqual(order.status, OrderStatus.PENDING)
        self.assertTrue(order.is_open)
        self.assertIsNone(order.status_updated_at)

    def test_next_statuses_describes_what_may_follow(self):
        order = self.make_order()

        self.assertEqual(
            sorted(order.next_statuses),
            sorted([OrderStatus.CANCELLED, OrderStatus.CONFIRMED]),
        )


class TransitionTests(LifecycleTestCase):
    def test_the_happy_path_runs_to_delivered(self):
        order = self.make_order()

        for step in (
            OrderStatus.CONFIRMED,
            OrderStatus.PROCESSING,
            OrderStatus.SHIPPED,
            OrderStatus.DELIVERED,
        ):
            order.transition_to(step, changed_by=self.staff)

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.DELIVERED)
        self.assertFalse(order.is_open)

    def test_a_status_cannot_be_skipped(self):
        order = self.make_order()

        with self.assertRaises(InvalidTransition):
            order.transition_to(OrderStatus.SHIPPED, changed_by=self.staff)

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.PENDING)

    def test_an_order_cannot_go_backwards(self):
        order = self.make_order(status=OrderStatus.SHIPPED)

        with self.assertRaises(InvalidTransition):
            order.transition_to(OrderStatus.PROCESSING, changed_by=self.staff)

    def test_repeating_the_current_status_is_refused(self):
        order = self.make_order()

        with self.assertRaises(InvalidTransition) as caught:
            order.transition_to(OrderStatus.PENDING, changed_by=self.staff)

        self.assertIn("already", str(caught.exception))

    def test_a_delivered_order_is_finished(self):
        order = self.make_order(status=OrderStatus.DELIVERED)

        self.assertEqual(order.next_statuses, [])
        with self.assertRaises(InvalidTransition):
            order.transition_to(OrderStatus.CANCELLED, changed_by=self.staff)

    def test_the_error_names_what_is_allowed_instead(self):
        order = self.make_order()

        with self.assertRaises(InvalidTransition) as caught:
            order.transition_to(OrderStatus.DELIVERED, changed_by=self.staff)

        message = str(caught.exception)
        self.assertIn("confirmed", message)
        self.assertIn("cancelled", message)

    def test_status_updated_at_is_recorded(self):
        order = self.make_order()

        order.transition_to(OrderStatus.CONFIRMED, changed_by=self.staff)

        order.refresh_from_db()
        self.assertIsNotNone(order.status_updated_at)


class CancellationTests(LifecycleTestCase):
    def test_cancelling_returns_the_stock(self):
        order = self.make_order(quantity=3)
        self.assertEqual(self.product.stock, 7)

        order.transition_to(
            OrderStatus.CANCELLED, changed_by=self.staff, note="customer changed mind"
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_cancelling_records_when_and_why(self):
        order = self.make_order()

        order.transition_to(
            OrderStatus.CANCELLED, changed_by=self.staff, note="out of stock at depot"
        )

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.CANCELLED)
        self.assertIsNotNone(order.cancelled_at)
        self.assertEqual(order.cancellation_reason, "out of stock at depot")
        self.assertTrue(order.stock_restored)

    def test_stock_is_never_returned_twice(self):
        """A retried cancel must not inflate stock."""
        order = self.make_order(quantity=4)
        order.transition_to(OrderStatus.CANCELLED, changed_by=self.staff, note="first")

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

        # A second attempt is refused outright...
        with self.assertRaises(InvalidTransition):
            order.transition_to(
                OrderStatus.CANCELLED, changed_by=self.staff, note="again"
            )

        # ...and even calling the restore directly is a no-op.
        order._restore_stock()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_cancelling_is_allowed_up_to_processing(self):
        for status in (
            OrderStatus.PENDING,
            OrderStatus.CONFIRMED,
            OrderStatus.PROCESSING,
        ):
            with self.subTest(status=status):
                order = self.make_order(quantity=1, status=status)

                order.transition_to(
                    OrderStatus.CANCELLED, changed_by=self.staff, note="test"
                )

                order.refresh_from_db()
                self.assertEqual(order.status, OrderStatus.CANCELLED)

    def test_a_shipped_order_cannot_be_cancelled(self):
        """That would need a returns process, which does not exist here."""
        order = self.make_order(quantity=2, status=OrderStatus.SHIPPED)
        stock_before = self.product.stock

        with self.assertRaises(InvalidTransition):
            order.transition_to(
                OrderStatus.CANCELLED, changed_by=self.staff, note="too late"
            )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, stock_before)


class HistoryTests(LifecycleTestCase):
    def test_every_transition_is_recorded(self):
        order = self.make_order()

        order.transition_to(OrderStatus.CONFIRMED, changed_by=self.staff, note="paid")
        order.transition_to(OrderStatus.PROCESSING, changed_by=self.staff)

        events = list(OrderStatusEvent.objects.filter(order=order))
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].from_status, OrderStatus.PENDING)
        self.assertEqual(events[0].to_status, OrderStatus.CONFIRMED)
        self.assertEqual(events[0].note, "paid")
        self.assertEqual(events[0].changed_by, self.staff)

    def test_a_refused_transition_records_nothing(self):
        order = self.make_order()

        with self.assertRaises(InvalidTransition):
            order.transition_to(OrderStatus.DELIVERED, changed_by=self.staff)

        self.assertEqual(OrderStatusEvent.objects.filter(order=order).count(), 0)

    def test_history_survives_the_staff_account_being_deleted(self):
        order = self.make_order()
        order.transition_to(OrderStatus.CONFIRMED, changed_by=self.staff)

        self.staff.delete()

        event = OrderStatusEvent.objects.get(order=order)
        self.assertIsNone(event.changed_by)
        self.assertEqual(event.to_status, OrderStatus.CONFIRMED)


class TransitionMapTests(TestCase):
    def test_every_status_appears_in_the_map(self):
        """A new status added without a rule would silently allow nothing."""
        for status in OrderStatus:
            self.assertIn(status, ALLOWED_TRANSITIONS)

    def test_no_rule_points_at_an_unknown_status(self):
        known = set(OrderStatus)
        for targets in ALLOWED_TRANSITIONS.values():
            self.assertTrue(set(targets).issubset(known))
