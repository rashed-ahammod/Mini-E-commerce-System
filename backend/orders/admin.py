"""Admin registration for orders."""

from django.contrib import admin

from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "product", "quantity", "total_price", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "product__name")
    autocomplete_fields = ("user", "product")
    # Prices are derived from the product and quantity, so they are shown
    # but not edited by hand.
    readonly_fields = ("unit_price", "total_price", "created_at")
    date_hierarchy = "created_at"
