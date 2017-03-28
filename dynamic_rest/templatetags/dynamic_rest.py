import six
import json
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
            name = six.text_type(v.obj)
            pk = v.split('/')[-1]
            result[pk] = name
    return mark_safe(json.dumps(result))
