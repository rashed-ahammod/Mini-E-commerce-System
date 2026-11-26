"""URL routes for the catalog app.

The DefaultRouter generates the list and detail routes for each viewset:
    /api/categories/  /api/categories/{id}/
    /api/products/    /api/products/{id}/
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, ProductViewSet

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("products", ProductViewSet, basename="product")

urlpatterns = [
    path("", include(router.urls)),
]
