"""Record where each order is delivered.

Written by hand rather than generated, because adding a required column to a
table that already has rows needs a decision about what those rows should
say. Orders placed before this change have no address of their own, so they
are backfilled from the customer's profile where there is one to copy —
that is genuinely the best-known destination for them — and left blank
otherwise, which the UI shows as "not recorded" rather than inventing
something a courier might act on.
"""

from django.db import migrations, models


def backfill_from_profiles(apps, schema_editor):
    """Copy each customer's saved address onto their existing orders."""
    Order = apps.get_model("orders", "Order")

    # One query for the orders that need it, and the profile comes along
    # with them, so this stays a handful of queries however long the table is.
    stale = Order.objects.filter(delivery_address="").select_related(
        "user", "user__profile"
    )

    updates = []
    for order in stale.iterator(chunk_size=500):
        profile = getattr(order.user, "profile", None)
        if profile is None:
            continue
        address = (profile.address or "").strip()
        if not address:
            continue
        order.delivery_address = address
        order.delivery_phone = (profile.phone or "").strip()
        updates.append(order)

        if len(updates) >= 500:
            Order.objects.bulk_update(
                updates, ["delivery_address", "delivery_phone"]
            )
            updates = []

    if updates:
        Order.objects.bulk_update(updates, ["delivery_address", "delivery_phone"])


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_orderstatusevent_order_cancellation_reason_and_more"),
        # The backfill reads Profile.address, so that column has to exist.
        ("accounts", "0003_profile_address"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="delivery_address",
            field=models.TextField(
                default="",
                help_text="The address this order is delivered to.",
            ),
            # The empty string is only for the rows that already exist; new
            # orders must supply an address of their own.
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_phone",
            field=models.CharField(
                blank=True,
                max_length=30,
                help_text="Number to call about this delivery.",
            ),
        ),
        migrations.RunPython(
            backfill_from_profiles,
            # Nothing to undo: dropping the columns takes the data with them.
            migrations.RunPython.noop,
        ),
    ]
