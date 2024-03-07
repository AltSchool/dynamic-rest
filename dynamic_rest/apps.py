"""Django app config for dynamic_rest."""
from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured

from dynamic_rest.conf import settings


class DynamicRestConfig(AppConfig):
    """Django app config for dynamic_rest."""

    name = "dynamic_rest"
    verbose_name = "Django Dynamic Rest"

    def ready(self):
        """Perform app config checks."""
        if hasattr(settings, "ENABLE_HASHID_FIELDS") and settings.ENABLE_HASHID_FIELDS:
            if not hasattr(settings, "HASHIDS_SALT") or settings.HASHIDS_SALT is None:
                raise ImproperlyConfigured(
                    "ENABLED_HASHID_FIELDS is True in your settings,"
                    "but no HASHIDS_SALT string was set!"
                )
