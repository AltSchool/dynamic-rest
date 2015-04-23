import copy
from django.db import models
from dynamic_rest.fields import DynamicRelationField
from dynamic_rest.processors import SideloadingProcessor
from dynamic_rest.wrappers import TaggedDict
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList
from rest_framework import serializers, fields, exceptions


class DynamicListSerializer(serializers.ListSerializer):

    def to_representation(self, data):
        iterable = data.all() if isinstance(data, models.Manager) else data
        return [self.child.to_representation(item) for item in iterable]

    def get_name(self):
        return self.child.get_name()

    def get_plural_name(self):
        return self.child.get_plural_name()

    @property
    def data(self):
        if not hasattr(self, '_sideloaded_data'):
            data = super(DynamicListSerializer, self).data
            if self.child.sideload:
                self._sideloaded_data = ReturnDict(
                    SideloadingProcessor(
                        self,
                        data).data,
                    serializer=self)
            else:
                self._sideloaded_data = ReturnList(data, serializer=self)
        return self._sideloaded_data


class WithDynamicSerializerMixin(object):

    def __new__(cls, *args, **kwargs):
        """
        Custom constructor that sets the ListSerializer to
        DynamicListSerializer to avoid re-evaluating querysets.

        Addresses DRF 3.1.0 bug:
        https://github.com/tomchristie/django-rest-framework/issues/2704)
        """
        meta = getattr(cls, 'Meta', None)
        if not meta:
            meta = type('Meta', (), {})
            cls.Meta = meta
        meta.list_serializer_class = DynamicListSerializer
        return super(
            WithDynamicSerializerMixin, cls).__new__(
            cls, *args, **kwargs)

    def __init__(
            self, instance=None, data=fields.empty, include_fields=None,
            exclude_fields=None, only_fields=None, request_fields=None,
            sideload=False, dynamic=True, **kwargs):
        """
        Custom initializer that builds `request_fields` and
        sets a `ListSerializer` that doesn't re-evaluate querysets.

        Arguments:
          instance: Instance for the serializer base.
          include_fields: List of field names to include.
            Adds to default field set.
          exclude_fields: List of field names to exclude.
            Removes from default field set.
          only_fields: List of field names to render.
            Overrides default field set.
          request_fields: map of field names that supports
            inclusions, exclusions, and nested sideloads.
          dynamic: If False, ignore deferred rules and
            revert to standard DRF `.fields` behavior. (default: True)
          sideload: If False, do not perform sideloading on `.data`.
            (default: False)
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
            for field_name, field in self.get_all_fields().iteritems():
                if field.allow_null is False and field.required is False \
                        and field_name in data and data[field_name] is None:
                    data.pop(field_name)

        kwargs['instance'] = instance
        kwargs['data'] = data
        super(WithDynamicSerializerMixin, self).__init__(**kwargs)

        self.sideload = sideload
        self.dynamic = dynamic
        self.request_fields = request_fields or {}
        self.only_fields = only_fields or []
        include_fields = include_fields or []
        exclude_fields = exclude_fields or []

        self.include_all = False
        if include_fields == '*':
            self.include_all = True
            include_fields = []

        for name in include_fields:
            self.request_fields[name] = True
        for name in exclude_fields:
            self.request_fields[name] = False

    def get_name(self):
        """Returns the serializer name.

        The name must be defined on the Meta class.
        """
        return self.Meta.name

    def get_plural_name(self):
        """Returns the serializer's plural name.

        The plural name may be defined on the Meta class.
        If the plural name is not defined,
        the pluralized name will be returned.
        """
        return getattr(self.Meta, 'plural_name', self.get_name() + 's')

    def get_all_fields(self):
        """Returns the entire serializer field set.

        Does not respect dynamic field inclusions/exclusions.
        """
        if not hasattr(self, '_all_fields'):
            self._all_fields = super(
                WithDynamicSerializerMixin,
                self).get_fields()
        return self._all_fields

    def get_fields(self):
        """Returns the serializer's field set.

        If `dynamic` is True, respects field inclusions/exlcusions.
        Otherwise, reverts back to standard DRF behavior.
        """
        if self.dynamic is False:
            return self.get_all_fields()

        if self.id_only():
            return {}

        serializer_fields = copy.deepcopy(self.get_all_fields())
        request_fields = self.request_fields
        only_fields = set(self.only_fields)

        # return only those fields specified, ignoring deferred rules
        if only_fields:
            return {
                k: v for k, v in serializer_fields.iteritems()
                if k in only_fields}

        # determine fields that are deferred by default
        meta_deferred = set(getattr(self.Meta, 'deferred_fields', []))
        deferred = set(
            [name for name, field in serializer_fields.iteritems()
             if getattr(field, 'deferred', None) is True or name in
             meta_deferred])

        # apply request overrides
        if request_fields:
            for name, include in request_fields.iteritems():
                if name not in serializer_fields:
                    raise exceptions.ParseError(
                        "'%s' is not a valid field name for '%s'" %
                        (name, self.get_name()))
                if include is not False and name in deferred:
                    deferred.remove(name)
                elif include is False:
                    deferred.add(name)

        # remove any deferred fields from the base list
        if not self.include_all:
            for name in deferred:
                serializer_fields.pop(name)

        # inject request_fields into sub-serializers
        for name, field in serializer_fields.iteritems():
            inject = None
            if isinstance(field, serializers.BaseSerializer):
                inject = field
            elif isinstance(field, DynamicRelationField):
                field.parent = self
                inject = field.serializer
            if isinstance(inject, serializers.ListSerializer):
                inject = inject.child
            if inject:
                inject.request_fields = request_fields.get(name, True)

        return serializer_fields

    def to_representation(self, instance):
        if self.dynamic and self.id_only():
            return instance.pk
        else:
            representation = super(
                WithDynamicSerializerMixin,
                self).to_representation(instance)
        # tag the representation with the serializer and instance
        return TaggedDict(representation, serializer=self, instance=instance)

    def save(self, *args, **kwargs):
        update = getattr(self, 'instance', None) is not None
        instance = super(
            WithDynamicSerializerMixin,
            self).save(
            *args,
            **kwargs)
        view = self._context.get('view')
        if update and view:
            # reload the object on update
            # to get around prefetched manager issues
            instance = self.instance = view.get_object()
        return instance

    def id_only(self):
        """Whether or not the serializer should return an ID instead of an object.

        Returns:
          True iff `request_fields` is True
        """
        return self.request_fields is True

    @property
    def data(self):
        if not hasattr(self, '_sideloaded_data'):
            data = super(WithDynamicSerializerMixin, self).data
            self._sideloaded_data = ReturnDict(
                SideloadingProcessor(
                    self,
                    data).data if self.sideload else data,
                serializer=self)
        return self._sideloaded_data


class WithDynamicModelSerializerMixin(WithDynamicSerializerMixin):

    """
    Dynamic serializer methods specific to model-based serializers.
    """

    def get_model(self):
        return self.Meta.model

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
        WithDynamicModelSerializerMixin, serializers.ModelSerializer):

    """
    DRESt-compatible model-based serializer.
    """
    pass


class EphemeralObject(object):

    """ Object that initializes attributes from a dict """

    def __init__(self, values_dict):
        if 'pk' not in values_dict:
            raise Exception("'pk' key is required")
        self.__dict__.update(values_dict)


class DynamicEphemeralSerializer(
        WithDynamicSerializerMixin, serializers.Serializer):

    """
    DREST-compatible baseclass for serializers that aren't model-based.
    """

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
                self).to_representation(instance)
        else:
            data = instance
            instance = EphemeralObject(data)

        if isinstance(data, dict):
            return TaggedDict(data, serializer=self, instance=instance)
        else:
            return data
