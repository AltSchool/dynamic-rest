"""This module contains custom serializer classes."""
import copy

import inflection
from django.db import models
from django.utils import six
from django.utils.functional import cached_property
from rest_framework import exceptions, fields, serializers
from rest_framework.fields import SkipField
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList

from dynamic_rest.bases import DynamicSerializerBase
from dynamic_rest.conf import settings
from dynamic_rest.fields import DynamicRelationField
from dynamic_rest.links import merge_link_object
from dynamic_rest.processors import SideloadingProcessor
from dynamic_rest.tagged import tag_dict


class DynamicListSerializer(serializers.ListSerializer):
    """Custom ListSerializer class.

    This implementation delegates DREST-specific methods to
    the child serializer and performs post-processing before
    returning the data.
    """
    def __init__(self, *args, **kwargs):
        super(DynamicListSerializer, self).__init__(*args, **kwargs)
        self.child.parent = self

    def to_representation(self, data):
        iterable = data.all() if isinstance(data, models.Manager) else data
        return [self.child.to_representation(item) for item in iterable]

    def get_model(self):
        """Get the child's model."""
        return self.child.get_model()

    def get_name(self):
        """Get the child's name."""
        return self.child.get_name()

    def get_plural_name(self):
        """Get the child's plural name."""
        return self.child.get_plural_name()

    def id_only(self):
        """Get the child's rendering mode."""
        return self.child.id_only()

    @property
    def data(self):
        """Get the data, after performing post-processing if necessary."""
        if not hasattr(self, '_sideloaded_data'):
            data = super(DynamicListSerializer, self).data
            if self.child.sideload:
                self._sideloaded_data = ReturnDict(
                    SideloadingProcessor(
                        self,
                        data
                    ).data,
                    serializer=self
                )
            else:
                self._sideloaded_data = ReturnList(data, serializer=self)
        return self._sideloaded_data


