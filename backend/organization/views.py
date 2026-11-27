"""Organization-facing views, mounted at /api/org/.

Every view here requires an organization account. Customers receive 403,
anonymous callers 401 — the distinction matters: one says "not you", the
other says "log in first".
"""

from django.contrib.auth import get_user_model
from django.db.models import Count, DecimalField, Max, Q, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import mixins, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from accounts.permissions import IsOrganizationUser
from orders.models import InvalidTransition, Order, OrderStatus

from .dashboard import build_dashboard
from .filters import CustomerFilter, OrgOrderFilter
from .serializers import (
    CustomerDetailSerializer,
    CustomerListSerializer,
    CustomerStatusSerializer,
    DashboardQuerySerializer,
    OrderCancelSerializer,
    OrderStatusUpdateSerializer,
    OrgOrderDetailSerializer,
    OrgOrderListSerializer,
    TransitionRulesSerializer,
)

User = get_user_model()


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


class OrgCustomerViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """The shop's customers.

        GET  /api/org/customers/                 list, with spend and counts
        GET  /api/org/customers/{id}/            one customer and their orders
        POST /api/org/customers/{id}/deactivate/ block them from signing in
        POST /api/org/customers/{id}/activate/   let them back in

    Read and suspend only: there is no create, no edit and no delete.

    * Creating accounts is the customer's own business (public registration)
      or, for organization accounts, an organization admin's.
    * Deleting a customer would cascade to their orders and destroy the
      sales history, so an unwanted account is deactivated instead.
    * Nothing here can change a password or read one; support resets go
      through the usual reset flow, not through staff.

    Organization accounts are not customers and are deliberately absent, so
    this endpoint cannot be used to suspend a colleague — or yourself.
    """

    permission_classes = [IsOrganizationUser]
    filterset_class = CustomerFilter
    search_fields = ["username", "email"]
    ordering_fields = [
        "date_joined",
        "username",
        "order_count",
        "total_spent",
        "last_order_at",
    ]
    ordering = ["-date_joined"]

    def get_queryset(self):
        """Customers only, with their order figures annotated.

        `total_spent` excludes cancelled orders: those were refunded or
        never charged, so counting them would overstate what a customer is
        worth. `order_count` includes them, because "how many times have
        they ordered" is a different question from "what have they spent".
        """
        money = DecimalField(max_digits=14, decimal_places=2)

        return (
            User.objects.filter(
                Q(profile__role=Role.CUSTOMER) | Q(profile__isnull=True)
            )
            .exclude(is_superuser=True)
            .select_related("profile")
            .annotate(
                order_count=Count("orders", distinct=True),
                total_spent=Coalesce(
                    Sum(
                        "orders__total_price",
                        filter=~Q(orders__status=OrderStatus.CANCELLED),
                    ),
                    Value(0, output_field=money),
                    output_field=money,
                ),
                last_order_at=Max("orders__created_at"),
            )
        )

    def get_serializer_class(self):
        if self.action == "list":
            return CustomerListSerializer
        return CustomerDetailSerializer

    def _detail_response(self, customer):
        """Re-read through the annotated queryset so the response carries the
        same figures the list does."""
        refreshed = self.get_queryset().get(pk=customer.pk)
        return Response(
            CustomerDetailSerializer(
                refreshed, context=self.get_serializer_context()
            ).data
        )

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """POST /api/org/customers/{id}/deactivate/ {"reason": "..."}

        Their orders and history stay exactly as they are; only signing in
        stops. Any token they hold is deleted as well — Django REST
        Framework already refuses an inactive user's token, but leaving a
        live row around to be relied on later is asking for trouble.
        """
        customer = self.get_object()
        serializer = CustomerStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not customer.is_active:
            return Response(
                {"detail": "This account is already deactivated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer.is_active = False
        customer.save(update_fields=["is_active"])
        Token.objects.filter(user=customer).delete()

        return self._detail_response(customer)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        """POST /api/org/customers/{id}/activate/ — undo a deactivation.

        The customer logs in again as normal and is issued a fresh token.
        """
        customer = self.get_object()

        if customer.is_active:
            return Response(
                {"detail": "This account is already active."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer.is_active = True
        customer.save(update_fields=["is_active"])

        return self._detail_response(customer)