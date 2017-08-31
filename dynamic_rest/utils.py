from django.core.urlresolvers import get_script_prefix
from django.utils.six import string_types

FALSEY_STRINGS = (
    '0',
    'false',
    '',
)


def is_truthy(x):
    if isinstance(x, string_types):
        return x.lower() not in FALSEY_STRINGS
    return bool(x)


def unpack(content):
    if not content:
        # empty values pass through
        return content

    keys = [k for k in content.keys() if k != 'meta']
    unpacked = content[keys[0]]
    if hasattr(content, 'serializer'):
        unpacked.serializer = content.serializer
    return unpacked


def get_breadcrumbs(request, view=None):
    from rest_framework.utils.breadcrumbs import (
        get_breadcrumbs as _get_breadcrumbs
    )
    if view:
        breadcrumbs = []
        try:
            instance = view.get_object()
        except:
            instance = None

        serializer_class = getattr(view, 'serializer_class', None)
        if not serializer_class:
            return _get_breadcrumbs(request)
        serializer = serializer_class(instance)
        plural_name = serializer.get_plural_name()
        url = serializer.get_url()
        breadcrumbs.append(('', get_script_prefix()))
        breadcrumbs.append((
            plural_name.title(),
            url
        ))

        if instance:
            url = serializer.get_url(pk=instance.pk)
            breadcrumbs.append((
                getattr(instance, serializer.get_natural_key()),
                url
            ))

        return breadcrumbs
    else:
        return _get_breadcrumbs(request)
