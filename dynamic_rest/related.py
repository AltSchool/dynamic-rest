"""This module provides backwards compatibility for RelatedObject."""
# flake8: noqa

from django.db.models.fields.related import (
    ForeignObjectRel as RelatedObject
)
