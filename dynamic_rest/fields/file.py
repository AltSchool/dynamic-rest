from .base import DynamicField
from rest_framework.serializers import FileField


class DynamicFileField(
    DynamicField,
    FileField,
):
    def admin_render(self, instance=None, value=None):
        return '<a class="no-spin" target="_blank" href="%s">%s%s</a>' % (
            value.url,
            '<span class="fa fa-download"></span>',
            str(value)
        )

    def prepare_value(self, instance):
        source = self.source or self.field_name
        value = getattr(instance, source)
        return value
