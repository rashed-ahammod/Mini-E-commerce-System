"""Serializers that translate catalog models to and from JSON."""

from rest_framework import serializers

from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    """Full representation of a category, used by the /categories/ endpoints."""

    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "description", "product_count", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_product_count(self, category: Category) -> int:
        """Use the annotation added by CategoryViewSet.get_queryset() when it
        is there (one query for the whole list), and fall back to counting for
        a freshly created object, which has not been re-fetched.
        """
        annotated = getattr(category, "product_count", None)
        if annotated is not None:
            return annotated
        return category.products.count()


class CategoryBriefSerializer(serializers.ModelSerializer):
    """Compact category, nested inside product responses."""

    class Meta:
        model = Category
        fields = ["id", "name"]


class ProductBriefSerializer(serializers.ModelSerializer):
    """Compact product, nested inside order responses."""

    class Meta:
        model = Product
        fields = ["id", "name", "price", "image"]


class ProductSerializer(serializers.ModelSerializer):
    """Products.

    Reads return the category nested (`category`), so the frontend can show a
    name without a second request. Writes take a plain id (`category_id`),
    which keeps request bodies simple:

        {"name": "Phone", "price": "499.99", "stock": 5, "category_id": 1}
    """

    category = CategoryBriefSerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source="category",
        write_only=True,
    )
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "price",
            "stock",
            "in_stock",
            "category",
            "category_id",
            "image",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return value
