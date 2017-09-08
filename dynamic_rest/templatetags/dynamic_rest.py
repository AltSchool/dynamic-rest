from __future__ import absolute_import

import six
import json
import inflection
from django import template
from django.utils.safestring import mark_safe
from dynamic_rest.conf import settings
from rest_framework.templatetags.rest_framework import format_value

register = template.Library()


@register.filter
def as_id_to_name(value):
    result = {}
    if not isinstance(value, list):
        value = [value]
    for v in value:
        if v:
            name = six.text_type(getattr(v, 'obj', v))
            splits = v.split('/')
            if splits[-1]:
                # no trailing slash: /foo/1
                pk = splits[-1]
            else:
                # trailing slash: /foo/1/
                pk = splits[-2]
            result[pk] = name

    return mark_safe(json.dumps(result))


@register.filter
def get_value_from_dict(d, key):
    return d[key]


@register.filter
def format_key(key):
    return inflection.humanize(key)


@register.simple_tag
def drest_settings(key):
    return getattr(settings, key)


@register.filter
def to_json(value):
    return json.dumps(value)


@register.filter
def drest_format_value(value):
    if getattr(value, 'is_dynamic_value', None):
        classes = value.classes
        value = value.name if value.display_name else value.value
        if classes:
            return mark_safe(
                '<span class="%s">%s</span>' % (
                    classes,
                    drest_format_value(value)
                )
            )
        else:
            return drest_format_value(value)
    return format_value(value)
