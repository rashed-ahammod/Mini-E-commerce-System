"""Serializers for the order endpoints."""

from django.db import transaction
from rest_framework import serializers

from accounts.models import profile_for
from accounts.serializers import validate_address, validate_phone
from catalog.models import Product
from catalog.serializers import ProductBriefSerializer

from .models import Order


def _keyed(field, validator, value):
    """Run `validator`, re-raising anything it rejects against `field`.

    The validators in `accounts.serializers` are written for fields that DRF
    runs itself, where it adds the field name. These two are resolved in
    `validate()` instead — one address can come from either of two inputs —
    so the name has to be put back by hand.
    """
    try:
        return validator(value)
    except serializers.ValidationError as error:
        raise serializers.ValidationError({field: error.detail}) from error


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
    # Customers can watch their order progress, but only the organization
    # can change where it has got to.
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    # -- delivery -------------------------------------------------------
    # The address is required, but it may arrive one of two ways: typed into
    # the field, or asked for from the profile with `use_profile_address`.
    # `validate()` below resolves the two into one address before anything
    # else looks at it.
    delivery_address = serializers.CharField(
        max_length=500, required=False, allow_blank=True
    )
    delivery_phone = serializers.CharField(
        max_length=30, required=False, allow_blank=True
    )
    use_profile_address = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
        help_text="Deliver to the address saved on my profile.",
    )
    save_to_profile = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
        help_text="Also save this address to my profile as the default.",
    )

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
            "delivery_address",
            "delivery_phone",
            "use_profile_address",
            "save_to_profile",
            "status",
            "status_display",
            "status_updated_at",
            "cancelled_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "unit_price",
            "total_price",
            "status",
            "status_updated_at",
            "cancelled_at",
            "created_at",
        ]

    def validate(self, attrs):
        """Check the stock and settle on a delivery address.

        The stock check here is the friendly, read-only one that produces a
        clear error message. `create()` below checks again under a row lock,
        because another order could be placed between this check and the
        write.
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

        self._resolve_delivery(attrs)
        return attrs

    def _resolve_delivery(self, attrs):
        """Turn the two ways of saying "deliver here" into one address.

        Either the customer typed an address, or they asked for the one on
        their profile. Whichever it is, the order ends up with a real address
        and a phone number, validated the same way the profile validates
        them — so an order can never be stored with a destination too vague
        to deliver to.
        """
        profile = profile_for(self.context["request"].user)

        if attrs.pop("use_profile_address", False):
            saved = (profile.address or "").strip() if profile else ""
            if not saved:
                raise serializers.ValidationError(
                    {
                        "use_profile_address": (
                            "Your profile does not have a delivery address "
                            "yet. Add one on your profile, or type an "
                            "address instead."
                        )
                    }
                )
            attrs["delivery_address"] = saved
            # Only borrow the profile's phone if none was typed, so a
            # one-off "call me on this number instead" still works.
            if not (attrs.get("delivery_phone") or "").strip():
                attrs["delivery_phone"] = (profile.phone or "").strip()

        address = (attrs.get("delivery_address") or "").strip()
        if not address:
            raise serializers.ValidationError(
                {
                    "delivery_address": (
                        "A delivery address is required. Type one, or choose "
                        "the address saved on your profile."
                    )
                }
            )
        # Keyed to the field: `validate_address` raises unkeyed, and an
        # error arriving as `non_field_errors` is one a form cannot show
        # next to the input the customer has to fix.
        attrs["delivery_address"] = _keyed("delivery_address", validate_address, address)

        phone = (attrs.get("delivery_phone") or "").strip()
        if not phone and profile:
            phone = (profile.phone or "").strip()
        if not phone:
            raise serializers.ValidationError(
                {
                    "delivery_phone": (
                        "A contact number is required so the courier can "
                        "reach you. Add one to your profile, or type one here."
                    )
                }
            )
        attrs["delivery_phone"] = _keyed("delivery_phone", validate_phone, phone)

    def create(self, validated_data):
        """Create the order and reduce the product's stock atomically."""
        product = validated_data["product"]
        quantity = validated_data["quantity"]
        address = validated_data["delivery_address"]
        phone = validated_data["delivery_phone"]
        save_to_profile = validated_data.pop("save_to_profile", False)

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

            user = self.context["request"].user

            if save_to_profile:
                # The customer asked for this address to become their
                # default. Inside the transaction so a failed order does not
                # leave a half-applied change behind.
                profile = profile_for(user)
                profile.address = address
                profile.phone = phone
                profile.save(update_fields=["address", "phone", "updated_at"])

            return Order.objects.create(
                user=user,
                product=locked_product,
                quantity=quantity,
                # Snapshot of today's price; see Order.save().
                unit_price=locked_product.price,
                # Snapshot of the destination, for the same reason.
                delivery_address=address,
                delivery_phone=phone,
            )
