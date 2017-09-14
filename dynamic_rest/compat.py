# flake8: noqa
from __future__ import absolute_import

from django import VERSION

DJANGO110 = VERSION >= (1, 10)

try:
    from django.urls import (
        NoReverseMatch,
        RegexURLPattern,
        RegexURLResolver,
        ResolverMatch,
        Resolver404,
        get_script_prefix,
        reverse,
        reverse_lazy,
        resolve
    )
except ImportError:
    from django.core.urlresolvers import (  # Will be removed in Django 2.0
        NoReverseMatch,
        RegexURLPattern,
        RegexURLResolver,
        ResolverMatch,
        Resolver404,
        get_script_prefix,
        reverse,
        reverse_lazy,
        resolve
    )


def set_many(instance, field, value):
    if DJANGO110:
        field = getattr(instance, field)
        field.set(value)
    else:
        setattr(instance, field, value)
