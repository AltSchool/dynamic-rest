from rest_framework import fields
from django.utils import six
from django.utils.safestring import mark_safe

from dynamic_rest.meta import get_model_field
from dynamic_rest.base import DynamicBase
from dynamic_rest.value import Value


class DynamicField(fields.Field, DynamicBase):

    """
    Generic field base to capture additional custom field attributes.
    """

    def __init__(
        self,
        *args,
        **kwargs
    ):
        """
        Arguments:
            deferred: Whether or not this field is deferred.
                Deferred fields are not included in the response,
                unless explicitly requested.
            field_type: Field data type, if not inferrable from model.
            requires: List of fields that this field depends on.
                Processed by the view layer during queryset build time.
            immutable: True if the field cannot be updated
            get_classes: a parent serializer method name that should
                return a list of classes to apply
        """

        self.requires = kwargs.pop('requires', None)
        self.deferred = kwargs.pop('deferred', None)
        self.field_type = kwargs.pop('field_type', None)
        self.immutable = kwargs.pop('immutable', False)
        self.get_classes = kwargs.pop('get_classes', None)
        self.kwargs = kwargs
        super(DynamicField, self).__init__(*args, **kwargs)

    def admin_get_label(self, value):
        return value

    def admin_get_url(self, value):
        # override this to set a link on the returned value
        return None

    def admin_get_classes(self, value):
        # override this to set custom CSS based on value
        instance = getattr(value, '_instance', None)
        parent = self.parent
        getter = self.get_classes
        if getter and instance and parent:
            return getattr(parent, getter)(instance)
        return None

    def admin_get_icon(self, value):
        serializer = self.parent
        name_field = serializer.get_name_field()
        if name_field == self.field_name:
            return serializer.get_icon()

        return None

    def render_admin(self, value):
        if isinstance(value, list) and not isinstance(
            value, six.string_types
        ):
            return mark_safe(
                ', '.join((
                    self.render_admin(v) for v in value
                ))
            )

        # URL link or None
        url = self.admin_get_url(value)
        # list of classes or None
        classes = self.admin_get_classes(value) or []
        classes.append('drest-value')
        # name of an icon or None
        icon = self.admin_get_icon(value)
        # label or None
        label = self.admin_get_label(value)

        tag = 'a' if url else 'span'
        result = label or value

        if icon:
            result = """
                <span>
                    <span class="{0} {0}-{1}"></span>
                    <span>{2}</span>
                </span>
            """.format('fa', icon, result)

        result = '<{0} {3} class="{1}">{2}</{0}>'.format(
            tag,
            ' '.join(classes),
            result,
            ('href="%s"' % url) if url else ''
        )

        return mark_safe(result)

    def render(self, value, format=None):
        if format == 'admin':
            return self.render_admin(value)

        return value

    def to_representation(self, value):
        try:
            return super(DynamicField, self).to_representation(value)
        except:
            return value

    def to_internal_value(self, value):
        try:
            return super(DynamicField, self).to_internal_value(value)
        except:
            return value

    @property
    def parent_model(self):
        if not hasattr(self, '_parent_model'):
            self._parent_model = getattr(self.parent.Meta, 'model', None)
        return self._parent_model

    @property
    def model_field(self):
        if not hasattr(self, '_model_field'):
            try:
                self._model_field = get_model_field(
                    self.parent_model, self.source
                )
            except:
                self._model_field = None
        return self._model_field


class DynamicComputedField(DynamicField):
    def __init__(self, *args, **kwargs):
        kwargs['read_only'] = True
        super(DynamicComputedField, self).__init__(*args, **kwargs)


class CountField(DynamicComputedField):

    """
    Computed field that counts the number of elements in another field.
    """

    def __init__(self, serializer_source, *args, **kwargs):
        """
        Arguments:
            serializer_source: A serializer field.
            unique: Whether or not to perform a count of distinct elements.
        """
        self.field_type = int
        # Use `serializer_source`, which indicates a field at the API level,
        # instead of `source`, which indicates a field at the model level.
        self.serializer_source = serializer_source
        # Set `source` to an empty value rather than the field name to avoid
        # an attempt to look up this field.
        kwargs['source'] = ''
        self.unique = kwargs.pop('unique', True)
        return super(CountField, self).__init__(*args, **kwargs)

    def get_attribute(self, obj):
        source = self.serializer_source
        if source not in self.parent.fields:
            return None
        value = self.parent.fields[source].get_attribute(obj)
        data = self.parent.fields[source].to_representation(value)

        # How to count None is undefined... let the consumer decide.
        if data is None:
            return None

        # Check data type. Technically len() works on dicts, strings, but
        # since this is a "count" field, we'll limit to list, set, tuple.
        if not isinstance(data, (list, set, tuple)):
            raise TypeError(
                "'%s' is %s. Must be list, set or tuple to be countable." % (
                    source, type(data)
                )
            )

        if self.unique:
            # Try to create unique set. This may fail if `data` contains
            # non-hashable elements (like dicts).
            try:
                data = set(data)
            except TypeError:
                pass

        return len(data)


class WithRelationalFieldMixin(object):
    """Mostly code shared by DynamicRelationField and
        DynamicGenericRelationField.
    """

    def _get_request_fields_from_parent(self):
        """Get request fields from the parent serializer."""
        if not self.parent:
            return None

        if not getattr(self.parent, 'request_fields'):
            return None

        if not isinstance(self.parent.request_fields, dict):
            return None

        return self.parent.request_fields.get(self.field_name)
