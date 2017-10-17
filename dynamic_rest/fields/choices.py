from .base import DynamicField
from rest_framework.serializers import ChoiceField
from dynamic_rest.meta import Meta
from dynamic_rest.value import Value


class DynamicChoicesField(
    DynamicField,
    ChoiceField,
):

    def get_attribute(self, instance):
        return instance

    def to_representation(self, instance):
        model = self.parent_model
        source = self.source or self.field_name
        choices = Meta(model).get_field(source).choices
        value = getattr(instance, source)
        choices_as_dict = dict(choices)
        return Value(
            choices_as_dict.get(value),
            field=self,
            instance=instance
        )
