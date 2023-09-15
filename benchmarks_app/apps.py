"""Benchmark app config."""
from django.apps import AppConfig


class BenchmarksAppConfig(AppConfig):
    """Benchmark app config."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "benchmarks_app"
