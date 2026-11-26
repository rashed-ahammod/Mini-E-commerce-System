"""Admin registration for the catalog models."""

from django.contrib import admin

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
    list_display = ("name", "category", "price", "stock", "created_at")
    list_filter = ("category", "created_at")
    list_editable = ("price", "stock")
    search_fields = ("name", "description")
    autocomplete_fields = ("category",)
    date_hierarchy = "created_at"
