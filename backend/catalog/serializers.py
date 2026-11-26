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


def resolve_image(product, request=None):
    """The picture to show for a product, or None.

    An uploaded file wins over `image_url`, so a product can be given a
    proper photo later without clearing the seeded link. Upload URLs are
    made absolute, because the frontend runs on a different origin and a
    path like /media/... would resolve against the frontend instead.
    """
    if product.image:
        url = product.image.url
        return request.build_absolute_uri(url) if request else url
    return product.image_url or None


class ProductBriefSerializer(serializers.ModelSerializer):
    """Compact product, nested inside order responses."""

    image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "price", "image"]

    def get_image(self, product):
        return resolve_image(product, self.context.get("request"))


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

    # Read: one resolved URL, whichever source the product uses.
    image = serializers.SerializerMethodField()
    # Write: upload a file...
    image_upload = serializers.ImageField(
        source="image", write_only=True, required=False, allow_null=True
    )
    # ...or point at one hosted elsewhere.

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
            "image_upload",
            "image_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_image(self, product):
        return resolve_image(product, self.context.get("request"))

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return value
