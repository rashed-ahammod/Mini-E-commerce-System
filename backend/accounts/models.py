"""User roles.

The project has two kinds of people in it:

* **customers**, who browse the shop and place their own orders;
* **organization users**, who run the shop — they see every order, move it
  through its lifecycle, and manage the catalog.

Rather than a second user table (which would mean two login flows, two
password reset paths and a foreign key on Order that could point at either),
both are ordinary Django users with a `Profile` that records which role they
hold. One account is one person; the role decides what they may do.

`Profile.role` is independent of Django's `is_staff` / `is_superuser`, which
control access to the Django admin site rather than to this API. A superuser
is nevertheless treated as an organization admin, so the person who owns the
server is never locked out of it.
"""

from django.conf import settings
from django.db import models


class Role(models.TextChoices):
    CUSTOMER = "customer", "Customer"
    STAFF = "staff", "Organization staff"
    ADMIN = "admin", "Organization admin"


class Profile(models.Model):
    """Extra fields hung off Django's User, created automatically with it."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
        help_text="What this account is allowed to do in the API.",
    )
    # Contact details. Blank at the database level because a Profile is
    # created by a signal the moment a User exists — before anyone has had
    # the chance to type anything. What makes them *required* is the
    # serializer that owns them (accounts.serializers.MyProfileSerializer),
    # plus `is_complete` below, which the UI uses to ask for what is missing.
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(
        blank=True,
        help_text="Where this person's orders are delivered by default.",
    )
    # Free text so a shop can record which desk or branch someone works at.
    department = models.CharField(
        max_length=100,
        blank=True,
        help_text="Only meaningful for organization users.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self) -> str:
        return f"{self.user.username} ({self.get_role_display()})"

    # -- role questions ---------------------------------------------------
    # Asked often enough, and in enough places, to be worth naming once.

    @property
    def is_organization(self) -> bool:
        """May use the organization endpoints at all."""
        return self.role in {Role.STAFF, Role.ADMIN} or self.user.is_superuser

    @property
    def is_organization_admin(self) -> bool:
        """May additionally create and manage other organization accounts."""
        return self.role == Role.ADMIN or self.user.is_superuser

    @property
    def is_customer(self) -> bool:
        return not self.is_organization

    # -- completeness -----------------------------------------------------

    @property
    def missing_details(self) -> list[str]:
        """Which of the required contact details are still empty.

        An order has to reach a real person at a real address, so email,
        phone and address are all required of a customer before checkout.
        Returning the field names — rather than a bare boolean — lets the
        shop say exactly what it still needs.
        """
        missing = []
        if not (self.user.email or "").strip():
            missing.append("email")
        if not self.phone.strip():
            missing.append("phone")
        if not self.address.strip():
            missing.append("address")
        return missing

    @property
    def is_complete(self) -> bool:
        return not self.missing_details


def profile_for(user):
    """The profile of `user`, creating it if it is somehow missing.

    Profiles are created by a signal whenever a user is created, but a user
    made before this app existed — or by a fixture that bypasses signals —
    would otherwise raise `Profile.DoesNotExist` deep inside a permission
    check. This keeps that from ever being a 500.
    """
    if user is None or not user.is_authenticated:
        return None
    profile = getattr(user, "profile", None)
    if profile is None:
        profile, _ = Profile.objects.get_or_create(user=user)
    return profile
