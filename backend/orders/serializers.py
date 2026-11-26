"""Serializers for the order endpoints."""

from django.db import transaction
from rest_framework import serializers

from catalog.models import Product
from catalog.serializers import ProductBriefSerializer

from .models import Order


class OrderSerializer(serializers.ModelSerializer):
    """Orders.

    A client only ever sends `product_id` and `quantity`:

        {"product_id": 3, "quantity": 2}

    The user comes from the token, and the prices are calculated on the
    server, so a client cannot choose what it pays or order for someone else.
    """

    user = serializers.StringRelatedField(read_only=True)
    product = ProductBriefSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source="product",
        write_only=True,
    )
    quantity = serializers.IntegerField(min_value=1)

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "product",
            "product_id",
            "quantity",
            "unit_price",
            "total_price",
            "created_at",
        ]
        read_only_fields = ["id", "user", "unit_price", "total_price", "created_at"]

    def validate(self, attrs):
        """Reject the order early if the product does not have enough stock.

        This is the friendly, read-only check that produces a clear error
        message. `create()` below checks again under a row lock, because
        another order could be placed between this check and the write.
        """
        product = attrs["product"]
        quantity = attrs["quantity"]
        if quantity > product.stock:
            raise serializers.ValidationError(
                {
                    "quantity": (
                        f"Only {product.stock} unit(s) of "
                        f"'{product.name}' are in stock."
                    )
                }
            )
        return attrs

    def create(self, validated_data):
        """Create the order and reduce the product's stock atomically."""
        product = validated_data["product"]
        quantity = validated_data["quantity"]

        with transaction.atomic():
            # Re-read the product inside the transaction and lock its row,
            # so two simultaneous orders cannot both pass the stock check and
            # oversell the item. Note: SQLite ignores row locks (it serialises
            # writes database-wide instead); the lock becomes a real one when
            # DATABASE_URL points at PostgreSQL.
            locked_product = Product.objects.select_for_update().get(pk=product.pk)
            if quantity > locked_product.stock:
                raise serializers.ValidationError(
                    {
                        "quantity": (
                            f"Only {locked_product.stock} unit(s) of "
                            f"'{locked_product.name}' are in stock."
                        )
                    }
                )

            locked_product.stock -= quantity
            locked_product.save(update_fields=["stock", "updated_at"])

            return Order.objects.create(
                user=self.context["request"].user,
                product=locked_product,
                quantity=quantity,
                # Snapshot of today's price; see Order.save().
                unit_price=locked_product.price,
            )
