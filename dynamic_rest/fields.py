import importlib
import os
import pickle
import pylru
from itertools import chain

from django.conf import settings
from django.db.models import ManyToManyField
from django.utils import six
from django.utils.functional import cached_property
from rest_framework import fields
from rest_framework.exceptions import NotFound, ParseError
from rest_framework.serializers import SerializerMethodField

from dynamic_rest.bases import DynamicSerializerBase
from dynamic_rest.related import RelatedObject


dynamic_settings = getattr(settings, 'DYNAMIC_REST', {})
serializer_cache = pylru.lrucache(
    int(dynamic_settings.get('SERIALIZER_CACHE_MAX_COUNT', 1000))
)


def is_model_field(model, field_name):
    """
    Helper function to get model field.
    """
    try:
        get_model_field(model, field_name)
        return True
    except AttributeError:
        return False


def get_model_field(model, field_name):
    """
    Helper function to get model field, including related fields.
    """
    meta = model._meta
    try:
        return meta.get_field_by_name(field_name)[0]
    except:
        related_objects = {
            o.get_accessor_name(): o
            for o in chain(
                meta.get_all_related_objects(),
                meta.get_all_related_many_to_many_objects()
            )
        }
        if field_name in related_objects:
            return related_objects[field_name]
        else:
            raise AttributeError(
                '%s is not a valid field for %s' % (field_name, model)
            )


def is_field_remote(model, field_name):
    """
    Helper function to determine whether model field is remote or not.
    Remote fields are many-to-many or many-to-one.
    """
    if not hasattr(model, '_meta'):
        # ephemeral model with no metaclass
        return False

    model_field = get_model_field(model, field_name)
    return isinstance(model_field, (ManyToManyField, RelatedObject))


class DynamicField(fields.Field):

    """
    Generic field to capture additional custom field attributes
    """

    def __init__(
        self,
        requires=None,
        deferred=False,
        field_type=None,
        **kwargs
    ):
        """
        Arguments:
            deferred: Whether or not this field is deferred,
                (not included in the response unless specifically requested).
            field_type: Field data type, if not inferrable from model.
            requires: List of fields that this field depends on.
                Processed by the view layer during queryset build time.
        """
        self.requires = requires
        self.deferred = deferred
        self.field_type = field_type
        super(DynamicField, self).__init__(**kwargs)

    def to_representation(self, value):
        return value

    def to_internal_value(self, data):
        return data


class DynamicComputedField(DynamicField):
    pass


class DynamicMethodField(SerializerMethodField, DynamicField):
    pass


