import sys
from .base import DynamicField
from rest_framework import serializers

for cls_name in (
    'BooleanField',
    'CharField',
    'DateField',
    'DateTimeField',
    'DecimalField',
    'DictField',
    'EmailField',
    'FilePathField',
    'FloatField',
    'HiddenField',
    'IPAddressField',
    'ImageField',
    'IntegerField',
    'JSONField',
    'ListField',
    'RegexField',
    'SlugField',
    'TimeField',
    'URLField',
    'UUIDField',
):
    cls = getattr(serializers, cls_name, None)
    if not cls:
        continue

    new_name = 'Dynamic%s' % cls_name
    new_cls = type(
        new_name,
        (DynamicField, cls),
        {}
    )
    setattr(sys.modules[__name__], new_name, new_cls)


class DynamicMethodField(
    serializers.SerializerMethodField,
    DynamicField
):
    pass
