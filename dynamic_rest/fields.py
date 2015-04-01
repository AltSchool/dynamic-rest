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
    self._serializer_class = serializer_class
    if not 'deferred' in kwargs:
      kwargs['deferred'] = True
    super(DynamicRelationField, self).__init__(**kwargs)

  @property
  def serializer(self):
    if hasattr(self, '_serializer'):
      return self._serializer

    serializer = self.serializer_class(many=self.many)
    self._serializer = serializer
    return serializer

  def to_representation(self, instance):
    return self.serializer.to_representation(instance)

  @property
  def serializer_class(self):
    serializer_class = self._serializer_class
    if not isinstance(serializer_class, basestring):
      return serializer_class

    parts = serializer_class.split('.')
    module_path = '.'.join(parts[:-1])
    if not module_path:
      if getattr(self, 'parent', None) is None:
        raise Exception(
            "Can not load serializer '%s' before binding or without specifying full path" % serializer_class)

      # try the module of the parent class
      module_path = self.parent.__module__

    module = importlib.import_module(module_path)
    serializer_class = getattr(module, parts[-1])

    self._serializer_class = serializer_class
    return serializer_class

  def __getattr__(self, name):
    """Proxy all methods and properties on the underlying serializer."""
    return getattr(self.serializer, name)

