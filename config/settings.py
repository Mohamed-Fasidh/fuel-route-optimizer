import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "assessment-only-secret")
DEBUG = os.getenv("DEBUG", "1") == "1"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "api",
]

MIDDLEWARE = [
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
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
}

REDIS_URL = os.getenv("REDIS_URL", "").strip()
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "fuel-route-optimizer",
        }
    }

OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
NOMINATIM_BASE_URL = os.getenv(
    "NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org"
)
NOMINATIM_USER_AGENT = os.getenv(
    "NOMINATIM_USER_AGENT",
    "fuel-route-optimizer/1.0 (assessment; replace-with-email)",
)

ROUTE_CACHE_SECONDS = int(os.getenv("ROUTE_CACHE_SECONDS", "86400"))
GEOCODE_CACHE_SECONDS = int(os.getenv("GEOCODE_CACHE_SECONDS", "604800"))
MAX_STATION_DISTANCE_MILES = float(
    os.getenv("MAX_STATION_DISTANCE_MILES", "5")
)
FUEL_MPG = float(os.getenv("FUEL_MPG", "10"))
FUEL_RANGE_MILES = float(os.getenv("FUEL_RANGE_MILES", "500"))
FUEL_TANK_GALLONS = float(os.getenv("FUEL_TANK_GALLONS", "50"))
