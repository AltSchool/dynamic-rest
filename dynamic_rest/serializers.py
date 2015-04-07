from collections import OrderedDict
from django.db import models
from dynamic_rest.fields import DynamicRelationField
from dynamic_rest.processors import SideloadingProcessor
from rest_framework import serializers, fields, exceptions


class DynamicListSerializer(serializers.ListSerializer):

  def to_representation(self, data):
    iterable = data.all() if isinstance(data, models.Manager) else data
    return [self.child.to_representation(item) for item in iterable]

  @property
  def data(self):
    if not hasattr(self, '_sideloaded_data'):
      data = super(DynamicListSerializer, self).data
      self._sideloaded_data = SideloadingProcessor(self, data).data
    return self._sideloaded_data

class DynamicModelSerializer(serializers.ModelSerializer):

  def __new__(cls, *args, **kwargs):
    """
    Custom constructor that sets the ListSerializer to DynamicListSerializer
    to avoid re-evaluating querysets.

    Addresses DRF 3.1.0 bug: https://github.com/tomchristie/django-rest-framework/issues/2704)
    """
    meta = getattr(cls, 'Meta', None)
    if not meta:
      meta = type('Meta', (), {})
      cls.Meta = meta
    meta.list_serializer_class = DynamicListSerializer
    return super(DynamicModelSerializer, cls).__new__(cls, *args, **kwargs)

  def __init__(self, instance=None, data=fields.empty, include_fields=None, exclude_fields=None, only_fields=None,
               request_fields=None, sideload=True, dynamic=True, **kwargs):
    """
    Custom initializer that builds `request_fields` and
    sets a `ListSerializer` that doesn't re-evaluate querysets.

    Arguments:
      instance: instance for the serializer base
      include_fields: list of field names to include (adds to default field set)
      exclude_fields: list of field names to exclude (removes from default field set)
      only_fields: list of field names to render (overrides field set)
      request_fields: map of field names that supports inclusions, exclusions, and nested sideloads
      dynamic: if False, ignore deferred rules and revert to standard DRF fields behavior (default: True)
      sideload: if False, do not perform sideloading on data
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
        if field.allow_null == False and field.required == False \
                and field_name in data and data[field_name] is None:
          data.pop(field_name)

    kwargs['instance'] = instance
    kwargs['data'] = data
    super(DynamicModelSerializer, self).__init__(**kwargs)

    self.sideload = self._context.get('sideload', sideload)
    self.dynamic = dynamic
    self.request_fields = request_fields or self._context.get('request_fields', {})
    self.only_fields = only_fields or self._context.get('only_fields', [])
    include_fields = include_fields or self._context.get('include_fields', [])
    exclude_fields = exclude_fields or self._context.get('exclude_fields', [])
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
    If the plural name is not defined, the pluralized name will be returned.
    """
    return getattr(self.Meta, 'plural_name', self.get_name() + 's')

  def get_all_fields(self):
    """Returns the entire serializer field set.

    Does not respect dynamic field inclusions/exclusions.
    """
    if not hasattr(self, '_all_fields'):
      self._all_fields = super(DynamicModelSerializer, self).get_fields()
    return self._all_fields

  def get_fields(self):
    """Returns the serializer's field set.

    If `dynamic` is True, respects field inclusions/exlcusions, taking into account
    `field.deferred` (field-specific flag), `Meta.deferred_fields` (serializer-specific list),
    `only_fields` and/or `request_fields` (passed to the serializer by a viewset or parent serializer).
    """
    if self.dynamic == False:
      return self.get_all_fields()

    if self.id_only():
      return {}

    serializer_fields = self.get_all_fields()
    request_fields = self.request_fields
    only_fields = set(self.only_fields)

    # return only those fields specified, ignoring deferred rules
    if only_fields:
      return {k:v for k,v in serializer_fields.iteritems() if k in only_fields}

    # determine fields that are deferred by default
    meta_deferred = set(getattr(self.Meta, 'deferred_fields', []))
    deferred = set([name for name, field in serializer_fields.iteritems()
                    if getattr(field, 'deferred', None) == True or name in meta_deferred])

    # apply request overrides
    if request_fields:
      for name, include in request_fields.iteritems():
        if not name in serializer_fields:
          raise exceptions.ParseError(
              "'%s' is not a valid field name for '%s'" % (name, self.get_name()))
        if include != False and name in deferred:
          deferred.remove(name)
        elif include == False:
          deferred.add(name)

    # remove any deferred fields from the base list
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
      representation = super(DynamicModelSerializer, self).to_representation(instance)
    # save the plural name and id
    # so that the DynamicRenderer can sideload in post-serialization
    representation['_name'] = self.get_plural_name()
    representation['_pk'] = instance.pk
    return representation

  def save(self, *args, **kwargs):
    update = getattr(self, 'instance', None) is not None
    instance = super(DynamicModelSerializer, self).save(*args, **kwargs)
    view = self._context.get('view')
    if update and view:
      # reload the object on update
      # to get around prefetched manager issues
      instance = self.instance = view.get_object()
    return instance

  def id_only(self):
    """Whether or not the serializer should return an ID instead of an object.

    Returns:
      True iff `request_fields` == True
    """
    return self.request_fields == True

  @property
  def data(self):
    if not hasattr(self, '_sideloaded_data'):
      data = super(DynamicModelSerializer, self).data
      self._sideloaded_data = SideloadingProcessor(self, data).data
    return self._sideloaded_data

