import sys
from .base import DynamicField
from rest_framework.serializers import (
    SerializerMethodField,
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    DecimalField,
    DictField,
    DurationField,
    EmailField,
    FileField,
    FilePathField,
    FloatField,
    HiddenField,
    IPAddressField,
    ImageField,
    IntegerField,
    JSONField,
    ListField,
    RegexField,
    SlugField,
    TimeField,
    URLField,
    UUIDField
)

for cls in (
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    DecimalField,
    DictField,
    DurationField,
    EmailField,
    FileField,
    FilePathField,
    FloatField,
    HiddenField,
    IPAddressField,
    ImageField,
    IntegerField,
    JSONField,
    ListField,
    RegexField,
    SlugField,
    TimeField,
    URLField,
    UUIDField
):
    name = cls.__name__
    new_name = 'Dynamic%s' % name
    new_cls = type(
        new_name,
        (cls, DynamicField),
        {}
    )
    setattr(sys.modules[__name__], new_name, new_cls)


class DynamicMethodField(SerializerMethodField, DynamicField):
    pass
