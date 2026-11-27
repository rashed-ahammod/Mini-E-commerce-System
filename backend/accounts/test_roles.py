"""Tests for roles, profiles and the organization permission classes.

The security-relevant claims are the ones to read first: a customer cannot
become an organization user by registering, and a superuser is always
treated as an organization admin so the server owner cannot be locked out.
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Profile, Role, profile_for
from .permissions import (
    IsOrganizationAdmin,
    IsOrganizationUser,
    IsOrganizationUserOrReadOnly,
)

User = get_user_model()

PASSWORD = "StrongPass!234"


def make_user(username, role=Role.CUSTOMER, **kwargs):
    user = User.objects.create_user(username, password=PASSWORD, **kwargs)
    profile = profile_for(user)
    profile.role = role
    profile.save()
    return user


class ProfileCreationTests(TestCase):
    def test_a_profile_is_created_with_every_user(self):
        user = User.objects.create_user("alice", password=PASSWORD)

        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_new_users_are_customers_by_default(self):
        user = User.objects.create_user("alice", password=PASSWORD)

        self.assertEqual(user.profile.role, Role.CUSTOMER)
        self.assertTrue(user.profile.is_customer)
        self.assertFalse(user.profile.is_organization)

    def test_profile_for_creates_a_missing_profile(self):
        """A user made before this app existed must not cause a 500."""
        user = User.objects.create_user("alice", password=PASSWORD)
        Profile.objects.filter(user=user).delete()
        user.refresh_from_db()

        profile = profile_for(user)

        self.assertIsNotNone(profile)
        self.assertEqual(profile.role, Role.CUSTOMER)

    def test_superuser_counts_as_an_organization_admin(self):
        """So whoever owns the server is never locked out of it."""
        user = User.objects.create_superuser("root", password=PASSWORD)

        self.assertTrue(user.profile.is_organization)
        self.assertTrue(user.profile.is_organization_admin)


class RoleCapabilityTests(TestCase):
    def test_staff_is_an_organization_user_but_not_an_admin(self):
        user = make_user("sam", Role.STAFF)

        self.assertTrue(user.profile.is_organization)
        self.assertFalse(user.profile.is_organization_admin)

    def test_admin_is_both(self):
        user = make_user("ada", Role.ADMIN)

        self.assertTrue(user.profile.is_organization)
        self.assertTrue(user.profile.is_organization_admin)


class PermissionClassTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.customer = make_user("cara", Role.CUSTOMER)
        self.staff = make_user("sam", Role.STAFF)
        self.admin = make_user("ada", Role.ADMIN)

    def request_as(self, user, method="get"):
        request = getattr(self.factory, method)("/")
        request.user = user
        return request

    def test_is_organization_user(self):
        permission = IsOrganizationUser()

        self.assertFalse(permission.has_permission(self.request_as(self.customer), None))
        self.assertTrue(permission.has_permission(self.request_as(self.staff), None))
        self.assertTrue(permission.has_permission(self.request_as(self.admin), None))

    def test_is_organization_admin(self):
        permission = IsOrganizationAdmin()

        self.assertFalse(permission.has_permission(self.request_as(self.customer), None))
        self.assertFalse(permission.has_permission(self.request_as(self.staff), None))
        self.assertTrue(permission.has_permission(self.request_as(self.admin), None))

    def test_read_only_permission_lets_anyone_read(self):
        permission = IsOrganizationUserOrReadOnly()

        self.assertTrue(permission.has_permission(self.request_as(self.customer), None))

    def test_read_only_permission_blocks_customer_writes(self):
        permission = IsOrganizationUserOrReadOnly()

        self.assertFalse(
            permission.has_permission(self.request_as(self.customer, "post"), None)
        )
        self.assertTrue(
            permission.has_permission(self.request_as(self.staff, "post"), None)
        )

    def test_anonymous_users_are_not_organization_users(self):
        from django.contrib.auth.models import AnonymousUser

        permission = IsOrganizationUser()

        self.assertFalse(
            permission.has_permission(self.request_as(AnonymousUser()), None)
        )


class RoleInAuthResponsesTests(APITestCase):
    def test_login_reports_the_role(self):
        make_user("sam", Role.STAFF)

        response = self.client.post(
            reverse("login"),
            {"username": "sam", "password": PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["role"], Role.STAFF)
        self.assertTrue(response.data["user"]["is_organization"])

    def test_me_reports_the_role(self):
        user = make_user("cara", Role.CUSTOMER)
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.get(reverse("me"))

        self.assertEqual(response.data["role"], Role.CUSTOMER)
        self.assertFalse(response.data["is_organization"])

    def test_public_registration_always_creates_a_customer(self):
        """Even when the request tries to ask for something else."""
        response = self.client.post(
            reverse("register"),
            {
                "username": "sneaky",
                "email": "sneaky@example.com",
                "phone": "+880 1711 123456",
                "address": "House 12, Road 5, Dhanmondi, Dhaka 1205",
                "password": PASSWORD,
                "role": Role.ADMIN,
                "is_organization": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["role"], Role.CUSTOMER)
        self.assertFalse(response.data["user"]["is_organization"])
        self.assertEqual(User.objects.get(username="sneaky").profile.role, Role.CUSTOMER)

    def test_superuser_reports_the_admin_role(self):
        user = User.objects.create_superuser("root", password=PASSWORD)
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.get(reverse("me"))

        self.assertEqual(response.data["role"], Role.ADMIN)
        self.assertTrue(response.data["is_organization"])


class CreateOrgUserCommandTests(TestCase):
    def test_creates_a_staff_account(self):
        call_command("create_org_user", "sam", role="staff", password=PASSWORD)

        user = User.objects.get(username="sam")
        self.assertEqual(user.profile.role, Role.STAFF)
        self.assertTrue(user.check_password(PASSWORD))

    def test_creates_an_admin_account(self):
        call_command(
            "create_org_user", "ada", role="admin", password=PASSWORD,
            department="Operations",
        )

        profile = User.objects.get(username="ada").profile
        self.assertEqual(profile.role, Role.ADMIN)
        self.assertEqual(profile.department, "Operations")

    def test_refuses_an_existing_username_without_promote(self):
        make_user("sam")

        with self.assertRaises(CommandError):
            call_command("create_org_user", "sam", role="staff", password=PASSWORD)

    def test_promote_changes_an_existing_users_role(self):
        make_user("cara", Role.CUSTOMER)

        call_command("create_org_user", "cara", role="admin", promote=True)

        self.assertEqual(User.objects.get(username="cara").profile.role, Role.ADMIN)

    def test_rejects_a_weak_password(self):
        with self.assertRaises(CommandError):
            call_command("create_org_user", "sam", role="staff", password="123")

        self.assertFalse(User.objects.filter(username="sam").exists())
