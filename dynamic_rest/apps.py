from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured

from dynamic_rest.conf import settings


class DynamicRestConfig(AppConfig):
    name = "dynamic_rest"
    verbose_name = "Django Dynamic Rest"

    def ready(self):

        if hasattr(settings, "ENABLE_HASHID_FIELDS") and settings.ENABLE_HASHID_FIELDS:
            if not hasattr(settings, "HASHIDS_SALT") or settings.HASHIDS_SALT is None:
                raise ImproperlyConfigured(
                    "You have set ENABLE_HASHID_FIELDS to True in your dynamic_rest setting. "
                    "Then, you must set a HASHIDS_SALT string as well."
                )
