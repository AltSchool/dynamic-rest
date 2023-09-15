"""Settings for running tests locally."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "test"
INSTALL_DIR = os.getenv("INSTALL_DIR")

STATIC_URL = "/static/"
STATIC_ROOT = os.environ.get("STATIC_ROOT", INSTALL_DIR if INSTALL_DIR else None)

ENABLE_INTEGRATION_TESTS = os.environ.get("ENABLE_INTEGRATION_TESTS", False)

DEBUG = True
USE_TZ = False

DATABASES = {}
if os.environ.get("DATABASE_URL"):
    # remote database
    import dj_database_url

    DATABASES["default"] = dj_database_url.config()
else:
    # local sqlite database file
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
    }

INSTALLED_APPS = (
    "rest_framework",
    "django.contrib.staticfiles",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sites",
    "dynamic_rest",
    "tests",
)

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "dynamic_rest.renderers.DynamicBrowsableAPIRenderer",
    ),
}

ROOT_URLCONF = "tests.urls"

STATICFILES_DIRS = (os.path.abspath(os.path.join(BASE_DIR, "../dynamic_rest/static")),)

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
    }
]

DYNAMIC_REST = {
    "ENABLE_LINKS": True,
    "DEBUG": os.environ.get("DYNAMIC_REST_DEBUG", "false").lower() == "true",
    "ENABLE_HASHID_FIELDS": True,
    "HASHIDS_SALT": "It's your kids, Marty!",
}
