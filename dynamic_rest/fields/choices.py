from .base import DynamicField
from rest_framework.serializers import ChoiceField
from dynamic_rest.meta import Meta


class DynamicChoicesField(
    DynamicField,
    ChoiceField,
):
    def admin_to_representation(self, value, instance):
        model = self.parent_model
        source = self.source or self.field_name
        choices = Meta(model).get_field(source).choices
        value = getattr(instance, source)
        choice = dict(choices).get(value)
        return super(DynamicChoicesField, self).admin_to_representation(
            choice
        )
