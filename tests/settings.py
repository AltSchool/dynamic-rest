"""Settings for running tests locally."""
import os
from pathlib import Path

import environ

env = environ.Env(
    # set casting, default value
    DEBUG=(bool, True)
)

BASE_DIR = Path(__file__).resolve().parent.parent

environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = "test"
INSTALL_DIR = os.getenv("INSTALL_DIR")

STATIC_URL = "/static/"
STATIC_ROOT = os.environ.get("STATIC_ROOT", INSTALL_DIR if INSTALL_DIR else None)

ENABLE_INTEGRATION_TESTS = os.environ.get("ENABLE_INTEGRATION_TESTS", False)

DEBUG = env("DEBUG")

USE_TZ = False

DATABASES = {"default": env.db(default="sqlite:///db.sqlite3")}

INSTALLED_APPS = (
    "rest_framework",
    "django.contrib.staticfiles",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sites",
    "dynamic_rest",
    "tests",
    "behave_django",
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
