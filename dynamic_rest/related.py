"""This module provides backwards compatibility for RelatedObject."""
# flake8: noqa

try:
    # Django <= 1.7
    from django.db.models.related import RelatedObject
except:
    # Django >= 1.8
    # See: https://code.djangoproject.com/ticket/21414
    from django.db.models.fields.related import (
        ForeignObjectRel as RelatedObject
    )
