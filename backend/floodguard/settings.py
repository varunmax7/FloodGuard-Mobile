"""
FloodGuard Django Configuration
"""
import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Core ──────────────────────────────────────────────────────────────────────
SECRET_KEY = config("SECRET_KEY", default="dev-insecure-key-do-not-use-in-prod")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    # Leading-dot forms are Django wildcards — accept any *.ngrok-free.app /
    # *.ngrok.io subdomain so tunnels rotate freely without a restart.
    default="localhost,127.0.0.1,.ngrok-free.app,.ngrok-free.dev,.ngrok.io,.ngrok.app,.ngrok.dev",
).split(",")

# Trust ngrok origins for CSRF (admin login and any browser POST going
# through the tunnel).
CSRF_TRUSTED_ORIGINS = [
    "https://*.ngrok-free.app",
    "https://*.ngrok-free.dev",
    "https://*.ngrok.io",
    "https://*.ngrok.app",
    "https://*.ngrok.dev",
]

# ── Apps ──────────────────────────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",            # GeoDjango
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "django_celery_beat",
    "django_celery_results",
    "storages",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.geo",
    "apps.risk",
    "apps.ingest",
    "apps.reports",
    "apps.alerts",
    "apps.adminapi",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "floodguard.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "floodguard.wsgi.application"

# ── Database (PostGIS) ────────────────────────────────────────────────────────

DATABASE_URL = config(
    "DATABASE_URL",
    default="postgis://floodguard:floodguard@localhost:5432/floodguard",
)
DATABASES = {
    "default": dj_database_url.parse(DATABASE_URL, conn_max_age=60)
}
DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"

# ── Custom User Model ─────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

# ── Password validation ───────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Internationalization ──────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ── Static / Media ────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── REST Framework ────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "200/hour",
        "user": "2000/hour",
        "otp_request": "5/hour",
        "otp_verify": "10/hour",
    },
}

# ── SimpleJWT ─────────────────────────────────────────────────────────────────

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in config(
        "CORS_ALLOWED_ORIGINS",
        default="http://localhost:5173,http://localhost:3000",
    ).split(",")
    if o.strip().startswith(("http://", "https://"))
]
CORS_ALLOW_CREDENTIALS = True

# Allow any localhost port in dev (Flutter web uses a random port)
if DEBUG:
    CORS_ALLOWED_ORIGIN_REGEXES = [r"^http://localhost:\d+$"]

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "django-cache"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_ALWAYS_EAGER = DEBUG  # Run tasks synchronously in local dev

# ── Storage (S3 / Cloudflare R2) ──────────────────────────────────────────────
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", default="floodguard-media")
# Custom endpoint (e.g. Cloudflare R2). Only set the attribute when non-empty —
# passing an empty string makes boto3 raise ValueError("Invalid endpoint: ").
_s3_endpoint = config("AWS_S3_ENDPOINT_URL", default="").strip()
if _s3_endpoint:
    AWS_S3_ENDPOINT_URL = _s3_endpoint
AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="auto")
AWS_S3_FILE_OVERWRITE = False
# Private ACL so photos are served only via pre-signed URLs (not public)
AWS_DEFAULT_ACL = "private"
AWS_QUERYSTRING_AUTH = True
AWS_QUERYSTRING_EXPIRE = 3600          # signed URL valid for 1 hour

USE_S3_STORAGE = config("USE_S3_STORAGE", default=False, cast=bool)
if USE_S3_STORAGE or (AWS_ACCESS_KEY_ID and _s3_endpoint):
    STORAGES["default"] = {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"}

# ── Cache — Redis in prod, LocMem in dev ──────────────────────────────────────
# NOTE: Django's built-in RedisCache passes OPTIONS as kwargs to redis.Redis(),
# so it must NOT contain django-redis-specific keys like CLIENT_CLASS.
CACHE_URL = config("CACHE_URL", default="")
if CACHE_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": CACHE_URL,
            "KEY_PREFIX": "fg",
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "floodguard-default",
        }
    }

