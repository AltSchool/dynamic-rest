from rest_framework import fields
import importlib


class DynamicField(fields.Field):

  """
  Generic field to capture additional custom field attributes
  """

  def __init__(self, deferred=False, **kwargs):
    """
    Arguments:
      deferred: Whether or not this field is deferred,
        i.e. not included in the response unless specifically requested.
    """
    super(DynamicField, self).__init__(**kwargs)
    self.deferred = deferred


class DynamicRelationField(DynamicField):

  """Proxy for a sub-serializer.

  Supports passing in the target serializer as a class or string,
  resolves after binding to the parent serializer.
  """

  def __init__(self, serializer_class, many=False, **kwargs):
    """
    Arguments:
      serializer_class: Serializer class or string for objects type of this field
      many: Whether or not the target represents a list of objects, passed to the serializer.
    """
    self.many = many
    self.serializer_class = serializer_class
    if not 'deferred' in kwargs:
      kwargs['deferred'] = True
    super(DynamicRelationField, self).__init__(**kwargs)

  def bind(self, *args, **kwargs):
    super(DynamicRelationField, self).bind(*args, **kwargs)
    self.serializer_class = self._get_serializer_class(self.serializer_class)

  def get_serializer_context(self):
    return {
        'request_fields': getattr(self, '_request_fields', None)
    }

  def to_representation(self, instance):
    return self.serializer_class(many=self.many, context=self.get_serializer_context()).to_representation(instance)

  def _get_serializer_class(self, cls):
    if not isinstance(cls, basestring):
      return cls

    parts = cls.split('.')
    module_path = '.'.join(parts[:-1])
    if not module_path:
      # try the module of the parent class
      module_path = self.parent.__module__

    module = importlib.import_module(module_path)
    return getattr(module, parts[-1])