class DynamicRelationField(DynamicField):

    """Proxy for a sub-serializer.

    Supports passing in the target serializer as a class or string,
    resolves after binding to the parent serializer.
    """

    SERIALIZER_KWARGS = set(('many', 'source'))

    def __init__(
            self,
            serializer_class,
            many=False,
            queryset=None,
            embed=False,
            **kwargs
    ):
        """
        Arguments:
          serializer_class: Serializer class (or string representation)
            to proxy.
          many: Boolean, if relation is to-many.
          queryset: Default queryset to apply when filtering for related
            objects.
          embed: Always embed related object(s). Will not sideload, and
            will always include full object unless specifically excluded.
        """
        self.kwargs = kwargs
        self._serializer_class = serializer_class
        self.bound = False
        self.queryset = queryset
        self.embed = embed
        if '.' in self.kwargs.get('source', ''):
            raise Exception('Nested relationships are not supported')
        if 'link' in kwargs:
            self.link = kwargs.pop('link')
        super(DynamicRelationField, self).__init__(**kwargs)
        self.kwargs['many'] = many

    def get_model(self):
        return getattr(self.serializer_class.Meta, 'model', None)

    def bind(self, *args, **kwargs):
        if self.bound:  # Prevent double-binding
            return
        super(DynamicRelationField, self).bind(*args, **kwargs)
        self.bound = True
        parent_model = getattr(self.parent.Meta, 'model', None)

        remote = is_field_remote(parent_model, self.source)
        try:
            model_field = parent_model._meta.get_field_by_name(self.source)[0]
        except:
            # model field may not be available for m2o fields with no
            # related_name
            model_field = None

        if 'required' not in self.kwargs and (
                remote or (model_field and
                           (model_field.has_default() or model_field.null))):
            self.required = False
        if 'allow_null' not in self.kwargs and getattr(
                model_field, 'null', False):
            self.allow_null = True

        self.model_field = model_field

    @property
    def root_serializer(self):
        if hasattr(self, '_root_serializer'):
            return self._root_serializer

        if not self.parent:
            # Don't cache, so that we'd recompute if parent is set.
            return None

        node = self
        seen = set()
        while True:
            seen.add(node)
            if getattr(node, 'parent', None):
                node = node.parent
                if node in seen:
                    return None
            else:
                self._root_serializer = node
                break

        return self._root_serializer

    def _get_cached_serializer(self, args, init_args):
        enabled = dynamic_settings.get('ENABLE_SERIALIZER_CACHE', True)

        if not self.parent or not self.field_name or not enabled:
            # Not enough info to use cache.
            return self.serializer_class(*args, **init_args)

        key_dict = {
            'parent': self.parent.__class__.__name__,
            'field': self.field_name,
            'args': args,
            'init_args': init_args
        }
        cache_key = hash(pickle.dumps(key_dict))

        if cache_key not in serializer_cache:
            szr = self.serializer_class(
                *args,
                **init_args
            )
            serializer_cache[cache_key] = szr

        return serializer_cache[cache_key]

    def _get_request_fields_from_parent(self):
        if not self.parent:
            return None

        if not getattr(self.parent, 'request_fields'):
            return None

        if not isinstance(self.parent.request_fields, dict):
            return None

        return self.parent.request_fields.get(self.field_name)

    def _inherit_parent_kwargs(self, kwargs):
        """Extract any necessary attributes from parent serializer to
        propagate down to child serializer.
        """

        if not self.parent or not self._is_dynamic:
            return kwargs

        if 'request_fields' not in kwargs:
            # If 'request_fields' isn't explicitly set, pull it from the
            # parent serializer.
            request_fields = self._get_request_fields_from_parent()
            if request_fields is None:
                # Default to 'id_only' for nested serializers.
                request_fields = True
            kwargs['request_fields'] = request_fields

        if self.embed and kwargs.get('request_fields') is True:
            # If 'embed' then make sure we fetch the full object.
            kwargs['request_fields'] = {}

        if hasattr(self.parent, 'sideload'):
            kwargs['sideload'] = self.parent.sideload

        return kwargs

    def get_serializer(self, *args, **kwargs):
        init_args = {
            k: v for k, v in six.iteritems(self.kwargs)
            if k in self.SERIALIZER_KWARGS
        }

        kwargs = self._inherit_parent_kwargs(kwargs)
        init_args.update(kwargs)

        if self.embed and self._is_dynamic:
            init_args['embed'] = True

        return self._get_cached_serializer(args, init_args)

    @property
    def serializer(self):
        if hasattr(self, '_serializer'):
            return self._serializer

        serializer = self.get_serializer()
        serializer.parent = self
        self._serializer = serializer
        return serializer

    @cached_property
    def _is_dynamic(self):
        return issubclass(
            self.serializer_class,
            DynamicSerializerBase
        )

    def get_attribute(self, instance):
        return instance

    def to_representation(self, instance):
        serializer = self.serializer
        model = serializer.get_model()
        source = self.source
        if not self.kwargs['many'] and serializer.id_only():
            # attempt to optimize by reading the related ID directly
            # from the current instance rather than from the related object
            source_id = '%s_id' % source
            if hasattr(instance, source_id):
                return getattr(instance, source_id)

        if model is None:
            related = getattr(instance, source)
        else:
            try:
                related = getattr(instance, source)
            except model.DoesNotExist:
                return None

        if related is None:
            return None
        try:
            return serializer.to_representation(related)
        except Exception as e:
            # Provide more context to help debug these cases
            if getattr(settings, 'DEBUG', False) or os.environ.get(
                    'DREST_DEBUG', False):
                import traceback
                traceback.print_exc()
            raise Exception(
                "Failed to serialize %s.%s: %s\nObj: %s" %
                (self.parent.__class__.__name__,
                 self.source,
                 str(e),
                    repr(related)))

    def to_internal_value_single(self, data, serializer):
        related_model = serializer.Meta.model
        if isinstance(data, related_model):
            return data
        try:
            instance = related_model.objects.get(pk=data)
        except related_model.DoesNotExist:
            raise NotFound(
                "'%s object with ID=%s not found" %
                (related_model.__name__, data))
        return instance

    def to_internal_value(self, data):
        if self.kwargs['many']:
            serializer = self.serializer.child
            if not isinstance(data, list):
                raise ParseError("'%s' value must be a list" % self.field_name)
            return [self.to_internal_value_single(
                instance, serializer) for instance in data]
        return self.to_internal_value_single(data, self.serializer)

    @property
    def serializer_class(self):
        serializer_class = self._serializer_class
        if not isinstance(serializer_class, six.string_types):
            return serializer_class

        parts = serializer_class.split('.')
        module_path = '.'.join(parts[:-1])
        if not module_path:
            if getattr(self, 'parent', None) is None:
                raise Exception(
                    "Can not load serializer '%s'" % serializer_class +
                    ' before binding or without specifying full path')

            # try the module of the parent class
            module_path = self.parent.__module__

        module = importlib.import_module(module_path)
        serializer_class = getattr(module, parts[-1])

        self._serializer_class = serializer_class
        return serializer_class


class CountField(DynamicComputedField):

    """
    Field that counts number of elements in another specified field.
    """

    def __init__(self, serializer_source, *args, **kwargs):
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
