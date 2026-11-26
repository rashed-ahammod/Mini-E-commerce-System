"""Admin registration for the catalog models."""

from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "product_count", "created_at")
    search_fields = ("name", "description")
    ordering = ("name",)

    @admin.display(description="products")
    def product_count(self, category: Category) -> int:
        return category.products.count()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("thumbnail", "name", "category", "price", "stock", "created_at")
    list_display_links = ("thumbnail", "name")
    list_filter = ("category", "created_at")
    list_editable = ("price", "stock")
    search_fields = ("name", "description")
    autocomplete_fields = ("category",)
    date_hierarchy = "created_at"

    @admin.display(description="")
    def thumbnail(self, product: Product):
        """Small preview so the list is scannable, from whichever image is set."""
        url = product.image.url if product.image else product.image_url
        if not url:
            return "—"
        return format_html(
            '<img src="{}" alt="" style="height:38px;width:38px;'
            'object-fit:cover;border-radius:6px;" />',
            url,
        )
