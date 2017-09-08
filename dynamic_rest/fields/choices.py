from .base import WithRelationalFieldMixin, DynamicField
from rest_framework.serializers import ChoiceField
from django.utils import six


class Choice(six.text_type):
    """
    A string like object that additionally has an associated name.
    We use this for hyperlinked URLs that may render as a named link
    in some contexts, or render as a plain URL in others.
    """
    def __new__(self, value, display, classes=None):
        ret = six.text_type.__new__(self, value)
        ret.display = display
        ret.classes = classes
        return ret

    def __getnewargs__(self):
        return(str(self), self.name, self.classes)

    @property
    def name(self):
        # This ensures that we only called `__str__` lazily,
        # as in some cases calling __str__ on a model instances *might*
        # involve a database lookup.
        return six.text_type(self.display)

    is_choice = True


class DynamicChoicesField(
    WithRelationalFieldMixin,
    ChoiceField,
    DynamicField
):
    def __init__(self, *args, **kwargs):
        self.classes = kwargs.pop('classes', {})
        super(DynamicChoicesField, self).__init__(*args, **kwargs)

    def to_representation(self, value):
        return Choice(
            super(DynamicChoicesField, self).to_representation(value),
            self.choices.get(value, value),
            classes=self.classes.get(value, None)
        )
