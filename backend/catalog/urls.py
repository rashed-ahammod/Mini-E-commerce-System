"""URL routes for the catalog app.

SimpleRouter, not DefaultRouter: these are mounted at /api/ alongside
config.views.api_root, and DefaultRouter would add a second index view
there under the same URL name, shadowing ours.

The router generates the list and detail routes for each viewset:
    /api/categories/  /api/categories/{id}/
    /api/products/    /api/products/{id}/
"""

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import CategoryViewSet, ProductViewSet

router = SimpleRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("products", ProductViewSet, basename="product")

urlpatterns = [
    path("", include(router.urls)),
]
