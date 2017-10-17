from __future__ import absolute_import

import six
import json
from django import template
from django.utils.safestring import mark_safe
from dynamic_rest.conf import settings
try:
    from rest_framework.templatetags.rest_framework import format_value
except:
    format_value = lambda x: x

register = template.Library()


@register.filter
def as_id_to_name(value):
    result = {}
    if not isinstance(value, list):
        value = [value]
    for v in value:
        if v:
            name = six.text_type(getattr(v, 'obj', v))
            splits = str(v).split('/')
            if splits[-1]:
                # no trailing slash: /foo/1
                pk = splits[-1]
            else:
                # trailing slash: /foo/1/
                pk = splits[-2]
            result[pk] = name

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
    if callable(getattr(value, 'render', None)):
        return value.render('admin')
    if isinstance(value, list) and value and callable(
        getattr(value[0], 'render', None)
    ):
        return mark_safe(
            ', '.join([
                admin_format_value(v) for v in value
            ])
        )
    return format_value(value)
