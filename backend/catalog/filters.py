"""Query-string filters for the product list endpoint."""

from django_filters import rest_framework as filters

from .models import Product


class ProductFilter(filters.FilterSet):
    """Filters available on GET /api/products/.

        ?category=1              exact category id
        ?category_name=phones    case-insensitive category name
        ?min_price=100           price greater than or equal to
        ?max_price=500           price less than or equal to
        ?in_stock=true           only products with stock left
        ?low_stock=5             stock at or below 5 (restocking view)
    """

    min_price = filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = filters.NumberFilter(field_name="price", lookup_expr="lte")
    category_name = filters.CharFilter(
        field_name="category__name",
        lookup_expr="iexact",
    )
    in_stock = filters.BooleanFilter(method="filter_in_stock")
    # Used by the organization side to find what needs reordering.
    low_stock = filters.NumberFilter(field_name="stock", lookup_expr="lte")

    class Meta:
        model = Product
        # `price` stays available as an exact match, e.g. ?price=499.99
        fields = ["category", "price"]

    def filter_in_stock(self, queryset, name, value):
        """?in_stock=true -> stock > 0, ?in_stock=false -> stock == 0."""
        if value is True:
            return queryset.filter(stock__gt=0)
        if value is False:
            return queryset.filter(stock=0)
        return queryset
