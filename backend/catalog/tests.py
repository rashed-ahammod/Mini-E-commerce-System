"""Tests for the category and product endpoints.

Covers the permission rules, the five CRUD operations, and the filtering,
searching, ordering and pagination the assignment asks for.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from catalog.models import Category, Product
from orders.models import Order

User = get_user_model()


class CatalogTestCase(APITestCase):
    """Shared fixtures: two categories, three products and a logged-in user."""

    def setUp(self):
        self.user = User.objects.create_user("alice", password="StrongPass!234")
        self.token = Token.objects.create(user=self.user)

        self.phones = Category.objects.create(name="Phones", description="Smartphones")
        self.laptops = Category.objects.create(name="Laptops")

        self.cheap_phone = Product.objects.create(
            name="Budget Phone",
            description="Entry level phone",
            price=Decimal("199.00"),
            stock=10,
            category=self.phones,
        )
        self.flagship = Product.objects.create(
            name="Flagship Phone",
            price=Decimal("999.00"),
            stock=3,
            category=self.phones,
        )
        self.laptop = Product.objects.create(
            name="Gaming Laptop",
            description="Powerful laptop",
            price=Decimal("1499.00"),
            stock=0,
            category=self.laptops,
        )

    def authenticate(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def names_in(self, response):
        return [row["name"] for row in response.data["results"]]


class CategoryApiTests(CatalogTestCase):
    def test_anyone_can_list_categories(self):
        response = self.client.get(reverse("category-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_list_includes_product_count(self):
        response = self.client.get(reverse("category-list"))

        counts = {row["name"]: row["product_count"] for row in response.data["results"]}
        self.assertEqual(counts, {"Phones": 2, "Laptops": 1})

    def test_created_category_also_reports_product_count(self):
        """The Count annotation only exists on the list queryset, so creation
        used to return a category without this field."""
        self.authenticate()

        response = self.client.post(
            reverse("category-list"), {"name": "Audio"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["product_count"], 0)

    def test_retrieve_single_category(self):
        response = self.client.get(reverse("category-detail", args=[self.phones.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Phones")

    def test_anonymous_user_cannot_write(self):
        create = self.client.post(
            reverse("category-list"), {"name": "Audio"}, format="json"
        )
        update = self.client.patch(
            reverse("category-detail", args=[self.phones.id]),
            {"name": "Hacked"},
            format="json",
        )
        delete = self.client.delete(reverse("category-detail", args=[self.phones.id]))

        for response in (create, update, delete):
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Category.objects.count(), 2)

    def test_update_and_delete_category(self):
        self.authenticate()

        updated = self.client.patch(
            reverse("category-detail", args=[self.laptops.id]),
            {"description": "Notebooks"},
            format="json",
        )
        deleted = self.client.delete(reverse("category-detail", args=[self.laptops.id]))

        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data["description"], "Notebooks")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Category.objects.filter(id=self.laptops.id).exists())

    def test_duplicate_category_name_is_rejected(self):
        self.authenticate()

        response = self.client.post(
            reverse("category-list"), {"name": "Phones"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deleting_a_category_with_ordered_products_returns_409(self):
        Order.objects.create(
            user=self.user,
            product=self.flagship,
            quantity=1,
            unit_price=self.flagship.price,
        )
        self.authenticate()

        response = self.client.delete(reverse("category-detail", args=[self.phones.id]))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("detail", response.data)
        self.assertTrue(Category.objects.filter(id=self.phones.id).exists())


class ProductApiTests(CatalogTestCase):
    def test_list_is_public_and_paginated(self):
        response = self.client.get(reverse("product-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in ("count", "next", "previous", "results"):
            self.assertIn(key, response.data)
        self.assertEqual(response.data["count"], 3)

    def test_page_size_can_be_set_by_the_client(self):
        response = self.client.get(reverse("product-list"), {"page_size": 2})

        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["count"], 3)
        self.assertIsNotNone(response.data["next"])

    def test_page_size_above_the_cap_does_not_error(self):
        response = self.client.get(reverse("product-list"), {"page_size": 5000})

        # The cap is 100, so with 3 products we simply get all of them back.
        self.assertEqual(len(response.data["results"]), 3)

    def test_product_includes_nested_category_and_stock_flag(self):
        response = self.client.get(
            reverse("product-detail", args=[self.cheap_phone.id])
        )

        self.assertEqual(response.data["category"]["name"], "Phones")
        self.assertTrue(response.data["in_stock"])

    def test_out_of_stock_product_reports_in_stock_false(self):
        response = self.client.get(reverse("product-detail", args=[self.laptop.id]))

        self.assertFalse(response.data["in_stock"])

    # ---- search / filter / ordering --------------------------------------

    def test_search_matches_name(self):
        response = self.client.get(reverse("product-list"), {"search": "phone"})

        self.assertEqual(response.data["count"], 2)
        self.assertNotIn("Gaming Laptop", self.names_in(response))

    def test_search_also_matches_description(self):
        response = self.client.get(reverse("product-list"), {"search": "Powerful"})

        self.assertEqual(self.names_in(response), ["Gaming Laptop"])

    def test_filter_by_category_id(self):
        response = self.client.get(reverse("product-list"), {"category": self.phones.id})

        self.assertEqual(response.data["count"], 2)

    def test_filter_by_category_name(self):
        response = self.client.get(reverse("product-list"), {"category_name": "laptops"})

        self.assertEqual(self.names_in(response), ["Gaming Laptop"])

    def test_filter_by_price_range(self):
        response = self.client.get(
            reverse("product-list"), {"min_price": "500", "max_price": "1200"}
        )

        self.assertEqual(self.names_in(response), ["Flagship Phone"])

    def test_filter_by_exact_price(self):
        response = self.client.get(reverse("product-list"), {"price": "199.00"})

        self.assertEqual(self.names_in(response), ["Budget Phone"])

    def test_filter_in_stock(self):
        in_stock = self.client.get(reverse("product-list"), {"in_stock": "true"})
        out_of_stock = self.client.get(reverse("product-list"), {"in_stock": "false"})

        self.assertEqual(
            sorted(self.names_in(in_stock)), ["Budget Phone", "Flagship Phone"]
        )
        self.assertEqual(self.names_in(out_of_stock), ["Gaming Laptop"])

    def test_order_by_price_ascending_and_descending(self):
        ascending = self.client.get(reverse("product-list"), {"ordering": "price"})
        descending = self.client.get(reverse("product-list"), {"ordering": "-price"})

        self.assertEqual(
            self.names_in(ascending),
            ["Budget Phone", "Flagship Phone", "Gaming Laptop"],
        )
        self.assertEqual(self.names_in(descending), self.names_in(ascending)[::-1])

    def test_filters_can_be_combined(self):
        response = self.client.get(
            reverse("product-list"),
            {"search": "phone", "category": self.phones.id, "ordering": "-price"},
        )

        self.assertEqual(self.names_in(response), ["Flagship Phone", "Budget Phone"])

    # ---- writing ---------------------------------------------------------

    def test_anonymous_user_cannot_create_a_product(self):
        response = self.client.post(
            reverse("product-list"),
            {"name": "Nope", "price": "1.00", "stock": 1, "category_id": self.phones.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Product.objects.count(), 3)

    def test_create_product_with_category_id(self):
        self.authenticate()

        response = self.client.post(
            reverse("product-list"),
            {
                "name": "New Phone",
                "description": "Fresh",
                "price": "349.99",
                "stock": 5,
                "category_id": self.phones.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Written with a plain id, read back as a nested object.
        self.assertEqual(
            response.data["category"], {"id": self.phones.id, "name": "Phones"}
        )
        self.assertEqual(Product.objects.get(name="New Phone").price, Decimal("349.99"))

    def test_create_product_rejects_bad_input(self):
        self.authenticate()

        response = self.client.post(
            reverse("product-list"),
            {"name": "Bad", "price": "-5", "stock": 1, "category_id": 9999},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("price", response.data)
        self.assertIn("category_id", response.data)

    def test_update_product(self):
        self.authenticate()

        response = self.client.patch(
            reverse("product-detail", args=[self.cheap_phone.id]),
            {"price": "179.00", "stock": 25},
            format="json",
        )

        self.cheap_phone.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.cheap_phone.price, Decimal("179.00"))
        self.assertEqual(self.cheap_phone.stock, 25)

    def test_delete_product_without_orders(self):
        self.authenticate()

        response = self.client.delete(
            reverse("product-detail", args=[self.cheap_phone.id])
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(id=self.cheap_phone.id).exists())

    def test_deleting_an_ordered_product_returns_409_not_500(self):
        Order.objects.create(
            user=self.user,
            product=self.cheap_phone,
            quantity=1,
            unit_price=self.cheap_phone.price,
        )
        self.authenticate()

        response = self.client.delete(
            reverse("product-detail", args=[self.cheap_phone.id])
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(Product.objects.filter(id=self.cheap_phone.id).exists())

    def test_missing_product_returns_404(self):
        response = self.client.get(reverse("product-detail", args=[9999]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
