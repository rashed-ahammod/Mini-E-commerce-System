"""Give a profile a delivery address.

Blank at the database level because a Profile is created by a signal the
moment a User exists, before anyone has typed anything. The requirement
lives in the serializers (and in `Profile.is_complete`), which is what the
shop checks before letting an order through.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_backfill_profiles"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="address",
            field=models.TextField(
                blank=True,
                help_text="Where this person's orders are delivered by default.",
            ),
        ),
    ]
