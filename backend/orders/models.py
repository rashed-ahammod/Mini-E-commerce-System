"""Database models for customer orders."""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import Product


class Order(models.Model):
    """A single purchase: one user buying one product, in some quantity.

    `unit_price` is a snapshot of the product price at the time of the order,
    so changing a product's price later never rewrites past order history.
    `total_price` is derived from it in `save()`.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    product = models.ForeignKey(
        Product,
        # PROTECT keeps order history honest: a product that has been ordered
        # cannot be deleted out from under its orders. The product API turns
        # the resulting ProtectedError into a clear 409 response.
        on_delete=models.PROTECT,
        related_name="orders",
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self) -> str:
        return f"Order #{self.pk} — {self.user} × {self.quantity} {self.product}"

    def save(self, *args, **kwargs):
        # Fall back to the current product price if the caller did not set one
        # (e.g. objects created in the admin or a shell).
        if not self.unit_price:
            self.unit_price = self.product.price
        self.total_price = Decimal(self.unit_price) * self.quantity
        super().save(*args, **kwargs)
