"""Project-level views that do not belong to a single app."""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """GET /healthz/ — a liveness probe for the hosting platform.

    Deliberately does no database work. Render restarts a service whose
    health check fails, and Neon pauses an idle database: a probe that
    waited on a cold database could report the service as dead while it is
    merely waiting, and get it restarted in a loop.

    It is also exempt from the HTTPS redirect (SECURE_REDIRECT_EXEMPT in
    settings), because an internal probe arrives over plain HTTP and would
    otherwise be answered with a 301 rather than a 200.
    """
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request):
    """GET /api/ — an index of the available endpoints."""
    return Response(
        {
            "register": reverse("register", request=request),
            "login": reverse("login", request=request),
            "logout": reverse("logout", request=request),
            "me": reverse("me", request=request),
            "profile": reverse("my-profile", request=request),
            "categories": reverse("category-list", request=request),
            "products": reverse("product-list", request=request),
            "orders": reverse("order-list", request=request),
            # Organization endpoints answer 403 to a customer, but listing
            # them makes the shape of the API discoverable.
            "organization_orders": reverse("org-order-list", request=request),
        }
    )
