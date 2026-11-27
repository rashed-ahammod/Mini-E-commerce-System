"""Tests for organization account provisioning at /api/org/staff/.

The guards are what matter here. Everything else is ordinary CRUD; the
lock-yourself-out cases are the ones that would be discovered at the worst
possible moment.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import Role, profile_for

User = get_user_model()

PASSWORD = "StrongPass!234"


def make(username, role=Role.CUSTOMER, **kwargs):
    user = User.objects.create_user(username, password=PASSWORD, **kwargs)
    profile = profile_for(user)
    profile.role = role
    profile.save()
    return user


class StaffApiTestCase(APITestCase):
    def setUp(self):
        self.admin = make("ada", Role.ADMIN)
        self.admin_token = Token.objects.create(user=self.admin)

        self.second_admin = make("alex", Role.ADMIN)

        self.staff = make("sam", Role.STAFF, email="sam@shop.test")
        self.staff_token = Token.objects.create(user=self.staff)

        self.customer = make("cara", Role.CUSTOMER)
        self.customer_token = Token.objects.create(user=self.customer)

    def as_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

    def as_staff(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.staff_token.key}")

    def as_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.customer_token.key}")

    def detail_url(self, user):
        return reverse("org-staff-detail", args=[user.id])

    def deactivate_url(self, user):
        return reverse("org-staff-deactivate", args=[user.id])

    def activate_url(self, user):
        return reverse("org-staff-activate", args=[user.id])


class AccessTests(StaffApiTestCase):
    def test_anonymous_gets_401(self):
        response = self.client.get(reverse("org-staff-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_customer_gets_403(self):
        self.as_customer()

        response = self.client.get(reverse("org-staff-list"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_cannot_manage_accounts(self):
        """Running the shop and deciding who runs it are different jobs."""
        self.as_staff()

        listed = self.client.get(reverse("org-staff-list"))
        created = self.client.post(
            reverse("org-staff-list"),
            {"username": "new", "password": PASSWORD, "role": "staff"},
            format="json",
        )

        self.assertEqual(listed.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(created.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(username="new").exists())

    def test_an_admin_is_allowed_in(self):
        self.as_admin()

        response = self.client.get(reverse("org-staff-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_a_superuser_is_allowed_in(self):
        root = User.objects.create_superuser("root", password=PASSWORD)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=root).key}"
        )

        response = self.client.get(reverse("org-staff-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ListTests(StaffApiTestCase):
    def test_only_organization_accounts_are_listed(self):
        self.as_admin()

        response = self.client.get(reverse("org-staff-list"))

        usernames = {row["username"] for row in response.data["results"]}
        self.assertEqual(usernames, {"ada", "alex", "sam"})
        self.assertNotIn("cara", usernames)

    def test_superusers_appear_even_without_an_explicit_role(self):
        """The list must agree with who can actually act."""
        User.objects.create_superuser("root", password=PASSWORD)
        self.as_admin()

        response = self.client.get(reverse("org-staff-list"))

        self.assertIn("root", {row["username"] for row in response.data["results"]})

    def test_the_list_never_carries_a_password(self):
        self.as_admin()

        response = self.client.get(reverse("org-staff-list"))

        for row in response.data["results"]:
            self.assertNotIn("password", row)

    def test_filter_by_role(self):
        self.as_admin()

        response = self.client.get(reverse("org-staff-list"), {"profile__role": "staff"})

        self.assertEqual([r["username"] for r in response.data["results"]], ["sam"])


class CreateTests(StaffApiTestCase):
    def test_an_admin_can_add_a_colleague(self):
        self.as_admin()

        response = self.client.post(
            reverse("org-staff-list"),
            {
                "username": "noor",
                "email": "noor@shop.test",
                "password": PASSWORD,
                "role": "staff",
                "department": "Fulfilment",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(username="noor")
        self.assertEqual(created.profile.role, Role.STAFF)
        self.assertEqual(created.profile.department, "Fulfilment")
        self.assertTrue(created.check_password(PASSWORD))

    def test_the_new_account_can_sign_in(self):
        self.as_admin()
        self.client.post(
            reverse("org-staff-list"),
            {"username": "noor", "password": PASSWORD, "role": "staff"},
            format="json",
        )

        self.client.credentials()
        response = self.client.post(
            reverse("login"),
            {"username": "noor", "password": PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["role"], Role.STAFF)
        self.assertTrue(response.data["user"]["is_organization"])

    def test_the_response_never_contains_the_password(self):
        self.as_admin()

        response = self.client.post(
            reverse("org-staff-list"),
            {"username": "noor", "password": PASSWORD, "role": "staff"},
            format="json",
        )

        self.assertNotIn("password", response.data)

    def test_a_weak_password_is_rejected(self):
        self.as_admin()

        response = self.client.post(
            reverse("org-staff-list"),
            {"username": "noor", "password": "123", "role": "staff"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)
        self.assertFalse(User.objects.filter(username="noor").exists())

    def test_a_duplicate_username_is_rejected(self):
        self.as_admin()

        response = self.client.post(
            reverse("org-staff-list"),
            {"username": "SAM", "password": PASSWORD, "role": "staff"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_the_customer_role_cannot_be_granted_here(self):
        """Creating a shopper is what public registration is for."""
        self.as_admin()

        response = self.client.post(
            reverse("org-staff-list"),
            {"username": "noor", "password": PASSWORD, "role": "customer"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_superuser_cannot_be_granted_through_the_api(self):
        self.as_admin()

        self.client.post(
            reverse("org-staff-list"),
            {
                "username": "noor",
                "password": PASSWORD,
                "role": "admin",
                "is_superuser": True,
                "is_staff": True,
            },
            format="json",
        )

        created = User.objects.get(username="noor")
        self.assertFalse(created.is_superuser)
        self.assertFalse(created.is_staff)


class UpdateTests(StaffApiTestCase):
    def test_an_admin_can_promote_a_colleague(self):
        self.as_admin()

        response = self.client.patch(
            self.detail_url(self.staff), {"role": "admin"}, format="json"
        )

        self.staff.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.staff.profile.role, Role.ADMIN)

    def test_details_can_be_updated(self):
        self.as_admin()

        response = self.client.patch(
            self.detail_url(self.staff),
            {"department": "Returns", "phone": "0100000000"},
            format="json",
        )

        self.staff.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.staff.profile.department, "Returns")

    def test_access_can_be_revoked_by_setting_the_customer_role(self):
        self.as_admin()

        self.client.patch(self.detail_url(self.staff), {"role": "customer"}, format="json")

        self.staff.refresh_from_db()
        self.assertFalse(self.staff.profile.is_organization)

    def test_an_admin_cannot_change_their_own_role(self):
        """An accidental self-demotion would end access mid-session."""
        self.as_admin()

        response = self.client.patch(
            self.detail_url(self.admin), {"role": "staff"}, format="json"
        )

        self.admin.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.admin.profile.role, Role.ADMIN)

    def test_an_admin_may_edit_their_own_details(self):
        """Only the role is off limits."""
        self.as_admin()

        response = self.client.patch(
            self.detail_url(self.admin), {"department": "Head office"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_passwords_cannot_be_set_through_this_endpoint(self):
        self.as_admin()
        original = self.staff.password

        self.client.patch(
            self.detail_url(self.staff), {"password": "NewPass!2026"}, format="json"
        )

        self.staff.refresh_from_db()
        self.assertEqual(self.staff.password, original)


class LockoutGuardTests(StaffApiTestCase):
    """The rules that keep a shop from becoming unadministrable.

    Only the self-guards are reachable over HTTP: the caller is always an
    admin, so acting on anyone else leaves the caller holding the role. The
    last-admin backstop is therefore exercised directly below rather than
    through a request that could never reach it.
    """

    def test_an_admin_cannot_demote_themselves(self):
        self.as_admin()

        response = self.client.patch(
            self.detail_url(self.admin), {"role": "staff"}, format="json"
        )

        self.admin.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("your own role", str(response.data["role"]))
        self.assertEqual(self.admin.profile.role, Role.ADMIN)

    def test_an_admin_cannot_deactivate_themselves(self):
        self.as_admin()

        response = self.client.post(
            self.deactivate_url(self.admin), {"reason": "oops"}, format="json"
        )

        self.admin.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("your own account", str(response.data["detail"]))
        self.assertTrue(self.admin.is_active)

    def test_another_admin_can_still_be_demoted(self):
        """The guards must not block ordinary, safe changes."""
        self.as_admin()

        response = self.client.patch(
            self.detail_url(self.second_admin), {"role": "staff"}, format="json"
        )

        self.second_admin.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.second_admin.profile.role, Role.STAFF)

    def test_the_backstop_recognises_the_only_admin(self):
        """Unit test of the check itself, since HTTP cannot reach it."""
        from organization.views import OrgStaffViewSet

        self.second_admin.delete()  # `ada` is now the only admin
        view = OrgStaffViewSet()
        view.request = type("R", (), {"user": self.admin})()

        self.assertTrue(view._would_remove_the_last_admin(self.admin))

    def test_the_backstop_allows_it_when_another_admin_remains(self):
        from organization.views import OrgStaffViewSet

        view = OrgStaffViewSet()
        view.request = type("R", (), {"user": self.admin})()

        # `alex` is also an admin, so removing `ada` is safe.
        self.assertFalse(view._would_remove_the_last_admin(self.admin))

    def test_the_backstop_ignores_inactive_admins(self):
        """A suspended admin cannot grant anyone access."""
        from organization.views import OrgStaffViewSet

        self.second_admin.is_active = False
        self.second_admin.save()
        view = OrgStaffViewSet()
        view.request = type("R", (), {"user": self.admin})()

        self.assertTrue(view._would_remove_the_last_admin(self.admin))


class DeactivationTests(StaffApiTestCase):
    def test_deactivating_revokes_access(self):
        self.as_admin()

        response = self.client.post(
            self.deactivate_url(self.staff), {"reason": "left the company"},
            format="json",
        )

        self.staff.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(self.staff.is_active)

    def test_their_token_stops_working(self):
        self.as_admin()
        self.client.post(
            self.deactivate_url(self.staff), {"reason": "left"}, format="json"
        )

        self.as_staff()
        response = self.client.get(reverse("me"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_you_cannot_deactivate_yourself(self):
        self.as_admin()

        response = self.client.post(
            self.deactivate_url(self.admin), {"reason": "oops"}, format="json"
        )

        self.admin.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(self.admin.is_active)

    def test_a_reason_is_required(self):
        self.as_admin()

        response = self.client.post(self.deactivate_url(self.staff), {}, format="json")

        self.staff.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(self.staff.is_active)

    def test_reactivating_restores_access(self):
        self.as_admin()
        self.client.post(
            self.deactivate_url(self.staff), {"reason": "suspended"}, format="json"
        )

        response = self.client.post(self.activate_url(self.staff), {}, format="json")

        self.staff.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(self.staff.is_active)


class NoDeleteTests(StaffApiTestCase):
    def test_accounts_cannot_be_deleted(self):
        """They own order history that should keep their name on it."""
        self.as_admin()

        response = self.client.delete(self.detail_url(self.staff))

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(User.objects.filter(pk=self.staff.pk).exists())
