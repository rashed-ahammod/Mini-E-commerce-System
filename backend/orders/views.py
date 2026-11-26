"""API views for orders.

Orders are private: every endpoint requires a token, and a user can only
ever see their own orders. Only create / list / retrieve are exposed, which
is exactly what the assignment asks for — an order is a record of something
that happened, so it is not editable or deletable through the API.
"""

from rest_framework import mixins, permissions, viewsets

from .models import Order
from .serializers import OrderSerializer


class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Order endpoints.

        POST /api/orders/        place an order {product_id, quantity}
        GET  /api/orders/        the caller's orders, newest first (paginated)
        GET  /api/orders/{id}/   one of the caller's orders
    """

    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    ordering_fields = ["created_at", "total_price"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # Filtering by the logged-in user here is what makes another user's
        # order invisible: /api/orders/{someone elses id}/ returns 404, not
        # 403, so order ids are not leaked either.
        return (
            Order.objects.filter(user=self.request.user)
            .select_related("product", "user")
        )
