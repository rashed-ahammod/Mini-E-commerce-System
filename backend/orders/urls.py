"""Order routes, mounted at /api/ by config/urls.py.

SimpleRouter rather than DefaultRouter, so no second "api-root" view is
registered at the same prefix as config.views.api_root.
"""

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import OrderViewSet

router = SimpleRouter()
router.register("orders", OrderViewSet, basename="order")

urlpatterns = [
    path("", include(router.urls)),
]