# ── Geo ───────────────────────────────────────────────────────────────────────
# H3 resolution used by build_hexgrid and every lat/lng → cell lookup.
# Must match the res the hexgrid was built at, or point → hex resolution fails.
#   res 9 (~174 m edge)  — city-scale (GHMC / Hyderabad legacy)
#   res 7 (~1.2 km edge) — state-scale (Assam)
H3_RESOLUTION = config("H3_RESOLUTION", default=7, cast=int)

# ── Ingest pipeline ───────────────────────────────────────────────────────────
# INGEST_MOCK=True → tasks use synthetic fixture data (no network calls).
# Per-feed overrides let us go live one feed at a time.
INGEST_MOCK = config("INGEST_MOCK", default=True, cast=bool)
FORECAST_LIVE = config("FORECAST_LIVE", default=True, cast=bool)   # Open-Meteo, no key
RADAR_LIVE = config("RADAR_LIVE", default=True, cast=bool)         # RainViewer, no key
AWS_LIVE = config("AWS_LIVE", default=True, cast=bool)             # Open-Meteo, no key
ECMWF_API_KEY = config("ECMWF_API_KEY", default="")   # unused with Open-Meteo, kept for compat
TGDPS_API_URL = config("TGDPS_API_URL", default="")
TGDPS_API_KEY = config("TGDPS_API_KEY", default="")
RADAR_API_URL = config("RADAR_API_URL", default="")
RADAR_API_KEY = config("RADAR_API_KEY", default="")

# ── Risk freshness ────────────────────────────────────────────────────────────
# Public /risk/* endpoints return 503 STALE_FORECAST when the newest RiskSnapshot
# is older than this. Prevents serving stale seeded values as if they were live.
RISK_FRESHNESS_HOURS = config("RISK_FRESHNESS_HOURS", default=2, cast=int)

# ── Firebase ──────────────────────────────────────────────────────────────────
FIREBASE_CREDENTIALS_PATH = config("FIREBASE_CREDENTIALS_PATH", default="")
FIREBASE_CREDENTIALS_JSON = config("FIREBASE_CREDENTIALS_JSON", default="")

# ── Logging ───────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {module} — {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "floodguard": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}

# ── Sentry (disabled when DSN is empty) ───────────────────────────────────────
SENTRY_DSN = config("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk  # noqa: E402
    from sentry_sdk.integrations.celery import CeleryIntegration  # noqa: E402
    from sentry_sdk.integrations.django import DjangoIntegration  # noqa: E402
    from sentry_sdk.integrations.logging import LoggingIntegration  # noqa: E402

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(transaction_style="url"),
            CeleryIntegration(monitor_beat_tasks=True),
            LoggingIntegration(level=None, event_level="ERROR"),
        ],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.0,
        environment="production" if not DEBUG else "development",
        send_default_pii=False,
    )

# ── Production security headers (no-op in dev) ────────────────────────────────
if not DEBUG:
    # SSL redirect is opt-in — flip on once the ALB has an HTTPS listener with
    # an ACM cert. While the ALB is HTTP-only, redirecting to HTTPS causes ALB
    # health checks (and every real request) to receive a 301 → unhealthy.
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
    if SECURE_SSL_REDIRECT:
        SECURE_HSTS_SECONDS = 31536000
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Health probes must never be redirected — ALB target-group health checks
    # expect a 2xx response on /api/v1/readyz/.
    SECURE_REDIRECT_EXEMPT = [r"^api/v1/livez/?$", r"^api/v1/readyz/?$", r"^api/v1/health/?$"]
    CORS_ALLOWED_ORIGINS = [
        o.strip() for o in config("CORS_ALLOWED_ORIGINS", default="").split(",")
        if o.strip().startswith(("http://", "https://"))
    ]
    # Remove blanket localhost CORS in prod
    CORS_ALLOWED_ORIGIN_REGEXES = []
