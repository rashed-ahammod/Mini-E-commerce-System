"""Database models for the product catalog."""

from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    """A product grouping, e.g. "Phones" or "Laptops"."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    """An item for sale, always belonging to exactly one category."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    stock = models.PositiveIntegerField(
        default=0,
        help_text="Units currently available. An order cannot exceed this.",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="products",
    )
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # The product list is filtered by category and sorted by price
            # often enough to be worth an index on each.
            models.Index(fields=["category"]),
            models.Index(fields=["price"]),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def in_stock(self) -> bool:
        return self.stock > 0
