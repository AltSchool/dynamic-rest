# flake8: noqa
from __future__ import absolute_import

from django.utils import six
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


try:
    from rest_framework.relations import Hyperlink
except ImportError:
    class Hyperlink(six.text_type):
        """
        A string like object that additionally has an associated name.
        We use this for hyperlinked URLs that may render as a named link
        in some contexts, or render as a plain URL in others.

        Taken from DRF 3.2, used for compatability with DRF 3.1.
        TODO(compat): remove when we drop compat for DRF 3.1.
        """
        def __new__(self, url, obj):
            ret = six.text_type.__new__(self, url)
            ret.obj = obj
            return ret

        def __getnewargs__(self):
            return(str(self), self.name,)

        @property
        def name(self):
            # This ensures that we only called `__str__` lazily,
            # as in some cases calling __str__ on a model instances *might*
            # involve a database lookup.
            return six.text_type(self.obj)

        is_hyperlink = True
