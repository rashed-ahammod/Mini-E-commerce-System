"""Tests for the project-level endpoints: the API index and the health probe.

The health check in particular has a requirement that is easy to break by
accident: it must answer 200 to a plain HTTP request. The hosting platform
probes the container directly, without the X-Forwarded-Proto header that
public traffic carries, so if the HTTPS redirect applied to it the platform
would see a 301, decide the service is unhealthy and restart it.
"""

from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework import status


class ApiRootTests(SimpleTestCase):
    def test_api_root_lists_the_endpoints(self):
        response = self.client.get(reverse("api-root"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in (
            "register",
            "login",
            "logout",
            "me",
            "categories",
            "products",
            "orders",
        ):
            self.assertIn(key, response.data)

    def test_api_root_is_public(self):
        """It is the first URL anyone tries, so it must not need a token."""
        response = self.client.get(reverse("api-root"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class HealthCheckTests(SimpleTestCase):
    def test_health_check_is_public_and_ok(self):
        response = self.client.get(reverse("health-check"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"status": "ok"})

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_REDIRECT_EXEMPT=[r"^healthz/?$"],
    )
    def test_health_check_answers_plain_http_without_redirecting(self):
        """What the platform's internal probe actually does."""
        response = self.client.get(reverse("health-check"), secure=False)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_REDIRECT_EXEMPT=[r"^healthz/?$"],
    )
    def test_other_urls_are_still_redirected_to_https(self):
        """The exemption must cover the probe and nothing else."""
        response = self.client.get(reverse("api-root"), secure=False)

        self.assertEqual(response.status_code, status.HTTP_301_MOVED_PERMANENTLY)
        self.assertTrue(response["Location"].startswith("https://"))
