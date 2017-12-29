import importlib
import pickle

from rest_framework.serializers import CreateOnlyDefault, CurrentUserDefault
from django.utils import six
from django.utils.functional import cached_property
from rest_framework.exceptions import (
    APIException,
    NotFound,
    ParseError
)
from rest_framework import fields
from dynamic_rest.conf import settings
from dynamic_rest.meta import (
    get_related_model
)
from .base import (
    DynamicField,
    WithRelationalFieldMixin
)
from dynamic_rest.base import DynamicBase


class DynamicRelationField(WithRelationalFieldMixin, DynamicField):

    """Field proxy for a nested serializer.

    Supports passing in the child serializer as a class or string,
    and resolves to the class after binding to the parent serializer.

    Will proxy certain arguments to the child serializer.

    Attributes:
        SERIALIZER_KWARGS: list of arguments that are passed
            to the child serializer.
    """

    SERIALIZER_KWARGS = set(('many', 'source'))

    def __init__(
            self,
            serializer_class=None,
            many=False,
            queryset=None,
            embed=False,
            sideloading=None,
            debug=False,
            **kwargs
    ):
        """
        Arguments:
            serializer_class: Serializer class (or string representation)
                to proxy.
            many: Boolean, if relation is to-many.
            queryset: Default queryset to apply when filtering for related
                objects.
            sideloading: if True, force sideloading all the way down.
                if False, force embedding all the way down.
                This overrides the "embed" option if set.
            debug: if True, representation will include a meta key with extra
                instance information.
            embed: If True, always embed related object(s). Will not sideload,
                and will include the full object unless specifically excluded.
        """
        self._serializer_class = serializer_class
        self.queryset = queryset
        self.sideloading = sideloading
        self.debug = debug
        self.embed = embed if sideloading is None else not sideloading
        if 'link' in kwargs:
            self.link = kwargs.pop('link')
        super(DynamicRelationField, self).__init__(**kwargs)
        self.kwargs['many'] = self.many = many

    def get_pk_field(self):
        return self.serializer.get_pk_field()

    def get_url(self, pk=None):
        """Get the serializer's endpoint."""
        return self.serializer_class.get_url(pk=pk)

    def get_plural_name(self):
        """Get the serializer's plural name."""
        return self.serializer_class.get_plural_name()

    def get_name_field(self):
        """Get the serializer's name field."""
        return self.serializer_class.get_name_field()

    def get_search_key(self):
        """Get the serializer's search key."""
        return self.serializer_class.get_search_key()

    def get_model(self):
        """Get the serializer's model."""
        return self.serializer_class.get_model()

    def get_value(self, dictionary):
        """Extract value from QueryDict.

        Taken from DRF's ManyRelatedField
        """
        if hasattr(dictionary, 'getlist'):
            # Don't return [] if the update is partial
            if self.field_name not in dictionary:
                if getattr(self.root, 'partial', False):
                    return fields.empty
            return dictionary.getlist(
                self.field_name
            ) if self.many else dictionary.get(self.field_name)
        return dictionary.get(self.field_name, fields.empty)

    @property
    def root_serializer(self):
        """Return the root serializer (serializer for the primary resource)."""
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
        enabled = settings.ENABLE_SERIALIZER_CACHE

        root = self.root_serializer
        if not root or not self.field_name or not enabled:
            # Not enough info to use cache.
            if 'context' not in init_args:
                init_args['context'] = self.context
            return self.serializer_class(*args, **init_args)

        if not hasattr(root, '_descendant_serializer_cache'):
            # Initialize dict to use as cache on root serializer.
            # Arguably this is a Serializer concern, but we'll do it
            # here so it's agnostic to the exact type of the root
            # serializer (i.e. it could be a DRF serializer).
            root._descendant_serializer_cache = {}

        key_dict = {
            'parent': self.parent.__class__.__name__,
            'field': self.field_name,
            'args': args,
            'init_args': init_args
        }
        cache_key = hash(pickle.dumps(key_dict))

        if cache_key not in root._descendant_serializer_cache:
            if 'context' not in init_args:
                init_args['context'] = self.context
            szr = self.serializer_class(
                *args,
                **init_args
            )
            root._descendant_serializer_cache[cache_key] = szr

        return root._descendant_serializer_cache[cache_key]

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

        if hasattr(self.parent, 'sideloading'):
            kwargs['sideloading'] = self.parent.sideloading

        if hasattr(self.parent, 'debug'):
            kwargs['debug'] = self.parent.debug

        return kwargs

    def get_serializer(self, *args, **kwargs):
        """Get an instance of the child serializer."""
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
        """Return True if the child serializer is dynamic."""
        return issubclass(
            self.serializer_class,
            DynamicBase
        )

    def get_attribute(self, instance):
        return instance

    def admin_get_classes(self, instance, value):
        serializer = self.serializer
        getter = serializer.get_class_getter()
        if getter and value is not None:
            if hasattr(serializer, 'child'):
                serializer = serializer.child
            getter = getattr(serializer, getter)
            return getter(value)
        else:
            return super(DynamicRelationField, self).admin_get_classes(
                instance,
                value
            )

    def admin_get_icon(self, instance, value):
        serializer = self.serializer
        if serializer:
            icon = serializer.get_icon()
            label = self.admin_get_label(instance, value)
            if label:
                return icon

        return None

    def admin_get_label(self, instance, value):
        # use the name field
        serializer = self.serializer
        name_field_name = serializer.get_name_field()
        name_field = serializer.get_field(name_field_name)
        source = name_field.source or name_field_name
        sources = source.split('.')
        related = value
        if related:
            for source in sources:
                if source == '*':
                    break
                related = getattr(related, source)
            return related
        else:
            return ''

    def admin_get_url(self, instance, value):
        serializer = self.serializer
        related = value

        if related:
            return serializer.get_url(related.pk)

        return None

    def get_related(self, instance):
        return self.prepare_value(instance)

    def to_representation(self, instance):
        """Represent the relationship, either as an ID or object."""
        serializer = self.serializer
        source = self.source
        if (
            not self.getter and
            not self.many and
            serializer.id_only()
        ):
            # attempt to optimize by reading the related ID directly
            # from the current instance rather than from the related object
            source_id = '%s_id' % source
            value = getattr(instance, source_id, None)
            if value:
                return value

        value = self.prepare_value(instance)

        if value is None:
            return None
        try:
            return serializer.to_representation(value)
        except Exception as e:
            # Provide more context to help debug these cases
            if getattr(serializer, 'debug', False):
                import traceback
                traceback.print_exc()
            raise APIException(
                "Failed to serialize %s.%s: %s\nObj: %s" %
                (
                    self.parent.__class__.__name__,
                    self.source,
                    str(e),
                    repr(value)
                )
            )

    def to_internal_value_single(self, data):
        """Return the underlying object, given the serialized form."""
        model = self.get_model()
        if isinstance(data, model):
            return data
        try:
            instance = model.objects.get(pk=data)
        except model.DoesNotExist:
            raise NotFound(
                '"%s" with ID "%s" not found' %
                (model.__name__, data)
            )
        return instance

    def run_validation(self, data):
        if self.setter:
            if data == fields.empty:
                data = [] if self.kwargs.get('many') else None

            def fn(instance):
                setter = getattr(self.parent, self.setter)
                setter(instance, data)

            self.parent.add_post_save(fn)
            raise fields.SkipField()
        return super(DynamicRelationField, self).run_validation(data)

    def to_internal_value(self, data):
        """Return the underlying object(s), given the serialized form."""
        if self.kwargs['many']:
            if not isinstance(data, list):
                raise ParseError('"%s" value must be a list' % self.field_name)
            return [
                self.to_internal_value_single(
                    instance,
                ) for instance in data
            ]
        return self.to_internal_value_single(data)

    @property
    def serializer_class(self):
        """Get the class of the child serializer.

        Resolves string imports.
        """
        serializer_class = self._serializer_class
        if serializer_class is None:
            from dynamic_rest.routers import DynamicRouter
            serializer_class = DynamicRouter.get_canonical_serializer(
                None,
                model=get_related_model(self.model_field)
            )

        if not isinstance(serializer_class, six.string_types):
            return serializer_class

        parts = serializer_class.split('.')
        module_path = '.'.join(parts[:-1])
        if not module_path:
            if getattr(self, 'parent', None) is None:
                raise Exception(
                    "Can not load serializer '%s'" % serializer_class +
                    ' before binding or without specifying full path'
                )

            # try the module of the parent class
            module_path = self.parent.__module__

        module = importlib.import_module(module_path)
        serializer_class = getattr(module, parts[-1])

        self._serializer_class = serializer_class
        return serializer_class


class DynamicCreatorField(DynamicRelationField):
    def __init__(self, *args, **kwargs):
        kwargs['default'] = CreateOnlyDefault(
            CurrentUserDefault()
        )
        if 'read_only' not in kwargs:
            # default to read_only
            kwargs['read_only'] = True
        super(DynamicCreatorField, self).__init__(*args, **kwargs)
