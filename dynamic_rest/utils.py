from django.core.urlresolvers import get_script_prefix
from django.utils.six import string_types, text_type

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


class DynamicValue(text_type):
    """
    A string like object that additionally has an associated display name.
    We use this for hyperlinked URLs that may render as a named link
    in some contexts, or render as a plain URL in others.
    """
    def __new__(self, value, display, classes='', display_name=False):
        ret = text_type.__new__(self, value)
        ret.value = value
        ret.display = display
        ret.display_name = display_name
        ret.classes = classes
        return ret

    def __getnewargs__(self):
        return(str(self), self.name, self.classes, self.display_name)

    @property
    def name(self):
        # This ensures that we only called `__str__` lazily,
        # as in some cases calling __str__ on a model instances *might*
        # involve a database lookup.
        return text_type(self.display)

    is_dynamic_value = True
