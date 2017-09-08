from rest_framework.serializers import SerializerMethodField
from rest_framework import fields
from dynamic_rest.meta import get_model_field


class DynamicField(fields.Field):

    """
    Generic field base to capture additional custom field attributes.
    """

    def __init__(
        self,
        requires=None,
        deferred=None,
        field_type=None,
        immutable=False,
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
        """
        self.requires = requires
        self.deferred = deferred
        self.field_type = field_type
        self.immutable = immutable
        self.kwargs = kwargs
        super(DynamicField, self).__init__(**kwargs)

    def to_representation(self, value):
        return value

    def to_internal_value(self, value):
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


class DynamicMethodField(SerializerMethodField, DynamicField):
    pass


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
