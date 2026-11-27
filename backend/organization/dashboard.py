"""The organization dashboard: one request, the state of the shop.

Everything here is computed by the database with aggregates rather than by
looping over rows in Python, so the endpoint stays flat as the order table
grows — roughly seven queries whether there are ten orders or ten thousand.

A note on what "revenue" means, because it is the number most easily got
wrong. Two figures are reported and they answer different questions:

    booked    every order that has not been cancelled, including ones still
              being processed — what has been promised
    realised  delivered orders only — what has actually been completed

Cancelled orders are excluded from both: the stock went back and no money
changed hands, so counting them would overstate the shop.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from catalog.models import Category, Product
from orders.models import Order, OrderStatus

User = get_user_model()

MONEY = DecimalField(max_digits=14, decimal_places=2)
ZERO = Value(Decimal("0.00"), output_field=MONEY)

# Orders that represent real demand. Cancelled ones do not.
NOT_CANCELLED = ~Q(status=OrderStatus.CANCELLED)


def _money(value) -> str:
    """Render a total the same way DRF renders a DecimalField."""
    return str((value or Decimal("0.00")).quantize(Decimal("0.01")))


def build_dashboard(*, days: int = 30, low_stock_threshold: int = 5) -> dict:
    """Assemble the dashboard payload.

    `days` controls the trend window and the "recent" figures;
    `low_stock_threshold` decides what counts as running low.
    """
    now = timezone.now()
    today = timezone.localdate()
    week_ago = now - timedelta(days=7)
    window_start = now - timedelta(days=days)

    return {
        "generated_at": now,
        "window_days": days,
        "low_stock_threshold": low_stock_threshold,
        "orders": _order_totals(today, week_ago, window_start),
        "revenue": _revenue(today, week_ago, window_start),
        "orders_by_status": _orders_by_status(),
        "customers": _customers(week_ago, window_start),
        "catalog": _catalog(low_stock_threshold),
        "top_products": _top_products(window_start),
        "needs_attention": _needs_attention(low_stock_threshold),
        "daily": _daily_trend(days),
    }


def _order_totals(today, week_ago, window_start) -> dict:
    """Counts, in one query, using filtered aggregates."""
    return Order.objects.aggregate(
        total=Count("id"),
        today=Count("id", filter=Q(created_at__date=today)),
        last_7_days=Count("id", filter=Q(created_at__gte=week_ago)),
        in_window=Count("id", filter=Q(created_at__gte=window_start)),
        open=Count(
            "id",
            filter=~Q(status__in=[OrderStatus.DELIVERED, OrderStatus.CANCELLED]),
        ),
        cancelled=Count("id", filter=Q(status=OrderStatus.CANCELLED)),
        delivered=Count("id", filter=Q(status=OrderStatus.DELIVERED)),
    )


def _revenue(today, week_ago, window_start) -> dict:
    totals = Order.objects.aggregate(
        booked=Coalesce(Sum("total_price", filter=NOT_CANCELLED), ZERO),
        realised=Coalesce(
            Sum("total_price", filter=Q(status=OrderStatus.DELIVERED)), ZERO
        ),
        lost_to_cancellations=Coalesce(
            Sum("total_price", filter=Q(status=OrderStatus.CANCELLED)), ZERO
        ),
        today=Coalesce(
            Sum("total_price", filter=NOT_CANCELLED & Q(created_at__date=today)), ZERO
        ),
        last_7_days=Coalesce(
            Sum("total_price", filter=NOT_CANCELLED & Q(created_at__gte=week_ago)), ZERO
        ),
        in_window=Coalesce(
            Sum("total_price", filter=NOT_CANCELLED & Q(created_at__gte=window_start)),
            ZERO,
        ),
        booked_orders=Count("id", filter=NOT_CANCELLED),
    )

    booked_orders = totals.pop("booked_orders")
    average = totals["booked"] / booked_orders if booked_orders else Decimal("0.00")

    payload = {key: _money(value) for key, value in totals.items()}
    payload["average_order_value"] = _money(average)
    return payload


def _orders_by_status() -> list[dict]:
    """Every status, including ones with no orders.

    A status missing from the response would make a dashboard render a gap
    rather than a zero, so the full set is filled in here.
    """
    counted = {
        row["status"]: row
        for row in Order.objects.values("status").annotate(
            count=Count("id"),
            value=Coalesce(Sum("total_price"), ZERO),
        )
    }

    return [
        {
            "status": status.value,
            "label": status.label,
            "count": counted.get(status.value, {}).get("count", 0),
            "value": _money(counted.get(status.value, {}).get("value")),
        }
        for status in OrderStatus
    ]


def _customers(week_ago, window_start) -> dict:
    """Customers only — organization accounts are staff, not clientele."""
    customers = User.objects.filter(
        Q(profile__role="customer") | Q(profile__isnull=True)
    ).exclude(is_superuser=True)

    # Every count here is distinct. `with_orders` joins the orders table,
    # and that join multiplies a customer's row once per order they have
    # placed — so a plain Count("id") would report a customer with three
    # orders as three customers.
    return customers.aggregate(
        total=Count("id", distinct=True),
        new_last_7_days=Count(
            "id", filter=Q(date_joined__gte=week_ago), distinct=True
        ),
        new_in_window=Count(
            "id", filter=Q(date_joined__gte=window_start), distinct=True
        ),
        with_orders=Count("id", filter=Q(orders__isnull=False), distinct=True),
        inactive=Count("id", filter=Q(is_active=False), distinct=True),
    )


def _catalog(low_stock_threshold) -> dict:
    stats = Product.objects.aggregate(
        products=Count("id"),
        out_of_stock=Count("id", filter=Q(stock=0)),
        low_stock=Count("id", filter=Q(stock__gt=0, stock__lte=low_stock_threshold)),
        units_in_stock=Coalesce(Sum("stock"), Value(0)),
    )
    stats["categories"] = Category.objects.count()
    return stats


def _top_products(window_start) -> list[dict]:
    """Best sellers in the window, by units sold.

    Cancelled orders are excluded: those units came back, so counting them
    would point restocking at the wrong products.
    """
    rows = (
        Order.objects.filter(NOT_CANCELLED, created_at__gte=window_start)
        .values("product_id", "product__name")
        .annotate(
            units_sold=Sum("quantity"),
            revenue=Coalesce(Sum("total_price"), ZERO),
            order_count=Count("id"),
        )
        .order_by("-units_sold")[:5]
    )

    return [
        {
            "product_id": row["product_id"],
            "name": row["product__name"],
            "units_sold": row["units_sold"],
            "order_count": row["order_count"],
            "revenue": _money(row["revenue"]),
        }
        for row in rows
    ]


def _needs_attention(low_stock_threshold) -> dict:
    """The two lists someone opening the dashboard is looking for."""
    low = (
        Product.objects.filter(stock__lte=low_stock_threshold)
        .order_by("stock", "name")
        .values("id", "name", "stock")[:10]
    )
    waiting = (
        Order.objects.filter(status=OrderStatus.PENDING)
        .select_related("user", "product")
        .order_by("created_at")[:10]
    )

    return {
        "low_stock_products": list(low),
        "orders_awaiting_action": [
            {
                "id": order.id,
                "customer": order.user.username,
                "product": order.product.name,
                "quantity": order.quantity,
                "total_price": str(order.total_price),
                "created_at": order.created_at,
            }
            for order in waiting
        ],
    }


def _daily_trend(days: int) -> list[dict]:
    """Orders and revenue per day, oldest first, for charting.

    Days with no orders are filled in with zeros rather than left out, so a
    chart does not join two distant points into a straight line that implies
    activity which did not happen.
    """
    start = timezone.localdate() - timedelta(days=days - 1)

    counted = {
        row["day"]: row
        for row in Order.objects.filter(created_at__date__gte=start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            orders=Count("id"),
            revenue=Coalesce(Sum("total_price", filter=NOT_CANCELLED), ZERO),
        )
    }

    return [
        {
            "date": start + timedelta(days=offset),
            "orders": counted.get(start + timedelta(days=offset), {}).get("orders", 0),
            "revenue": _money(
                counted.get(start + timedelta(days=offset), {}).get("revenue")
            ),
        }
        for offset in range(days)
    ]
