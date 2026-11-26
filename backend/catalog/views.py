"""API views for categories and products.

Both are ModelViewSets, so the five required operations (list, retrieve,
create, update, destroy) come from one class each and the router builds the
URLs.

Reading the catalog is public: the shop front has to work for a visitor who
has not logged in. Changing it is restricted to organization users — a
customer with a token may place orders, but must not be able to invent
categories, reprice a product or delete one.
"""

from django.db import transaction
from django.db.models import Count, ProtectedError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsOrganizationUser, IsOrganizationUserOrReadOnly

from .filters import ProductFilter
from .models import Category, Product
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    StockAdjustmentSerializer,
)


class ProtectedDeleteMixin:
    """Turn a database PROTECT error into a readable 409 instead of a 500.

    Orders reference products with on_delete=PROTECT, so deleting a product
    that has already been ordered (or a category containing one) is refused
    by the database. Without this the client would just see a server error.
    """

    protected_delete_message = "This object is referenced by existing orders."

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": self.protected_delete_message},
                status=status.HTTP_409_CONFLICT,
            )


class CategoryViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    """CRUD for categories.

        GET    /api/categories/        list     (public)
        GET    /api/categories/{id}/   retrieve (public)
        POST   /api/categories/        create   (organization only)
        PUT    /api/categories/{id}/   update   (organization only)
        PATCH  /api/categories/{id}/   partial  (organization only)
        DELETE /api/categories/{id}/   delete   (organization only)
    """

    serializer_class = CategorySerializer
    permission_classes = [IsOrganizationUserOrReadOnly]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
    protected_delete_message = (
        "This category cannot be deleted because some of its products "
        "belong to existing orders."
    )

    def get_queryset(self):
        # product_count is computed in the database, not by looping in Python.
        return Category.objects.annotate(product_count=Count("products"))


class ProductViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    """CRUD for products, plus filtering, searching, ordering and pagination.

        GET /api/products/?search=phone      search name and description
        GET /api/products/?category=1        filter by category id
        GET /api/products/?min_price=100&max_price=500
        GET /api/products/?ordering=price    cheapest first (-price for high)
        GET /api/products/?page=2&page_size=20
        GET /api/products/?low_stock=5       what needs reordering

    Pagination is applied to every list endpoint by the project-wide
    DefaultPagination class.

    Reading is public; creating, updating and deleting require an
    organization account, as does the adjust-stock action below.
    """

    serializer_class = ProductSerializer
    permission_classes = [IsOrganizationUserOrReadOnly]
    filterset_class = ProductFilter
    search_fields = ["name", "description"]
    ordering_fields = ["price", "name", "created_at", "stock"]
    ordering = ["-created_at"]
    protected_delete_message = (
        "This product cannot be deleted because it belongs to existing orders."
    )

    def get_queryset(self):
        # select_related avoids one extra query per product for the nested
        # category in the response.
        return Product.objects.select_related("category")

    @action(
        detail=True,
        methods=["post"],
        url_path="adjust-stock",
        permission_classes=[IsOrganizationUser],
    )
    def adjust_stock(self, request, pk=None):
        """POST /api/products/{id}/adjust-stock/ — restock or correct a count.

            {"delta": 25, "reason": "delivery received"}
            {"stock": 40, "reason": "stocktake"}

        Editing `stock` with PATCH works too, but this exists because the
        two are not equally safe. PATCH writes the number the client last
        saw, so an order placed in between is overwritten and the shop
        oversells. `delta` is applied to the row inside a transaction, under
        the same lock the order path uses, so the two cannot interleave.
        """
        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        changes = serializer.validated_data

        with transaction.atomic():
            product = Product.objects.select_for_update().get(pk=self.get_object().pk)
            previous = product.stock

            if "delta" in changes:
                new_stock = previous + changes["delta"]
                if new_stock < 0:
                    return Response(
                        {
                            "delta": [
                                f"Cannot remove {abs(changes['delta'])} units: "
                                f"only {previous} in stock."
                            ]
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                new_stock = changes["stock"]

            product.stock = new_stock
            product.save(update_fields=["stock", "updated_at"])

        return Response(
            {
                "product": ProductSerializer(product, context={"request": request}).data,
                "previous_stock": previous,
                "new_stock": new_stock,
                "reason": changes.get("reason", ""),
            }
        )
