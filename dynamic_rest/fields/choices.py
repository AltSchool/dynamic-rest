from .base import DynamicField
from rest_framework.serializers import ChoiceField
from dynamic_rest.utils import DynamicValue


class DynamicChoicesField(
    ChoiceField,
    DynamicField
):
    def __init__(self, *args, **kwargs):
        self.class_choices = kwargs.pop(
            'class_choices', {}
        )
        super(DynamicChoicesField, self).__init__(*args, **kwargs)

    def to_representation(self, value):
        return DynamicValue(
            super(DynamicChoicesField, self).to_representation(value),
            self.choices.get(value, value),
            classes=self.class_choices.get(value, None),
            display_name=True
        )
