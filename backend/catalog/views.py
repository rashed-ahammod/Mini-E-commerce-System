"""API views for categories and products.

Both are ModelViewSets, so the five required operations (list, retrieve,
create, update, destroy) come from one class each and the router builds the
URLs. Reading is open to anyone; writing requires authentication, which comes
from REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] in config/settings.py.
"""

from django.db.models import Count, ProtectedError
from rest_framework import status, viewsets
from rest_framework.response import Response

from .filters import ProductFilter
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer


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

        GET    /api/categories/        list   (?search=, ?ordering=)
        POST   /api/categories/        create (auth required)
        GET    /api/categories/{id}/   retrieve
        PUT    /api/categories/{id}/   update (auth required)
        PATCH  /api/categories/{id}/   partial update (auth required)
        DELETE /api/categories/{id}/   delete (auth required)
    """

    serializer_class = CategorySerializer
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

    Pagination is applied to every list endpoint by the project-wide
    DefaultPagination class.
    """

    serializer_class = ProductSerializer
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
