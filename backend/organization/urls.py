"""Organization routes, mounted at /api/org/ by config/urls.py.

A DefaultRouter here, unlike the customer-facing apps, because /api/org/ is
its own prefix and an index of the organization endpoints is useful. Its
root view is renamed: the default name is "api-root", which would shadow
config.views.api_root and leave GET /api/ listing only these routes.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DashboardView, OrgOrderViewSet

router = DefaultRouter()
router.root_view_name = "org-root"
router.register("orders", OrgOrderViewSet, basename="org-order")

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="org-dashboard"),
    path("", include(router.urls)),
]
