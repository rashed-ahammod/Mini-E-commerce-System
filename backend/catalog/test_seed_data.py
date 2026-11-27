"""Tests for the `seed_data --demo-user` accounts.

These two logins are printed on the login page, so that anyone reviewing the
project can see both halves of it. That makes them a published promise: if
the seed stops creating them, or the staff account quietly loses its role,
the page goes on advertising credentials that no longer work.

The catalog itself is not re-tested here — the command's own output covers
it — only the accounts and the privileges they carry.
"""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role

from .management.commands.seed_data import (
    DEMO_PASSWORD,
    DEMO_USERNAME,
    STAFF_PASSWORD,
    STAFF_USERNAME,
)

User = get_user_model()


def seed():
    call_command("seed_data", "--demo-user", stdout=StringIO())


class DemoAccountTests(TestCase):
    def setUp(self):
        seed()

    def test_both_published_accounts_exist(self):
        self.assertTrue(User.objects.filter(username=DEMO_USERNAME).exists())
        self.assertTrue(User.objects.filter(username=STAFF_USERNAME).exists())

    def test_the_published_passwords_are_the_ones_that_work(self):
        self.assertTrue(
            User.objects.get(username=DEMO_USERNAME).check_password(DEMO_PASSWORD)
        )
        self.assertTrue(
            User.objects.get(username=STAFF_USERNAME).check_password(STAFF_PASSWORD)
        )

    def test_the_staff_account_can_reach_the_console_but_not_accounts(self):
        """Staff, not admin — which is what the login page claims it is."""
        profile = User.objects.get(username=STAFF_USERNAME).profile

        self.assertEqual(profile.role, Role.STAFF)
        self.assertTrue(profile.is_organization)
        self.assertFalse(profile.is_organization_admin)

    def test_the_demo_customer_is_only_a_customer(self):
        profile = User.objects.get(username=DEMO_USERNAME).profile

        self.assertEqual(profile.role, Role.CUSTOMER)
        self.assertFalse(profile.is_organization)

    def test_both_accounts_can_actually_order(self):
        """Email, phone and address are required before checkout."""
        for username in (DEMO_USERNAME, STAFF_USERNAME):
            with self.subTest(username=username):
                profile = User.objects.get(username=username).profile
                self.assertTrue(
                    profile.is_complete,
                    f"{username} is missing {profile.missing_details}",
                )

    def test_running_it_again_resets_rather_than_duplicates(self):
        """The seed runs on every deploy with SEED_DATA=true."""
        staff = User.objects.get(username=STAFF_USERNAME)
        staff.set_password("something-else-entirely")
        staff.profile.role = Role.CUSTOMER
        staff.profile.save()
        staff.save()

        seed()

        staff.refresh_from_db()
        staff.profile.refresh_from_db()
        self.assertEqual(User.objects.filter(username=STAFF_USERNAME).count(), 1)
        self.assertTrue(staff.check_password(STAFF_PASSWORD))
        # The role is forced back: a demo account someone had promoted (or
        # demoted) must not decide what the next visitor gets.
        self.assertEqual(staff.profile.role, Role.STAFF)


class DemoAccountLoginTests(APITestCase):
    """The credentials work through the API the login page actually calls."""

    def setUp(self):
        seed()

    def test_the_staff_login_reports_organization_access(self):
        response = self.client.post(
            reverse("login"),
            {"username": STAFF_USERNAME, "password": STAFF_PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # This is what sends the frontend to /org rather than the shop.
        self.assertTrue(response.data["user"]["is_organization"])
        self.assertEqual(response.data["user"]["role"], Role.STAFF)

    def test_the_customer_login_does_not(self):
        response = self.client.post(
            reverse("login"),
            {"username": DEMO_USERNAME, "password": DEMO_PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["user"]["is_organization"])

    def test_the_staff_account_is_refused_the_admin_only_endpoints(self):
        token = self.client.post(
            reverse("login"),
            {"username": STAFF_USERNAME, "password": STAFF_PASSWORD},
            format="json",
        ).data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")

        listed = self.client.get(reverse("org-staff-list"))

        self.assertEqual(listed.status_code, status.HTTP_403_FORBIDDEN)
