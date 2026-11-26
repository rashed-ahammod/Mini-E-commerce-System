"""Give every existing user a Profile.

The post_save signal only fires for users created from now on, so accounts
that already exist — the demo customer, any superuser, anyone who registered
before this release — would have no profile and would hit
`Profile.DoesNotExist` on their next request.

Superusers are made organization admins: whoever owns the server should not
have to be granted access to their own shop. Everyone else becomes a
customer, which is the safe default — nobody is silently promoted.
"""

from django.db import migrations


def create_missing_profiles(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Profile = apps.get_model("accounts", "Profile")

    for user in User.objects.filter(profile__isnull=True):
        Profile.objects.create(
            user=user,
            role="admin" if user.is_superuser else "customer",
        )


def remove_profiles(apps, schema_editor):
    """Reverse step: drop the profiles this migration created.

    It cannot tell which ones it made, so it removes them all; the forward
    migration recreates them with the same rule, and nothing else stores
    data on a profile at this point.
    """
    apps.get_model("accounts", "Profile").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_missing_profiles, remove_profiles),
    ]
