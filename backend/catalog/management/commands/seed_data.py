"""Fill the database with sample categories and products for development.

    python manage.py seed_data
    python manage.py seed_data --flush   # delete existing catalog data first
    python manage.py seed_data --demo-user

Safe to run repeatedly: products are matched by name inside their category,
so a second run updates them instead of creating duplicates.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Category, Product
from orders.models import Order

User = get_user_model()

# (category name, category description, [products])
# Each product: (name, description, price, stock)
SAMPLE_DATA = [
    (
        "Phones",
        "Smartphones from budget to flagship.",
        [
            ("Pixel Lite 5G", "Compact Android phone with a clean interface.", "299.00", 25),
            ("Galaxy S Ultra", "Flagship phone with a 200MP camera.", "1199.00", 8),
            ("iPhone Air", "Lightweight iPhone with an A18 chip.", "999.00", 12),
            ("Budget Phone X", "Entry level phone with a big battery.", "149.50", 60),
            ("Nord Edge", "Mid-range phone with fast charging.", "449.00", 0),
        ],
    ),
    (
        "Laptops",
        "Notebooks for work, study and gaming.",
        [
            ("UltraBook 14", "Thin and light laptop, 16GB RAM.", "1099.00", 10),
            ("Gaming Beast 17", "RTX graphics and a 165Hz display.", "1899.99", 4),
            ("Student Chromebook", "Affordable laptop for coursework.", "279.00", 30),
        ],
    ),
    (
        "Audio",
        "Headphones, earbuds and speakers.",
        [
            ("NoiseCancel Pro", "Over-ear headphones with ANC.", "349.00", 18),
            ("Daily Earbuds", "Wireless earbuds with a charging case.", "79.99", 75),
            ("Party Speaker 40W", "Portable Bluetooth speaker.", "129.00", 22),
        ],
    ),
    (
        "Accessories",
        "Cables, chargers and cases.",
        [
            ("65W GaN Charger", "Two-port fast charger.", "39.99", 100),
            ("Braided USB-C Cable", "2 metre, 100W rated.", "12.50", 250),
            ("Leather Phone Case", "Slim case with card slots.", "24.00", 40),
        ],
    ),
]

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo12345"


class Command(BaseCommand):
    help = "Create sample categories and products for local development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing orders, products and categories first.",
        )
        parser.add_argument(
            "--demo-user",
            action="store_true",
            help=f"Also create a '{DEMO_USERNAME}' user for testing the order API.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            # Orders go first: products are PROTECTed while an order uses them.
            deleted_orders, _ = Order.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            self.stdout.write(self.style.WARNING("Existing catalog data deleted."))

        created_products = updated_products = 0

        for name, description, products in SAMPLE_DATA:
            category, _ = Category.objects.update_or_create(
                name=name,
                defaults={"description": description},
            )
            for product_name, product_description, price, stock in products:
                _, created = Product.objects.update_or_create(
                    name=product_name,
                    category=category,
                    defaults={
                        "description": product_description,
                        "price": Decimal(price),
                        "stock": stock,
                    },
                )
                if created:
                    created_products += 1
                else:
                    updated_products += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{Category.objects.count()} categories, "
                f"{created_products} products created, "
                f"{updated_products} updated."
            )
        )

        if options["demo_user"]:
            user, created = User.objects.get_or_create(username=DEMO_USERNAME)
            user.set_password(DEMO_PASSWORD)
            user.save()
            action = "created" if created else "password reset"
            self.stdout.write(
                self.style.SUCCESS(
                    f"Demo user {action}: {DEMO_USERNAME} / {DEMO_PASSWORD}"
                )
            )
