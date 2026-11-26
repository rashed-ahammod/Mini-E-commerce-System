"""Root URL configuration.

Everything the API exposes lives under /api/, so the admin site and media
files can never collide with an endpoint name.

See the app-level `urls.py` files for the concrete endpoints, or GET
/api/ for a live index of them.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from config.views import api_root, health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    # Liveness probe for the hosting platform; not part of the public API.
    path("healthz/", health_check, name="health-check"),
    path("api/", api_root, name="api-root"),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("catalog.urls")),
    path("api/", include("orders.urls")),
    # Everything the people who run the shop use; closed to customers.
    path("api/org/", include("organization.urls")),
    # Login/logout pages for DRF's browsable API (handy while developing).
    path("api-auth/", include("rest_framework.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
