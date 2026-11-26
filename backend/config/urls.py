"""Root URL configuration.

Everything the API exposes lives under /api/, so the admin site and media
files can never collide with an endpoint name.

App routes (catalog, orders, accounts) are included here as each app is
built; see the app-level `urls.py` files for the concrete endpoints.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # Login/logout pages for DRF's browsable API (handy while developing).
    path("api-auth/", include("rest_framework.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
