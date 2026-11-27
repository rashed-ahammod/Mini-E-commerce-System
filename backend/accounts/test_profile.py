"""Tests for /api/auth/profile/ — the account's own details.

Email, phone and address are required of every account, because an order has
to reach a real person at a real address. The two things worth proving here
are that the requirement cannot be undone once met, and that the endpoint
only ever touches the account the token belongs to — there is no id in the
URL, so there must be no way to aim it at someone else.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

User = get_user_model()

PASSWORD = "StrongPass!234"
PHONE = "+880 1711 123456"
ADDRESS = "House 12, Road 5, Dhanmondi, Dhaka 1205"


class ProfileTestCase(APITestCase):
    url = reverse("my-profile")

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", email="alice@example.com", password=PASSWORD
        )
        profile = self.user.profile
        profile.phone = PHONE
        profile.address = ADDRESS
        profile.save()

        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")


class ReadProfileTests(ProfileTestCase):
    def test_a_token_is_required(self):
        self.client.credentials()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_the_token_owners_details_as_one_flat_object(self):
        """Email lives on User and the rest on Profile; the client sees one."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "alice")
        self.assertEqual(response.data["email"], "alice@example.com")
        self.assertEqual(response.data["phone"], PHONE)
        self.assertEqual(response.data["address"], ADDRESS)
        self.assertTrue(response.data["profile_complete"])
        self.assertEqual(response.data["missing_details"], [])

    def test_says_what_is_missing(self):
        """So the shop can ask for it, rather than failing at checkout."""
        profile = self.user.profile
        profile.phone = ""
        profile.address = ""
        profile.save()

        response = self.client.get(self.url)

        self.assertFalse(response.data["profile_complete"])
        self.assertCountEqual(response.data["missing_details"], ["phone", "address"])

    def test_never_includes_the_password(self):
        response = self.client.get(self.url)

        self.assertNotIn("password", response.data)


class UpdateProfileTests(ProfileTestCase):
    def test_details_can_be_changed(self):
        response = self.client.patch(
            self.url,
            {
                "email": "new@example.com",
                "phone": "+880 1999 888777",
                "address": "Plot 7, Sector 11, Uttara, Dhaka 1230",
                "first_name": "Alice",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.com")
        self.assertEqual(self.user.first_name, "Alice")
        self.assertEqual(self.user.profile.phone, "+880 1999 888777")
        self.assertEqual(
            self.user.profile.address, "Plot 7, Sector 11, Uttara, Dhaka 1230"
        )

    def test_a_partial_update_leaves_the_other_fields_alone(self):
        response = self.client.patch(self.url, {"phone": "+880 1999 888777"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "alice@example.com")
        self.assertEqual(self.user.profile.address, ADDRESS)

    def test_required_details_cannot_be_blanked(self):
        """The requirement would be worthless if a PATCH could undo it."""
        for field in ("email", "phone", "address"):
            with self.subTest(field=field):
                response = self.client.patch(self.url, {field: ""}, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.address, ADDRESS)

    def test_an_unusable_phone_or_address_is_refused(self):
        response = self.client.patch(
            self.url, {"phone": "12", "address": "home"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", response.data)
        self.assertIn("address", response.data)

    def test_an_email_already_in_use_is_refused(self):
        User.objects.create_user("bob", email="bob@example.com", password=PASSWORD)

        response = self.client.patch(
            self.url, {"email": "BOB@example.com"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_keeping_your_own_email_is_not_a_duplicate(self):
        """The uniqueness check must not trip over the account itself."""
        response = self.client.patch(
            self.url, {"email": "alice@example.com", "phone": PHONE}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_the_username_cannot_be_changed(self):
        """Orders are recorded against it, so it is read-only."""
        response = self.client.patch(self.url, {"username": "someone"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "alice")

    def test_the_role_cannot_be_escalated(self):
        """`role` is reported back, but it is not an input."""
        response = self.client.patch(self.url, {"role": "admin"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.role, "customer")
        self.assertFalse(self.user.profile.is_organization)

    def test_it_only_ever_writes_to_the_token_owner(self):
        """There is no id in the URL, and no field that stands in for one."""
        bob = User.objects.create_user("bob", email="bob@example.com", password=PASSWORD)

        response = self.client.patch(
            self.url,
            {"id": bob.id, "user": bob.id, "username": "bob", "phone": "+880 1555 444333"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        bob.refresh_from_db()
        bob.profile.refresh_from_db()
        self.assertEqual(bob.email, "bob@example.com")
        self.assertEqual(bob.profile.phone, "")
        # The caller's own number is what changed.
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.phone, "+880 1555 444333")

    def test_completing_a_profile_flips_it_to_ready(self):
        profile = self.user.profile
        profile.phone = ""
        profile.address = ""
        profile.save()

        response = self.client.patch(
            self.url, {"phone": PHONE, "address": ADDRESS}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["profile_complete"])
        self.assertEqual(response.data["missing_details"], [])

    def test_whitespace_is_trimmed(self):
        """So " " never counts as an address that was filled in."""
        response = self.client.patch(
            self.url, {"address": f"  {ADDRESS}  "}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.address, ADDRESS)
