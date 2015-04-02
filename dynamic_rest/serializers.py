from collections import OrderedDict
from rest_framework import serializers, fields, exceptions
from dynamic_rest.fields import DynamicRelationField


class DynamicModelSerializer(serializers.ModelSerializer):

  def __init__(self, *args, **kwargs):
    """Extracts `request_fields` from the `context`."""
    super(DynamicModelSerializer, self).__init__(*args, **kwargs)
    self._request_fields = self._context.get('request_fields', {})

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

  def get_fields(self):
    if self.id_only():
      return {}

    serializer_fields = super(DynamicModelSerializer, self).get_fields()
    request_fields = self._request_fields

    # determine fields that are deferred by default
    meta_deferred = set(getattr(self.Meta, 'deferred_fields', []))
    deferred = set([name for name, field in serializer_fields.iteritems()
                    if getattr(field, 'deferred', None) == True or name in meta_deferred])

    # apply request overrides
    if request_fields:
      for name, include in request_fields.iteritems():
        if not name in serializer_fields:
          raise exceptions.ParseError(
              "'%s' is not a valid field name for '%s'" % (name, self.Meta.name))
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
        inject = field.child
      if inject:
        inject._request_fields = request_fields.get(name, True)

    return serializer_fields

  def to_representation(self, instance):
    if self.id_only():
      return instance.pk
    else:
      representation = super(DynamicModelSerializer, self).to_representation(instance)
    # save the plural name and id
    # so that the DynamicRenderer can sideload in post-serialization
    representation['_name'] = self.get_plural_name()
    representation['_pk'] = instance.pk
    return representation

  def id_only(self):
    """Whether or not the serializer should return an ID instead of an object.

    Returns:
      True iff `_request_fields` == True
    """
    return self._request_fields == True
