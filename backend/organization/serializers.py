"""Serializers for the organization API.

These are intentionally separate from the customer-facing ones in
`orders.serializers`: the organization sees more of an order (who placed it,
the full status history, cancellation details) and is allowed to do things a
customer is not. Sharing one serializer between the two would mean a single
careless `fields` edit could leak a customer's details into the shop.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from catalog.serializers import ProductBriefSerializer
from orders.models import ALLOWED_TRANSITIONS, Order, OrderStatus, OrderStatusEvent

User = get_user_model()


class OrderCustomerSerializer(serializers.ModelSerializer):
    """The customer behind an order, as the organization needs to see them."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "date_joined"]
        read_only_fields = fields


class OrderStatusEventSerializer(serializers.ModelSerializer):
    """One entry in an order's timeline."""

    changed_by = serializers.StringRelatedField()
    from_status_display = serializers.CharField(
        source="get_from_status_display", read_only=True
    )
    to_status_display = serializers.CharField(
        source="get_to_status_display", read_only=True
    )

    class Meta:
        model = OrderStatusEvent
        fields = [
            "id",
            "from_status",
            "from_status_display",
            "to_status",
            "to_status_display",
            "changed_by",
            "note",
            "created_at",
        ]
        read_only_fields = fields


class OrgOrderListSerializer(serializers.ModelSerializer):
    """An order as it appears in the organization's order list."""

    customer = OrderCustomerSerializer(source="user", read_only=True)
    product = ProductBriefSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "customer",
            "product",
            "quantity",
            "unit_price",
            "total_price",
            "status",
            "status_display",
            "status_updated_at",
            "created_at",
        ]
        read_only_fields = fields


class OrgOrderDetailSerializer(OrgOrderListSerializer):
    """One order in full, including its history and what it may become next.

    `next_statuses` means the UI never has to hold its own copy of the
    transition rules: it offers exactly the buttons the server will accept.
    """

    events = OrderStatusEventSerializer(many=True, read_only=True)
    next_statuses = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    is_open = serializers.BooleanField(read_only=True)

    class Meta(OrgOrderListSerializer.Meta):
        fields = OrgOrderListSerializer.Meta.fields + [
            "cancelled_at",
            "cancellation_reason",
            "stock_restored",
            "is_open",
            "next_statuses",
            "events",
        ]
        read_only_fields = fields


class OrderStatusUpdateSerializer(serializers.Serializer):
    """Input for POST /api/org/orders/{id}/status/.

        {"status": "confirmed", "note": "payment cleared"}

    Whether the move is allowed from the order's current status is decided
    by the model, not here, so the same rules apply from the admin and the
    shell too.
    """

    status = serializers.ChoiceField(choices=OrderStatus.choices)
    note = serializers.CharField(
        required=False, allow_blank=True, max_length=300,
        help_text="Why the status changed. Kept in the order's history.",
    )


class OrderCancelSerializer(serializers.Serializer):
    """Input for POST /api/org/orders/{id}/cancel/.

    A reason is required: a cancelled order returns stock and disappoints a
    customer, so the history should say why it happened.
    """

    reason = serializers.CharField(max_length=300)


class TransitionRulesSerializer(serializers.Serializer):
    """Shape of GET /api/org/orders/statuses/ — the workflow, described."""

    status = serializers.CharField()
    label = serializers.CharField()
    next_statuses = serializers.ListField(child=serializers.CharField())

    @staticmethod
    def describe_workflow():
        return [
            {
                "status": status.value,
                "label": status.label,
                "next_statuses": sorted(ALLOWED_TRANSITIONS.get(status, set())),
            }
            for status in OrderStatus
        ]


class DashboardQuerySerializer(serializers.Serializer):
    """Query parameters for GET /api/org/dashboard/.

    Both are bounded: an unbounded `days` would let a caller ask for a
    multi-year daily series in one request.
    """

    days = serializers.IntegerField(
        required=False, default=30, min_value=1, max_value=365,
        help_text="Window for the trend and the 'in_window' figures.",
    )
    low_stock_threshold = serializers.IntegerField(
        required=False, default=5, min_value=0, max_value=1000,
        help_text="Stock at or below this counts as running low.",
    )


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------


class CustomerListSerializer(serializers.ModelSerializer):
    """A customer as the organization sees them in the customer list.

    The three figures are annotated onto the queryset by the viewset, so the
    list costs one query however many customers there are.
    """

    order_count = serializers.IntegerField(read_only=True)
    total_spent = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    last_order_at = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "is_active",
            "date_joined",
            "last_login",
            "order_count",
            "total_spent",
            "last_order_at",
        ]
        read_only_fields = fields


class CustomerDetailSerializer(CustomerListSerializer):
    """One customer, with their recent orders attached.

    Capped at the most recent few: a customer's full history belongs on the
    order list, filtered by customer, where it can be paginated.
    """

    phone = serializers.CharField(source="profile.phone", read_only=True, default="")
    recent_orders = serializers.SerializerMethodField()

    class Meta(CustomerListSerializer.Meta):
        fields = CustomerListSerializer.Meta.fields + ["phone", "recent_orders"]
        read_only_fields = fields

    def get_recent_orders(self, user):
        orders = user.orders.select_related("product").order_by("-created_at")[:10]
        return OrgOrderListSerializer(
            orders, many=True, context=self.context
        ).data


class CustomerStatusSerializer(serializers.Serializer):
    """Input for the deactivate action.

    A reason is required. Blocking someone from signing in is a decision
    another member of staff may have to explain later.
    """

    reason = serializers.CharField(max_length=300)
