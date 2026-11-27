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


# A destination the server will accept: specific enough to deliver to.
ADDRESS = "House 12, Road 5, Dhanmondi, Dhaka 1205"
PROFILE_ADDRESS = "Flat 4B, 90 Gulshan Avenue, Gulshan, Dhaka 1212"
PHONE = "+880 1711 123456"


class OrderTestCase(APITestCase):
    """Two users with complete profiles, one product with 5 units in stock."""

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", email="alice@example.com", password="StrongPass!234"
        )
        self.bob = User.objects.create_user("bob", password="StrongPass!234")
        self.alice_token = Token.objects.create(user=self.alice)
        self.bob_token = Token.objects.create(user=self.bob)

        # Both can order, which is the ordinary case. The tests that care
        # about missing details empty these out themselves.
        for user in (self.alice, self.bob):
            profile = user.profile
            profile.phone = PHONE
            profile.address = PROFILE_ADDRESS
            profile.save()

        self.category = Category.objects.create(name="Phones")
        self.product = Product.objects.create(
            name="Flagship Phone",
            price=Decimal("999.00"),
            stock=5,
            category=self.category,
        )

    def authenticate(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def place_order(self, quantity=1, product=None, **extra):
        """Place an order, typing in a delivery address by default.

        `extra` overrides or adds fields, which is how the delivery tests
        below ask for the profile address instead, or leave it out entirely.
        """
        payload = {
            "product_id": (product or self.product).id,
            "quantity": quantity,
            "delivery_address": ADDRESS,
            **extra,
        }
        return self.client.post(
            reverse("order-list"),
            {key: value for key, value in payload.items() if value is not None},
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
                "delivery_address": ADDRESS,
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
            {"product_id": 9999, "quantity": 1, "delivery_address": ADDRESS},
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
            delivery_address=ADDRESS,
            delivery_phone=PHONE,
        )
        self.bob_order = Order.objects.create(
            user=self.bob,
            product=self.product,
            quantity=2,
            unit_price=self.product.price,
            delivery_address=ADDRESS,
            delivery_phone=PHONE,
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
            delivery_address=ADDRESS,
            delivery_phone=PHONE,
        )
        self.authenticate(self.alice_token)

        response = self.client.get(reverse("order-list"))

        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [newer.id, self.alice_order.id])


class DeliveryAddressTests(OrderTestCase):
    """Where an order goes, and the two ways a customer can say so.

    An address is required, because an order that cannot be delivered is not
    an order. It may be typed in for this one purchase, or taken from the
    profile — and either way it is snapshotted onto the order, so moving
    house later does not rewrite where last month's parcel went.
    """

    def test_typed_address_is_stored_on_the_order(self):
        self.authenticate(self.alice_token)

        response = self.place_order(delivery_address=ADDRESS)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["delivery_address"], ADDRESS)
        self.assertEqual(Order.objects.get().delivery_address, ADDRESS)

    def test_address_is_required(self):
        """The field is named in the error, so a form can point at it."""
        self.authenticate(self.alice_token)

        response = self.place_order(delivery_address=None)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("delivery_address", response.data)
        self.assertEqual(Order.objects.count(), 0)

    def test_a_refused_address_leaves_stock_untouched(self):
        """Nothing is half-done: no order, and the units stay on the shelf."""
        self.authenticate(self.alice_token)

        response = self.place_order(quantity=2, delivery_address="")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertEqual(Order.objects.count(), 0)

    def test_a_vague_address_is_refused(self):
        self.authenticate(self.alice_token)

        response = self.place_order(delivery_address="home")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("delivery_address", response.data)

    def test_profile_address_can_be_used_instead(self):
        """The "deliver to my saved address" option."""
        self.authenticate(self.alice_token)

        response = self.place_order(
            delivery_address=None, use_profile_address=True
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["delivery_address"], PROFILE_ADDRESS)
        self.assertEqual(response.data["delivery_phone"], PHONE)

    def test_profile_address_wins_over_a_typed_one_when_asked_for(self):
        """The customer chose the saved address; stale form text is ignored."""
        self.authenticate(self.alice_token)

        response = self.place_order(
            delivery_address=ADDRESS, use_profile_address=True
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["delivery_address"], PROFILE_ADDRESS)

    def test_asking_for_a_profile_address_that_is_not_there_is_refused(self):
        """And says what to do about it, rather than failing silently."""
        profile = self.alice.profile
        profile.address = ""
        profile.save()
        self.authenticate(self.alice_token)

        response = self.place_order(
            delivery_address=None, use_profile_address=True
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("use_profile_address", response.data)
        self.assertEqual(Order.objects.count(), 0)

    def test_phone_falls_back_to_the_profile(self):
        """A number is always recorded, even when the form did not ask."""
        self.authenticate(self.alice_token)

        response = self.place_order()

        self.assertEqual(response.data["delivery_phone"], PHONE)

    def test_a_typed_phone_is_kept_over_the_profile_one(self):
        """"Call me on this number instead" has to survive."""
        self.authenticate(self.alice_token)

        response = self.place_order(delivery_phone="+880 1999 888777")

        self.assertEqual(response.data["delivery_phone"], "+880 1999 888777")
        self.assertEqual(Order.objects.get().delivery_phone, "+880 1999 888777")

    def test_an_order_without_any_phone_is_refused(self):
        profile = self.alice.profile
        profile.phone = ""
        profile.save()
        self.authenticate(self.alice_token)

        response = self.place_order()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("delivery_phone", response.data)

    def test_address_can_be_saved_to_the_profile(self):
        """The "use this as my default from now on" option."""
        new_address = "Plot 7, Sector 11, Uttara, Dhaka 1230"
        self.authenticate(self.alice_token)

        response = self.place_order(
            delivery_address=new_address, save_to_profile=True
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.alice.profile.refresh_from_db()
        self.assertEqual(self.alice.profile.address, new_address)

    def test_the_profile_is_left_alone_unless_asked(self):
        self.authenticate(self.alice_token)

        self.place_order(delivery_address="Plot 7, Sector 11, Uttara, Dhaka")

        self.alice.profile.refresh_from_db()
        self.assertEqual(self.alice.profile.address, PROFILE_ADDRESS)

    def test_the_address_is_a_snapshot(self):
        """Moving house does not rewrite where past orders were sent."""
        self.authenticate(self.alice_token)
        self.place_order(delivery_address=ADDRESS)

        profile = self.alice.profile
        profile.address = "Somewhere else entirely, Chattogram 4000"
        profile.save()

        self.assertEqual(Order.objects.get().delivery_address, ADDRESS)

    def test_a_customer_cannot_order_to_someone_elses_saved_address(self):
        """`use_profile_address` reads the token owner's profile, no one else's."""
        self.authenticate(self.bob_token)
        bobs_profile = self.bob.profile
        bobs_profile.address = "Bob House, 1 Bob Road, Dhaka 1000"
        bobs_profile.save()

        response = self.place_order(
            delivery_address=None, use_profile_address=True
        )

        self.assertEqual(response.data["delivery_address"], bobs_profile.address)