class WithDynamicSerializerMixin(DynamicSerializerBase):
    """Base class for DREST serializers.

    This class provides support for dynamic field inclusions/exclusions.
    """
    def __new__(cls, *args, **kwargs):
        """
        Custom constructor that sets the ListSerializer to
        DynamicListSerializer to avoid re-evaluating querysets.

        Addresses DRF 3.1.0 bug:
        https://github.com/tomchristie/django-rest-framework/issues/2704
        """
        meta = getattr(cls, 'Meta', None)
        if not meta:
            meta = type('Meta', (), {})
            cls.Meta = meta
        meta.list_serializer_class = DynamicListSerializer
        return super(
            WithDynamicSerializerMixin, cls
        ).__new__(
            cls, *args, **kwargs
        )

    def __init__(
            self,
            instance=None,
            data=fields.empty,
            only_fields=None,
            include_fields=None,
            exclude_fields=None,
            request_fields=None,
            sideload=False,
            dynamic=True,
            embed=False,
            **kwargs
    ):
        """
        Custom initializer that builds `request_fields`.

        Arguments:
            instance: Instance to be managed by the serializer.
            only_fields: List of field names to render.
            include_fields: List of field names to include.
            exclude_fields: List of field names to exclude.
            request_fields: map of field names that supports
                inclusions, exclusions, and nested sideloads.
            sideload: If False, do not perform any sideloading at this level.
            embed: If True, force the current representation to be embedded.
            dynamic: If False, ignore deferred rules and
                revert to standard DRF `.fields` behavior.
        """
        name = self.get_name()
        if data is not fields.empty and name in data and len(data) == 1:
            # support POST/PUT key'd by resource name
            data = data[name]

        if data is not fields.empty:
            # if a field is nullable but not required and the implementation
            # passes null as a value, remove the field from the data
            # this addresses the frontends that send
            # undefined resource fields as null on POST/PUT
            for field_name, field in six.iteritems(self.get_all_fields()):
                if (
                    field.allow_null is False and field.required is False and
                    field_name in data and data[field_name] is None
                ):
                    data.pop(field_name)

        kwargs['instance'] = instance
        kwargs['data'] = data
        super(WithDynamicSerializerMixin, self).__init__(**kwargs)

        self.sideload = sideload
        self.dynamic = dynamic
        self.request_fields = request_fields or {}
        self.embed = embed

        self._dynamic_init(only_fields, include_fields, exclude_fields)
        self.enable_optimization = settings.ENABLE_SERIALIZER_OPTIMIZATIONS

    def _dynamic_init(self, only_fields, include_fields, exclude_fields):
        """
        Modifies `request_fields` via higher-level dynamic field interfaces.

        Arguments:
            only_fields: List of field names to render.
                All other fields will be deferred (respects sideloads).
            include_fields: List of field names to include.
                Adds to default field set, (respects sideloads).
                `*` means include all fields.
            exclude_fields: List of field names to exclude.
                Removes from default field set. If set to '*', all fields are
                removed, except for ones that are explicitly included.
        """

        if not self.dynamic:
            return

        if (
            isinstance(self.request_fields, dict)
            and self.request_fields.pop('*', None) is False
        ):
            exclude_fields = '*'

        only_fields = set(only_fields or [])
        include_fields = include_fields or []
        exclude_fields = exclude_fields or []
        all_fields = set(self.get_all_fields().keys())

        if only_fields:
            exclude_fields = '*'
            include_fields = only_fields

        if exclude_fields == '*':
            # First exclude all, then add back in explicitly included fields.
            include_fields = set(
                list(include_fields) + [
                    field for field, val in six.iteritems(self.request_fields)
                    if val or val == {}
                ]
            )
            exclude_fields = all_fields - include_fields
        elif include_fields == '*':
            include_fields = all_fields

        for name in exclude_fields:
            self.request_fields[name] = False

        for name in include_fields:
            if not isinstance(self.request_fields.get(name), dict):
                # not sideloading this field
                self.request_fields[name] = True

    @classmethod
    def get_model(cls):
        """Get the model, if the serializer has one.

        Model serializers should implement this method.
        """
        return None

    @classmethod
    def get_name(cls):
        """Get the serializer name.

        The name can be defined on the Meta class or will be generated
        automatically from the model name.
        """
        if not hasattr(cls.Meta, 'name'):
            class_name = getattr(cls.get_model(), '__name__', None)
            setattr(
                cls.Meta,
                'name',
                inflection.underscore(class_name) if class_name else None
            )

        return cls.Meta.name

    @classmethod
    def get_plural_name(cls):
        """Get the serializer's plural name.

        The plural name may be defined on the Meta class.
        If the plural name is not defined,
        the pluralized form of the name will be returned.
        """
        if not hasattr(cls.Meta, 'plural_name'):
            setattr(
                cls.Meta,
                'plural_name',
                inflection.pluralize(cls.get_name())
            )
        return cls.Meta.plural_name

    def get_all_fields(self):
        """Returns the entire serializer field set.

        Does not respect dynamic field inclusions/exclusions.
        """
        if not hasattr(self, '_all_fields'):
            self._all_fields = super(
                WithDynamicSerializerMixin,
                self
            ).get_fields()
            for k, field in six.iteritems(self._all_fields):
                field.field_name = k
                field.parent = self
        return self._all_fields

    def _get_deferred_field_names(self, serializer_fields):
        """Return set of deferred field names."""
        meta_deferred = set(getattr(self.Meta, 'deferred_fields', []))
        return {
            name for name, field in six.iteritems(serializer_fields)
            if getattr(field, 'deferred', None) is True or name in
            meta_deferred
        }

    def get_fields(self):
        """Returns the serializer's field set.

        If `dynamic` is True, respects field inclusions/exlcusions.
        Otherwise, reverts back to standard DRF behavior.
        """
        all_fields = self.get_all_fields()
        if self.dynamic is False:
            return all_fields

        if self.id_only():
            return {}

        serializer_fields = copy.deepcopy(all_fields)
        request_fields = self.request_fields
        deferred = self._get_deferred_field_names(serializer_fields)

        # apply request overrides
        if request_fields:
            for name, include in six.iteritems(request_fields):
                if name not in serializer_fields:
                    raise exceptions.ParseError(
                        "'%s' is not a valid field name for '%s'" %
                        (name, self.get_name()))
                if include is not False and name in deferred:
                    deferred.remove(name)
                elif include is False:
                    deferred.add(name)

        for name in deferred:
            serializer_fields.pop(name)

        return serializer_fields

    def get_link_fields(self):
        """Construct dict of name:field for linkable fields."""
        if not hasattr(self, '_link_fields'):
            all_fields = self.get_all_fields()
            self._link_fields = {
                name: field for name, field in six.iteritems(all_fields)
                if isinstance(field, DynamicRelationField)
                and getattr(field, 'link', True)
                and not (
                    # Skip sideloaded fields
                    name in self.fields
                    and not field.serializer.id_only()
                ) and not (
                    # Skip included single relations
                    # TODO: Use links, when we can generate canonical URLs
                    name in self.fields
                    and not getattr(field.serializer, 'many', False)
                )
            }

        return self._link_fields

    @cached_property
    def _readable_fields(self):
        # NOTE: Copied from DRF, exists in 3.2.x but not 3.1
        return [
            field for field in self.fields.values()
            if not field.write_only
        ]

    def _faster_to_representation(self, instance):
        """Modified to_representation with optimizations.

        1) Returns a plain old dict as opposed to OrderedDict.
            (Constructing ordered dict is ~100x slower than `{}`.)
        2) Ensure we use a cached list of fields
            (this optimization exists in DRF 3.2 but not 3.1)

        Arguments:
            instance: a model instance or data object
        Returns:
            Dict of primitive datatypes.
        """

        ret = {}
        fields = self._readable_fields

        for field in fields:
            try:
                attribute = field.get_attribute(instance)
            except SkipField:
                continue

            if attribute is None:
                # We skip `to_representation` for `None` values so that
                # fields do not have to explicitly deal with that case.
                ret[field.field_name] = None
            else:
                ret[field.field_name] = field.to_representation(attribute)

        return ret

    def to_representation(self, instance):
        """Modified to_representation method.

        Arguments:
            instance: A model instance or data object.
        Returns:
            Instance ID if the serializer is meant to represent its ID.
            Otherwise, a tagged data dict representation.
        """
        if self.id_only():
            return instance.pk
        else:
            if self.enable_optimization:
                representation = self._faster_to_representation(instance)
            else:
                representation = super(
                    WithDynamicSerializerMixin,
                    self
                ).to_representation(instance)

            if settings.ENABLE_LINKS:
                # TODO: Make this function configurable to support other
                #       formats like JSON API link objects.
                representation = merge_link_object(
                    self, representation, instance
                )

        # tag the representation with the serializer and instance
        return tag_dict(
            representation,
            serializer=self,
            instance=instance,
            embed=self.embed
        )

    def save(self, *args, **kwargs):
        """Serializer save that address prefetch issues."""
        update = getattr(self, 'instance', None) is not None
        instance = super(
            WithDynamicSerializerMixin,
            self
        ).save(
            *args,
            **kwargs
        )
        view = self._context.get('view')
        if update and view:
            # Reload the object on update
            # to get around prefetch cache issues
            instance = self.instance = view.get_object()
        return instance

    def id_only(self):
        """Check whether the serializer should return an ID instead of an object.

        Returns:
            True if and only if `request_fields` is True.
        """
        return self.dynamic and self.request_fields is True

    @property
    def data(self):
        if not hasattr(self, '_sideloaded_data'):
            data = super(WithDynamicSerializerMixin, self).data
            self._sideloaded_data = ReturnDict(
                SideloadingProcessor(
                    self,
                    data
                ).data if self.sideload else data,
                serializer=self
            )
        return self._sideloaded_data


