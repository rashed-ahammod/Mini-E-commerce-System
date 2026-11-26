"""Fill the database with a sample catalog for development and demos.

    python manage.py seed_data
    python manage.py seed_data --flush        # delete existing data first
    python manage.py seed_data --demo-user    # also create the demo account

The catalog itself lives in `catalog_data.json` next to this file: 6
categories and 49 products with real names, descriptions, prices and
photographs. Keeping the data out of the code means it can be reviewed,
edited or regenerated without touching the command.

Safe to run repeatedly: products are matched by name inside their category,
so a second run updates them instead of creating duplicates.

Product pictures are referenced by URL rather than uploaded, because hosts
such as Render wipe the filesystem on every deploy, which would leave the
catalog imageless after the first redeploy.
"""

import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Category, Product
from orders.models import Order

User = get_user_model()

DATA_FILE = Path(__file__).resolve().parent / "catalog_data.json"

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo12345"


class Command(BaseCommand):
    help = "Create the sample catalog of categories and products."

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
            Order.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            self.stdout.write(self.style.WARNING("Existing catalog data deleted."))

        categories = json.loads(DATA_FILE.read_text(encoding="utf-8"))

        created = updated = 0

        for entry in categories:
            category, _ = Category.objects.update_or_create(
                name=entry["name"],
                defaults={"description": entry["description"]},
            )
            for product in entry["products"]:
                _, was_created = Product.objects.update_or_create(
                    name=product["name"],
                    category=category,
                    defaults={
                        "description": product["description"],
                        "price": Decimal(product["price"]),
                        "stock": product["stock"],
                        "image_url": product.get("image_url", ""),
                    },
                )
                created += was_created
                updated += not was_created

        self.stdout.write(
            self.style.SUCCESS(
                f"{Category.objects.count()} categories, "
                f"{created} products created, {updated} updated."
            )
        )

        if options["demo_user"]:
            user, was_created = User.objects.get_or_create(username=DEMO_USERNAME)
            user.set_password(DEMO_PASSWORD)
            user.save()
            action = "created" if was_created else "password reset"
            self.stdout.write(
                self.style.SUCCESS(
                    f"Demo user {action}: {DEMO_USERNAME} / {DEMO_PASSWORD}"
                )
            )
