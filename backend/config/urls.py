"""Root URL configuration.

Everything the API exposes lives under /api/, so the admin site and media
files can never collide with an endpoint name.

See the app-level `urls.py` files for the concrete endpoints, or GET
/api/ for a live index of them.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

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

# Uploaded files (product photographs). Django's own static serve is used
# rather than only enabling this in DEBUG, because otherwise an image
# uploaded through the admin or the console would 404 on the deployed site
# and look like a bug in the upload.
#
# It is not how a busy site should serve media — every request goes through
# Python — but this catalog's images are small and few. The real limitation
# is the host: Render's filesystem is wiped on each deploy, so uploads do
# not survive one. The seeded catalog therefore uses `Product.image_url`,
# and object storage (Cloudinary, S3) is the fix if uploads must persist.
# django.conf.urls.static.static() is not used here: it returns an empty
# list when DEBUG is off, which would leave uploads 404ing on the deployed
# site and looking like a broken upload feature.
urlpatterns += [
    re_path(
        r"^media/(?P<path>.*)$",
        serve,
        {"document_root": settings.MEDIA_ROOT},
    ),
]
