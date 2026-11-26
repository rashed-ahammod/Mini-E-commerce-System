"""Database models for customer orders and their lifecycle."""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from catalog.models import Product


class OrderStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    PROCESSING = "processing", "Processing"
    SHIPPED = "shipped", "Shipped"
    DELIVERED = "delivered", "Delivered"
    CANCELLED = "cancelled", "Cancelled"


# Which status may follow which. Anything not listed here is refused, so an
# order cannot jump from "pending" straight to "delivered", nor go backwards
# once it has moved on.
#
# Cancelling is possible up to and including "processing". Once an order is
# shipped it is out of the organization's hands, and undoing that would mean
# a returns process with its own stock and refund rules — out of scope here,
# and better refused than half-implemented.
ALLOWED_TRANSITIONS = {
    OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.PROCESSING, OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}

# Statuses nothing can follow: the order is finished, one way or the other.
TERMINAL_STATUSES = {OrderStatus.DELIVERED, OrderStatus.CANCELLED}


class InvalidTransition(Exception):
    """Raised when a status change is not allowed from the current status."""


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

    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True,
    )
    status_updated_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=300, blank=True)
    # Set when a cancellation has put the units back, so a second cancel
    # attempt — or a retried request — cannot inflate stock.
    stock_restored = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Order #{self.pk} — {self.user} × {self.quantity} {self.product}"

    def save(self, *args, **kwargs):
        # Fall back to the current product price if the caller did not set one
        # (e.g. objects created in the admin or a shell).
        if not self.unit_price:
            self.unit_price = self.product.price
        self.total_price = Decimal(self.unit_price) * self.quantity
        super().save(*args, **kwargs)

    # -- lifecycle --------------------------------------------------------

    @property
    def is_open(self) -> bool:
        """Still moving: not delivered and not cancelled."""
        return self.status not in TERMINAL_STATUSES

    @property
    def next_statuses(self) -> list[str]:
        """What this order may become next, for the UI to offer."""
        return sorted(ALLOWED_TRANSITIONS.get(OrderStatus(self.status), set()))

    def can_transition_to(self, new_status) -> bool:
        return new_status in ALLOWED_TRANSITIONS.get(OrderStatus(self.status), set())

    @transaction.atomic
    def transition_to(self, new_status, changed_by=None, note=""):
        """Move the order to `new_status`, recording who did it and why.

        Cancelling returns the units to the product, because the order that
        took them is no longer going to happen. That happens here rather than
        in the view so every caller — API, admin, shell or a future
        scheduled job — gets the same behaviour.

        Raises InvalidTransition if the move is not allowed.
        """
        new_status = OrderStatus(new_status)
        previous = OrderStatus(self.status)

        if new_status == previous:
            raise InvalidTransition(f"This order is already {previous.label.lower()}.")

        if not self.can_transition_to(new_status):
            allowed = ", ".join(self.next_statuses) or "nothing — it is finished"
            raise InvalidTransition(
                f"An order that is {previous.label.lower()} cannot become "
                f"{new_status.label.lower()}. Allowed from here: {allowed}."
            )

        now = timezone.now()

        if new_status == OrderStatus.CANCELLED:
            self._restore_stock()
            self.cancelled_at = now
            self.cancellation_reason = note

        self.status = new_status
        self.status_updated_at = now
        self.save()

        OrderStatusEvent.objects.create(
            order=self,
            from_status=previous,
            to_status=new_status,
            changed_by=changed_by if changed_by and changed_by.is_authenticated else None,
            note=note,
        )
        return self

    def _restore_stock(self):
        """Put this order's units back on the product.

        Locks the product row so a restore and a concurrent order cannot read
        the same starting figure, and `stock_restored` makes it idempotent —
        a retried cancel request must not hand back the units twice.
        """
        if self.stock_restored:
            return

        product = Product.objects.select_for_update().get(pk=self.product_id)
        product.stock += self.quantity
        product.save(update_fields=["stock", "updated_at"])
        self.stock_restored = True


class OrderStatusEvent(models.Model):
    """One entry in an order's history.

    Kept as its own table rather than a single "last changed by" column so
    the organization can see the whole timeline: who confirmed it, who
    shipped it, who cancelled it and what reason they gave.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="events",
    )
    from_status = models.CharField(max_length=20, choices=OrderStatus.choices)
    to_status = models.CharField(max_length=20, choices=OrderStatus.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        # Keep the history even if the staff member's account is removed.
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_status_changes",
    )
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Order #{self.order_id}: {self.from_status} → {self.to_status}"
