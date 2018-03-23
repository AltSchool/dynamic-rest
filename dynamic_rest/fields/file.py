from .base import DynamicField
from rest_framework.serializers import FileField


class DynamicFileField(
    DynamicField,
    FileField,
):
    def admin_render(self, instance=None, value=None):
        return '<a class="no-spin" target="_blank" href="%s">%s%s</a>' % (
            '<span class="fa fa-download"></span>',
            value.url,
            str(value)
        )

    def prepare_value(self, instance):
        model = self.parent_model
        source = self.source or self.field_name
        value = getattr(instance, source)
        return value

