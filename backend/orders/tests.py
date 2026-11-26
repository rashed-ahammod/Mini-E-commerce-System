"""Tests for the order endpoints.

The important behaviours here are: prices are decided by the server, stock is
validated and decremented, and a user can only ever see their own orders.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from catalog.models import Category, Product

from .models import Order

User = get_user_model()


class OrderTestCase(APITestCase):
    """Two users, one product with 5 units in stock."""

    def setUp(self):
        self.alice = User.objects.create_user("alice", password="StrongPass!234")
        self.bob = User.objects.create_user("bob", password="StrongPass!234")
        self.alice_token = Token.objects.create(user=self.alice)
        self.bob_token = Token.objects.create(user=self.bob)

        self.category = Category.objects.create(name="Phones")
        self.product = Product.objects.create(
            name="Flagship Phone",
            price=Decimal("999.00"),
            stock=5,
            category=self.category,
        )

    def authenticate(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def place_order(self, quantity=1, product=None):
        return self.client.post(
            reverse("order-list"),
            {"product_id": (product or self.product).id, "quantity": quantity},
            format="json",
        )


class CreateOrderTests(OrderTestCase):
    def test_anonymous_user_cannot_order(self):
        response = self.place_order()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Order.objects.count(), 0)

    def test_order_is_created_with_server_calculated_prices(self):
        self.authenticate(self.alice_token)

        response = self.place_order(quantity=2)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["unit_price"], "999.00")
        self.assertEqual(response.data["total_price"], "1998.00")
        self.assertEqual(response.data["user"], "alice")

    def test_order_is_attached_to_the_token_owner(self):
        self.authenticate(self.bob_token)

        self.place_order()

        self.assertEqual(Order.objects.get().user, self.bob)

    def test_client_cannot_choose_its_own_price(self):
        self.authenticate(self.alice_token)

        response = self.client.post(
            reverse("order-list"),
            {
                "product_id": self.product.id,
                "quantity": 1,
                "unit_price": "0.01",
                "total_price": "0.01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Order.objects.get().total_price, Decimal("999.00"))

    def test_successful_order_reduces_stock(self):
        self.authenticate(self.alice_token)

        self.place_order(quantity=2)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_price_change_does_not_rewrite_past_orders(self):
        """unit_price is a snapshot taken when the order is placed."""
        self.authenticate(self.alice_token)
        self.place_order(quantity=1)

        self.product.price = Decimal("1299.00")
        self.product.save()

        order = Order.objects.get()
        self.assertEqual(order.unit_price, Decimal("999.00"))
        self.assertEqual(order.total_price, Decimal("999.00"))

    # ---- stock validation ------------------------------------------------

    def test_ordering_more_than_the_stock_is_rejected(self):
        self.authenticate(self.alice_token)

        response = self.place_order(quantity=6)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quantity", response.data)
        self.assertIn("5", str(response.data["quantity"]))

    def test_a_rejected_order_leaves_stock_untouched(self):
        self.authenticate(self.alice_token)

        self.place_order(quantity=99)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertEqual(Order.objects.count(), 0)

    def test_ordering_exactly_the_remaining_stock_is_allowed(self):
        self.authenticate(self.alice_token)

        response = self.place_order(quantity=5)

        self.product.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.product.stock, 0)

    def test_an_out_of_stock_product_cannot_be_ordered(self):
        sold_out = Product.objects.create(
            name="Sold Out", price=Decimal("10.00"), stock=0, category=self.category
        )
        self.authenticate(self.alice_token)

        response = self.place_order(quantity=1, product=sold_out)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_quantity_must_be_at_least_one(self):
        self.authenticate(self.alice_token)

        zero = self.place_order(quantity=0)
        negative = self.place_order(quantity=-3)

        self.assertEqual(zero.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(negative.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_product_is_rejected(self):
        self.authenticate(self.alice_token)

        response = self.client.post(
            reverse("order-list"),
            {"product_id": 9999, "quantity": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("product_id", response.data)

    def test_stock_cannot_be_oversold_by_repeated_orders(self):
        self.authenticate(self.alice_token)

        first = self.place_order(quantity=3)
        second = self.place_order(quantity=3)

        self.product.refresh_from_db()
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.product.stock, 2)


class ViewOrderTests(OrderTestCase):
    def setUp(self):
        super().setUp()
        self.alice_order = Order.objects.create(
            user=self.alice,
            product=self.product,
            quantity=1,
            unit_price=self.product.price,
        )
        self.bob_order = Order.objects.create(
            user=self.bob,
            product=self.product,
            quantity=2,
            unit_price=self.product.price,
        )

    def test_listing_orders_requires_a_token(self):
        response = self.client.get(reverse("order-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_user_only_sees_their_own_orders(self):
        self.authenticate(self.alice_token)

        response = self.client.get(reverse("order-list"))

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.alice_order.id)

    def test_order_list_is_paginated(self):
        self.authenticate(self.alice_token)

        response = self.client.get(reverse("order-list"))

        for key in ("count", "next", "previous", "results"):
            self.assertIn(key, response.data)

    def test_a_user_can_retrieve_their_own_order(self):
        self.authenticate(self.alice_token)

        response = self.client.get(
            reverse("order-detail", args=[self.alice_order.id])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["product"]["name"], "Flagship Phone")

    def test_another_users_order_returns_404_not_403(self):
        """404 keeps the existence of someone else's order private."""
        self.authenticate(self.alice_token)

        response = self.client.get(reverse("order-detail", args=[self.bob_order.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_orders_cannot_be_edited_or_deleted(self):
        self.authenticate(self.alice_token)
        url = reverse("order-detail", args=[self.alice_order.id])

        updated = self.client.patch(url, {"quantity": 99}, format="json")
        deleted = self.client.delete(url)

        self.assertEqual(updated.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(deleted.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(Order.objects.filter(id=self.alice_order.id).count(), 1)

    def test_newest_order_is_listed_first(self):
        newer = Order.objects.create(
            user=self.alice,
            product=self.product,
            quantity=1,
            unit_price=self.product.price,
        )
        self.authenticate(self.alice_token)

        response = self.client.get(reverse("order-list"))

        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [newer.id, self.alice_order.id])
