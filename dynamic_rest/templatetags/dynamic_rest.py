from __future__ import absolute_import

import json
from uuid import UUID
from django import template
from django.utils.safestring import mark_safe
from django.utils import six
from dynamic_rest.conf import settings
from rest_framework.fields import get_attribute
try:
    from rest_framework.templatetags.rest_framework import format_value
except:
    format_value = lambda x: x

register = template.Library()


@register.filter
def as_id_to_name(field):
    serializer = field.serializer
    name_field_name = serializer.get_name_field()
    name_source = serializer.get_field(
        name_field_name
    ).source or name_field_name
    source_attrs = name_source.split('.')
    value = field.value

    if not (
        isinstance(value, list)
        and not isinstance(value, six.string_types)
        and not isinstance(value, UUID)
    ):
        value = [value]

    result = {}
    for v in value:
        if v:
            if hasattr(v, 'instance'):
                instance = v.instance
            else:
                instance = serializer.get_model().objects.get(
                    pk=str(v)
                )
            result[str(instance.pk)] = get_attribute(instance, source_attrs)
    return mark_safe(json.dumps(result))


@register.simple_tag
def get_value_from_dict(d, key):
    return d.get(key, '')


@register.filter
def format_key(key):
    return key


@register.simple_tag
def drest_settings(key):
    return getattr(settings, key)


@register.filter
def to_json(value):
    return json.dumps(value)


@register.filter
def admin_format_value(value):
    return format_value(value)


@register.simple_tag
def get_field_value(serializer, instance, key, idx=None):
    return serializer.get_field_value(key, instance)


@register.filter
def render_field_value(field):
    value = getattr(field, 'get_rendered_value', lambda *x: field)()
    return mark_safe(value)
