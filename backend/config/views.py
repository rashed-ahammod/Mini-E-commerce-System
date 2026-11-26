"""Project-level views that do not belong to a single app."""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse


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
            "categories": reverse("category-list", request=request),
            "products": reverse("product-list", request=request),
            "orders": reverse("order-list", request=request),
        }
    )
