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


class StockAdjustmentSerializer(serializers.Serializer):
    """Input for POST /api/products/{id}/adjust-stock/.

    Two ways to say what should happen, and exactly one must be given:

        {"delta": 25}    a relative change: +25 received, -3 damaged
        {"stock": 40}    an absolute count, e.g. after a stocktake

    `delta` is the safer of the two under concurrency: it is applied to
    whatever the row holds at the time, so an order placed between reading
    the page and submitting the form is not silently overwritten.
    """

    delta = serializers.IntegerField(required=False)
    stock = serializers.IntegerField(required=False, min_value=0)
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=200,
        help_text="Free text, echoed back in the response for the audit trail.",
    )

    def validate(self, attrs):
        has_delta = "delta" in attrs
        has_stock = "stock" in attrs

        if has_delta == has_stock:
            raise serializers.ValidationError(
                "Send either 'delta' (a relative change) or 'stock' "
                "(an absolute count), but not both."
            )
        if has_delta and attrs["delta"] == 0:
            raise serializers.ValidationError({"delta": "Must not be zero."})
        return attrs
