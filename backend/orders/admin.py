"""Admin registration for orders and their history."""

from django.contrib import admin

from .models import Order, OrderStatusEvent


class OrderStatusEventInline(admin.TabularInline):
    """The order's timeline, shown read-only on the order page.

    History is written by `Order.transition_to()`, which also returns stock
    on a cancellation. Letting someone type an event here by hand would
    produce a record of something that never happened.
    """

    model = OrderStatusEvent
    extra = 0
    can_delete = False
    readonly_fields = ("from_status", "to_status", "changed_by", "note", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "product",
        "quantity",
        "total_price",
        "status",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "product__name", "delivery_address")
    autocomplete_fields = ("user", "product")
    # Prices are derived from the product and quantity; status moves through
    # the API so the stock and history stay consistent with it.
    readonly_fields = (
        "unit_price",
        "total_price",
        "status_updated_at",
        "cancelled_at",
        "stock_restored",
        "created_at",
    )
    date_hierarchy = "created_at"
    inlines = [OrderStatusEventInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "product")
