from collections import OrderedDict
from rest_framework import serializers, fields, exceptions


class DynamicModelSerializer(serializers.ModelSerializer):

  def __init__(self, *args, **kwargs):
    super(DynamicModelSerializer, self).__init__(*args, **kwargs)
    self._request_fields = self._context.get('request_fields', {})

  def _id_only(self):
    return self._request_fields == True

  def get_fields(self):
    serializer_fields = super(DynamicModelSerializer, self).get_fields()

    # determine fields that are deferred by default
    deferred = set()

    for name, field in serializer_fields.iteritems():
      if getattr(field, 'deferred', None) == True:
        deferred.add(name)

    deferred_fields = getattr(self.Meta, 'deferred_fields', [])
    for name in deferred_fields:
      deferred.add(name)

    # determine fields that are requested to be
    # deferred/included
    if not self._id_only() and self._request_fields:
      for name, include in self._request_fields.iteritems():
        if not name in serializer_fields:
          raise exceptions.ParseError(
              "'%s' is not a valid field name for '%s'" % (name, self.Meta.name))
        if include != False and name in deferred:
          deferred.remove(name)
        elif include == False:
          deferred.add(name)

    for name in deferred:
      serializer_fields.pop(name)

    return serializer_fields

  def to_representation(self, instance):
    if self._id_only():
      # if True is passed to request_fields,
      # the serializer should just return an ID/list of IDs
      return instance.pk
    else:
      representation = OrderedDict()
      serializer_fields = [
          field for field in self.fields.values() if not field.write_only]

      for field in serializer_fields:
        try:
          attribute = field.get_attribute(instance)
        except fields.SkipField:
          continue

        if attribute is None:
          # We skip `to_representation` for `None` values so that
          # fields do not have to explicitly deal with that case.
          representation[field.field_name] = None
        else:
          if isinstance(field, serializers.BaseSerializer):
            # inject the `request_fields` sub-object into any sub-serializer
            # default behavior for a sub-serializer is to return the ID
            if hasattr(field, 'child') and isinstance(field.child, serializers.BaseSerializer):
              # inject into the child serializer
              field.child._request_fields = self._request_fields.get(field.field_name, True)
            else:
              field._request_fields = self._request_fields.get(field.field_name, True)
          representation[field.field_name] = field.to_representation(attribute)

    # save the plural name and id
    # so that the DynamicRenderer can sideload in post-serialization
    representation['_model'] = self.Meta.plural_name
    representation['_pk'] = instance.pk
    return representation