class WithDynamicModelSerializerMixin(WithDynamicSerializerMixin):

    """Adds DREST serializer methods specific to model-based serializers."""

    @classmethod
    def get_model(cls):
        return cls.Meta.model

    def get_id_fields(self):
        """
        Called to return a list of fields consisting of, at minimum,
        the PK field name. The output of this method is used to
        construct a Prefetch object with a .only() queryset
        when this field is not being sideloaded but we need to
        return a list of IDs.
        """
        model = self.get_model()

        out = [model._meta.pk.name]  # get PK field name

        # If this is being called, it means it
        # is a many-relation  to its parent.
        # Django wants the FK to the parent,
        # but since accurately inferring the FK
        # pointing back to the parent is less than trivial,
        # we will just pull all ID fields.
        # TODO: We also might need to return all non-nullable fields,
        #    or else it is possible Django will issue another request.
        for field in model._meta.fields:
            if isinstance(field, models.ForeignKey):
                out.append(field.name + '_id')

        return out


class DynamicModelSerializer(
    WithDynamicModelSerializerMixin,
    serializers.ModelSerializer
):

    """DREST-compatible model-based serializer."""
    pass


class EphemeralObject(object):

    """Object that initializes attributes from a dict."""

    def __init__(self, values_dict):
        if 'pk' not in values_dict:
            raise Exception("'pk' key is required")
        self.__dict__.update(values_dict)


class DynamicEphemeralSerializer(
    WithDynamicSerializerMixin,
    serializers.Serializer
):

    """DREST-compatible baseclass for non-model serializers."""

    def to_representation(self, instance):
        """
        Provides post processing. Sub-classes should implement their own
        to_representation method, but pass the resulting dict through
        this function to get tagging and field selection.

        Arguments:
            instance: Serialized dict, or object. If object,
                it will be serialized by the super class's
                to_representation() method.
        """

        if not isinstance(instance, dict):
            data = super(
                DynamicEphemeralSerializer,
                self
            ).to_representation(instance)
        else:
            data = instance
            instance = EphemeralObject(data)

        if self.id_only():
            return data
        else:
            return tag_dict(data, serializer=self, instance=instance)
