"""Organization-facing views, mounted at /api/org/.

Every view here requires an organization account. Customers receive 403,
anonymous callers 401 — the distinction matters: one says "not you", the
other says "log in first".
"""

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsOrganizationUser
from orders.models import InvalidTransition, Order, OrderStatus

from .dashboard import build_dashboard
from .filters import OrgOrderFilter
from .serializers import (
    DashboardQuerySerializer,
    OrderCancelSerializer,
    OrderStatusUpdateSerializer,
    OrgOrderDetailSerializer,
    OrgOrderListSerializer,
    TransitionRulesSerializer,
)


class DashboardView(APIView):
    """GET /api/org/dashboard/ — the state of the shop in one request.

        ?days=7                  narrow the trend window (1-365, default 30)
        ?low_stock_threshold=10  what counts as running low (default 5)

    Everything is aggregated by the database, so the cost does not grow with
    the number of orders. See organization/dashboard.py for what each figure
    means — in particular, "booked" and "realised" revenue answer different
    questions and cancelled orders are excluded from both.
    """

    permission_classes = [IsOrganizationUser]

    def get(self, request):
        query = DashboardQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        return Response(
            build_dashboard(
                days=query.validated_data["days"],
                low_stock_threshold=query.validated_data["low_stock_threshold"],
            )
        )


class OrgOrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Every customer's orders, and the actions that move them along.

        GET  /api/org/orders/                  all orders (filter/search/sort)
        GET  /api/org/orders/{id}/             one order with its history
        POST /api/org/orders/{id}/status/      advance the status
        POST /api/org/orders/{id}/cancel/      cancel and return the stock
        GET  /api/org/orders/statuses/         the workflow itself

    There is no create, update or delete. Orders are placed by customers and
    changed only through the two actions above, so every change is a valid
    transition and leaves a record in the order's history. Editing an order
    row directly would let a total silently disagree with its quantity.
    """

    permission_classes = [IsOrganizationUser]
    filterset_class = OrgOrderFilter
    search_fields = ["product__name", "user__username", "user__email"]
    ordering_fields = ["created_at", "total_price", "status", "status_updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # Unlike the customer's OrderViewSet this is NOT filtered by user:
        # seeing every order is the whole point of the organization view.
        return (
            Order.objects.select_related("user", "product", "product__category")
            .prefetch_related("events", "events__changed_by")
            .all()
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return OrgOrderDetailSerializer
        return OrgOrderListSerializer

    def _detail_response(self, order):
        """Always answer an action with the full order, so the client can
        re-render from the response instead of re-fetching."""
        order.refresh_from_db()
        return Response(
            OrgOrderDetailSerializer(order, context=self.get_serializer_context()).data
        )

    @action(detail=False, methods=["get"])
    def statuses(self, request):
        """GET /api/org/orders/statuses/ — the status workflow, described.

        Lets a client build the UI from the server's rules rather than
        hard-coding a copy of them that can drift.
        """
        return Response(TransitionRulesSerializer.describe_workflow())

    @action(detail=True, methods=["post"])
    def status(self, request, pk=None):
        """POST /api/org/orders/{id}/status/ {"status": ..., "note": ...}"""
        order = self.get_object()
        serializer = OrderStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target = serializer.validated_data["status"]
        note = serializer.validated_data.get("note", "")

        if target == OrderStatus.CANCELLED and not note:
            # Cancelling has consequences — stock returns, a customer is
            # disappointed — so it goes through the cancel action, which
            # insists on a reason.
            return Response(
                {"status": ["Use the cancel action to cancel an order."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order.transition_to(target, changed_by=request.user, note=note)
        except InvalidTransition as error:
            return Response(
                {"status": [str(error)]}, status=status.HTTP_400_BAD_REQUEST
            )

        return self._detail_response(order)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """POST /api/org/orders/{id}/cancel/ {"reason": "..."}

        Returns the ordered units to the product. An order that has already
        shipped cannot be cancelled: that needs a returns process, with its
        own refund and restocking rules.
        """
        order = self.get_object()
        serializer = OrderCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order.transition_to(
                OrderStatus.CANCELLED,
                changed_by=request.user,
                note=serializer.validated_data["reason"],
            )
        except InvalidTransition as error:
            return Response(
                {"status": [str(error)]}, status=status.HTTP_400_BAD_REQUEST
            )

        return self._detail_response(order)
