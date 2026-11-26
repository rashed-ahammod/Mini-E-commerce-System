"""
Django settings for the Mini E-commerce REST API.

Values that change between machines (secret key, debug flag, hosts, database,
CORS origins) are read from environment variables so the same code can run in
development and in production. See `.env.example` for the full list.
"""

from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Load backend/.env if it exists. Real environment variables always win.
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean from the environment ("1", "true", "yes" are True)."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    """Read a comma-separated list from the environment."""
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------

DEBUG = env_bool("DJANGO_DEBUG", True)

DEV_SECRET_KEY = "dev-insecure-key-change-me"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", DEV_SECRET_KEY)

# Refuse to start a production server with the development key rather than
# serve signed cookies and tokens that anyone reading this repository could
# forge. Generate one with:
#   python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
if not DEBUG and SECRET_KEY == DEV_SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a real secret when DJANGO_DEBUG is off."
    )

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# Needed when the API is served over HTTPS behind a proxy (deployment).
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Render sets RENDER_EXTERNAL_HOSTNAME to the service's own hostname
# (e.g. mini-ecommerce-api.onrender.com). Trusting it here means the
# deployed URL never has to be copied into the dashboard by hand, and it
# keeps working if the service is renamed.
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")


# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework.authtoken",  # provides the Token model for token auth
    "django_filters",
    "corsheaders",
]

LOCAL_APPS = [
    "accounts",
    "catalog",
    "orders",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # must sit above CommonMiddleware
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
# SQLite by default. Set DATABASE_URL (e.g. postgres://...) to switch.

DATABASES = {
    "default": dj_database_url.parse(
        os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        # Reuse connections instead of opening one per request. Set
        # DJANGO_DB_CONN_MAX_AGE=0 for a serverless Postgres that suspends
        # when idle (Neon, Supabase), where a connection held open between
        # requests can go stale.
        conn_max_age=int(os.getenv("DJANGO_DB_CONN_MAX_AGE", "600")),
        # Check a reused connection is still usable before handing it to a
        # view, so a dropped connection becomes a retry rather than a 500.
        conn_health_checks=True,
        ssl_require=env_bool("DJANGO_DB_SSL_REQUIRE", False),
    )
}

# Required when connecting through a pooler that runs in transaction mode -
# Neon's "-pooler" host, Supabase's port 6543, PgBouncer generally. Those
# hand each transaction a different backend connection, so the session-level
# state a server-side cursor depends on is not there, and reads fail.
# Leave this off when using a direct connection: without server-side cursors,
# QuerySet.iterator() loads the whole result set into memory.
if env_bool("DJANGO_DB_DISABLE_SERVER_SIDE_CURSORS", False):
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --------------------------------------------------------------------------
# Internationalisation
# --------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True


# --------------------------------------------------------------------------
# Static & media files
# --------------------------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

if not DEBUG:
    # In production WhiteNoise serves the files collected by `collectstatic`
    # and the manifest storage adds cache-busting hashes to their names.
    # In development the staticfiles app already serves them, and enabling
    # this before `collectstatic` has run only produces warnings.
    MIDDLEWARE.insert(2, "whitenoise.middleware.WhiteNoiseMiddleware")
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --------------------------------------------------------------------------
# Django REST Framework
# --------------------------------------------------------------------------

REST_FRAMEWORK = {
    # Token auth is the assignment requirement; session auth is kept so the
    # browsable API stays usable while developing.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Read-only for anonymous visitors, writes require a logged-in user.
    # Individual views tighten this further where needed.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "config.pagination.DefaultPagination",
    "PAGE_SIZE": 10,
}


# --------------------------------------------------------------------------
# CORS (the React frontend is served from a different origin)
# --------------------------------------------------------------------------
# Locally that is the Vite dev server; in production it is the Vercel
# deployment. Browsers block any origin not listed here.

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)

# Vercel gives every preview deployment its own URL, so they cannot be listed
# one by one. A regex can cover them, but it must be anchored and scoped to
# your own project — a pattern like `\.vercel\.app$` would let any site
# hosted on Vercel call this API from a visitor's browser. For example:
#   ^https://mini-ecommerce-[a-z0-9-]+\.vercel\.app$
CORS_ALLOWED_ORIGIN_REGEXES = env_list("CORS_ALLOWED_ORIGIN_REGEXES")


# --------------------------------------------------------------------------
# Production hardening
# --------------------------------------------------------------------------
# Only applied when DEBUG is off, so local development over plain HTTP is
# unaffected. `manage.py check --deploy` reports on these.

if not DEBUG:
    # Most hosts terminate TLS at a proxy and forward this header; without it
    # Django thinks every request is plain HTTP and redirects forever.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    # The platform's own health check reaches the container over plain HTTP,
    # with no X-Forwarded-Proto header, so without this exemption it would be
    # answered with a 301 and the service would be reported unhealthy.
    SECURE_REDIRECT_EXEMPT = [r"^healthz/?$"]

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Start HSTS at one hour. Raise it deliberately once HTTPS is confirmed
    # working - a long max-age is hard to undo in visitors' browsers.
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "3600"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_INCLUDE_SUBDOMAINS", False)
    SECURE_HSTS_PRELOAD = False

    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
