"""Tests for registration, login, logout and the current-user endpoint."""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

User = get_user_model()

VALID_PASSWORD = "StrongPass!234"

# Registration requires contact details, so every test that expects a
# *successful* sign-up starts from this and overrides what it is testing.
VALID_REGISTRATION = {
    "username": "alice",
    "email": "alice@example.com",
    "phone": "+880 1711 123456",
    "address": "House 12, Road 5, Dhanmondi, Dhaka 1205",
    "password": VALID_PASSWORD,
}


def registration(**overrides):
    """A valid registration payload with `overrides` applied.

    A key set to None is removed, which is how the tests below say "send
    this request without that field".
    """
    payload = {**VALID_REGISTRATION, **overrides}
    return {key: value for key, value in payload.items() if value is not None}


class RegisterTests(APITestCase):
    url = reverse("register")

    def test_register_creates_user_and_returns_token(self):
        response = self.client.post(self.url, registration(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", response.data)
        self.assertEqual(response.data["user"]["username"], "alice")

        user = User.objects.get(username="alice")
        # The password must be hashed, never stored as given.
        self.assertNotEqual(user.password, VALID_PASSWORD)
        self.assertTrue(user.check_password(VALID_PASSWORD))
        self.assertTrue(Token.objects.filter(user=user).exists())

    def test_contact_details_are_stored_on_the_profile(self):
        """Sign-up leaves an account that can order straight away."""
        response = self.client.post(self.url, registration(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # No second request needed to discover the profile is usable.
        self.assertTrue(response.data["user"]["profile_complete"])
        self.assertEqual(response.data["user"]["missing_details"], [])

        profile = User.objects.get(username="alice").profile
        self.assertEqual(profile.phone, VALID_REGISTRATION["phone"])
        self.assertEqual(profile.address, VALID_REGISTRATION["address"])
        self.assertTrue(profile.is_complete)

    def test_response_never_contains_the_password(self):
        response = self.client.post(self.url, registration(), format="json")

        self.assertNotIn("password", response.data)
        self.assertNotIn("password", response.data["user"])

    def test_weak_password_is_rejected(self):
        response = self.client.post(
            self.url, registration(password="123"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)
        self.assertFalse(User.objects.filter(username="alice").exists())

    def test_duplicate_username_is_rejected_case_insensitively(self):
        User.objects.create_user("alice", password=VALID_PASSWORD)

        response = self.client.post(
            self.url, registration(username="ALICE"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_contact_details_are_required(self):
        """Each of the three is refused by name, so a form can point at it."""
        for field in ("email", "phone", "address"):
            with self.subTest(field=field):
                response = self.client.post(
                    self.url, registration(**{field: None}), format="json"
                )

                self.assertEqual(
                    response.status_code, status.HTTP_400_BAD_REQUEST
                )
                self.assertIn(field, response.data)
                self.assertFalse(User.objects.filter(username="alice").exists())

    def test_blank_contact_details_are_refused(self):
        """Sending the field empty is no different from leaving it out."""
        for field in ("email", "phone", "address"):
            with self.subTest(field=field):
                response = self.client.post(
                    self.url, registration(**{field: ""}), format="json"
                )

                self.assertEqual(
                    response.status_code, status.HTTP_400_BAD_REQUEST
                )
                self.assertIn(field, response.data)

    def test_unusable_phone_and_address_are_refused(self):
        """The point of requiring them is that an order can be delivered."""
        response = self.client.post(
            self.url, registration(phone="12", address="home"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", response.data)
        self.assertIn("address", response.data)
        self.assertFalse(User.objects.filter(username="alice").exists())

    def test_duplicate_email_is_rejected_case_insensitively(self):
        """One account per email, so a reset is never ambiguous."""
        self.client.post(self.url, registration(), format="json")

        response = self.client.post(
            self.url,
            registration(username="bob", email="ALICE@example.com"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.assertFalse(User.objects.filter(username="bob").exists())


class LoginTests(APITestCase):
    url = reverse("login")

    def setUp(self):
        self.user = User.objects.create_user("alice", password=VALID_PASSWORD)

    def test_login_returns_a_token(self):
        response = self.client.post(
            self.url,
            {"username": "alice", "password": VALID_PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["token"], Token.objects.get(user=self.user).key)

    def test_wrong_password_and_unknown_user_give_the_same_message(self):
        """So the endpoint cannot be used to discover which usernames exist."""
        wrong_password = self.client.post(
            self.url, {"username": "alice", "password": "nope"}, format="json"
        )
        unknown_user = self.client.post(
            self.url, {"username": "nobody", "password": "nope"}, format="json"
        )

        self.assertEqual(wrong_password.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(unknown_user.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(wrong_password.data, unknown_user.data)

    def test_inactive_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save()

        response = self.client.post(
            self.url,
            {"username": "alice", "password": VALID_PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MeAndLogoutTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password=VALID_PASSWORD)
        self.token = Token.objects.create(user=self.user)

    def authenticate(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_me_requires_a_token(self):
        response = self.client.get(reverse("me"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_the_token_owner(self):
        self.authenticate()

        response = self.client.get(reverse("me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "alice")

    def test_logout_invalidates_the_token(self):
        self.authenticate()

        logout = self.client.post(reverse("logout"))
        reused = self.client.get(reverse("me"))

        self.assertEqual(logout.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(reused.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Token.objects.filter(user=self.user).exists())

    def test_an_invalid_token_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token not-a-real-token")

        response = self.client.get(reverse("me"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
