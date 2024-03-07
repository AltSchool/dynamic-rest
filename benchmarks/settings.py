"""Benchmark settings."""
import os

import environ

env = environ.Env(
    # set casting, default value
    DEBUG=(bool, True)
)

BASE_DIR = os.path.dirname(__file__)
# Take environment variables from .env file
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# False if not in os.environ because of casting above
DEBUG = env("DEBUG")

SECRET_KEY = "test"
INSTALL_DIR = os.getenv("INSTALL_DIR")
STATIC_URL = "/static/"
STATIC_ROOT = os.getenv("STATIC_ROOT", INSTALL_DIR)

USE_TZ = False

DATABASES = {"default": env.db(default="sqlite:///db.sqlite3")}


MIDDLEWARE_CLASSES = ()

INSTALLED_APPS = (
    "django.contrib.staticfiles",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sites",
    "dynamic_rest",
    "rest_framework",
    "benchmarks_app",
)

ROOT_URLCONF = "benchmarks.urls"

DYNAMIC_REST = {"ENABLE_LINKS": False}
