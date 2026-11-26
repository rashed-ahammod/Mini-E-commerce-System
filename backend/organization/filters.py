"""Query-string filters for the organization's order list."""

from django_filters import rest_framework as filters

from orders.models import Order, OrderStatus, TERMINAL_STATUSES


class OrgOrderFilter(filters.FilterSet):
    """Filters available on GET /api/org/orders/.

        ?status=pending              exact status
        ?status__in=pending,confirmed    several at once
        ?open=true                   anything not delivered or cancelled
        ?customer=3                  orders belonging to one customer id
        ?customer_username=demo      ...or by username
        ?product=12                  orders for one product
        ?placed_after=2026-01-01     created on or after a date
        ?placed_before=2026-01-31    created on or before a date
        ?min_total=100               total_price at least
        ?max_total=500               total_price at most
    """

    status__in = filters.BaseInFilter(field_name="status")
    open = filters.BooleanFilter(method="filter_open")
    customer = filters.NumberFilter(field_name="user__id")
    customer_username = filters.CharFilter(
        field_name="user__username", lookup_expr="iexact"
    )
    placed_after = filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    placed_before = filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    min_total = filters.NumberFilter(field_name="total_price", lookup_expr="gte")
    max_total = filters.NumberFilter(field_name="total_price", lookup_expr="lte")

    class Meta:
        model = Order
        fields = ["status", "product"]

    def filter_open(self, queryset, name, value):
        """?open=true -> still being worked on; ?open=false -> finished."""
        if value is True:
            return queryset.exclude(status__in=TERMINAL_STATUSES)
        if value is False:
            return queryset.filter(status__in=TERMINAL_STATUSES)
        return queryset
