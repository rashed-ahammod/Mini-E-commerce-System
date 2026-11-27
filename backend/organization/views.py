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

from accounts.models import Role, profile_for
from accounts.permissions import IsOrganizationAdmin, IsOrganizationUser
from orders.models import InvalidTransition, Order, OrderStatus

from .dashboard import build_dashboard
from .filters import CustomerFilter, OrgOrderFilter
from .serializers import (
    CustomerDetailSerializer,
    CustomerListSerializer,
    CustomerStatusSerializer,
    DashboardQuerySerializer,
    OrgStaffCreateSerializer,
    OrgStaffSerializer,
    OrgStaffUpdateSerializer,
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


class OrgStaffViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """The organization's own accounts — admins only.

        GET    /api/org/staff/                  colleagues
        POST   /api/org/staff/                  add one
        GET    /api/org/staff/{id}/             one of them
        PATCH  /api/org/staff/{id}/             change role or details
        POST   /api/org/staff/{id}/deactivate/  revoke access
        POST   /api/org/staff/{id}/activate/    restore it

    Admin-only rather than staff-only: deciding who else may run the shop is
    a different kind of decision from running it. The first admin is created
    with `manage.py create_org_user`, because an API that needs an admin in
    order to create an admin cannot bootstrap itself.

    Two guards stop an admin from locking everyone out:

    * you cannot change your own role — demoting yourself by accident would
      end your access mid-session;
    * you cannot deactivate your own account.

    Together those are sufficient today: the caller is always an admin, so
    any account they act on other than their own leaves the caller holding
    admin rights. `_would_remove_the_last_admin` is a third check behind
    them, and with the self-guards in place it cannot currently fire. It is
    kept as a backstop for a future caller — a bulk action, a scheduled
    cleanup, a relaxed self-guard — that could otherwise empty the role.
    Its behaviour is unit-tested directly rather than through HTTP, because
    pretending it is reachable would be a test that passes for the wrong
    reason.

    Deleting is not offered: an account that has moved orders along owns
    history that should keep their name on it. Revoke access instead.
    """

    permission_classes = [IsOrganizationAdmin]
    serializer_class = OrgStaffSerializer
    filterset_fields = ["is_active", "profile__role"]
    search_fields = ["username", "email", "profile__department"]
    ordering_fields = ["username", "date_joined", "last_login"]
    ordering = ["username"]

    def get_queryset(self):
        """Organization accounts only — customers have their own endpoint.

        Superusers are included even without an explicit organization role,
        because the permission classes already treat them as admins; leaving
        them out would make this list disagree with who can actually act.
        """
        return (
            User.objects.filter(
                Q(profile__role__in=[Role.STAFF, Role.ADMIN]) | Q(is_superuser=True)
            )
            .select_related("profile")
            .distinct()
        )

    def get_serializer_class(self):
        if self.action == "create":
            return OrgStaffCreateSerializer
        if self.action in ("update", "partial_update"):
            return OrgStaffUpdateSerializer
        return OrgStaffSerializer

    # -- guards -----------------------------------------------------------

    def _is_self(self, account) -> bool:
        return account.pk == self.request.user.pk

    def _active_admin_count(self, excluding=None) -> int:
        admins = self.get_queryset().filter(
            Q(profile__role=Role.ADMIN) | Q(is_superuser=True), is_active=True
        )
        if excluding is not None:
            admins = admins.exclude(pk=excluding.pk)
        return admins.count()

    def _would_remove_the_last_admin(self, account) -> bool:
        profile = profile_for(account)
        is_admin = bool(profile and profile.is_organization_admin) and account.is_active
        return is_admin and self._active_admin_count(excluding=account) == 0

    def _detail_response(self, account):
        account.refresh_from_db()
        return Response(
            OrgStaffSerializer(account, context=self.get_serializer_context()).data
        )

    # -- actions ----------------------------------------------------------

    def create(self, request, *args, **kwargs):
        serializer = OrgStaffCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = serializer.save()
        response = self._detail_response(account)
        response.status_code = status.HTTP_201_CREATED
        return response

    def update(self, request, *args, **kwargs):
        account = self.get_object()
        serializer = OrgStaffUpdateSerializer(
            account, data=request.data, partial=kwargs.pop("partial", False)
        )
        serializer.is_valid(raise_exception=True)

        new_role = serializer.validated_data.get("role")

        if new_role and self._is_self(account):
            return Response(
                {"role": ["You cannot change your own role."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            new_role
            and new_role != Role.ADMIN
            and self._would_remove_the_last_admin(account)
        ):
            return Response(
                {
                    "role": [
                        "This is the only active organization admin. Promote "
                        "someone else before changing this account's role."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return self._detail_response(account)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """POST /api/org/staff/{id}/deactivate/ {"reason": "..."}"""
        account = self.get_object()
        reason = CustomerStatusSerializer(data=request.data)
        reason.is_valid(raise_exception=True)

        if self._is_self(account):
            return Response(
                {"detail": "You cannot deactivate your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not account.is_active:
            return Response(
                {"detail": "This account is already deactivated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if self._would_remove_the_last_admin(account):
            return Response(
                {
                    "detail": "This is the only active organization admin. "
                    "Promote someone else first."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        account.is_active = False
        account.save(update_fields=["is_active"])
        Token.objects.filter(user=account).delete()

        return self._detail_response(account)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        """POST /api/org/staff/{id}/activate/ — restore a revoked account."""
        account = self.get_object()

        if account.is_active:
            return Response(
                {"detail": "This account is already active."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        account.is_active = True
        account.save(update_fields=["is_active"])
        return self._detail_response(account)
