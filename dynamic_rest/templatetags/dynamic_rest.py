import six
import json
import inflection
from django import template
from django.utils.safestring import mark_safe

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
