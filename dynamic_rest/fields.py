from rest_framework import fields
from rest_framework.exceptions import ParseError, NotFound
from rest_framework.serializers import ListSerializer
from django.db.models.related import RelatedObject
from django.db.models import ForeignKey, ManyToManyField, Manager, Model
from django.db.models.fields.related import ForeignRelatedObjectsDescriptor 
import importlib

def field_is_remote(model, field_name):
  """
  Helper function to determine whether model field is remote or not.
  Remote fields are many-to-many or many-to-one.
  """

  try:
    model_field = model._meta.get_field_by_name(field_name)[0]
    return isinstance(model_field, (ManyToManyField, RelatedObject))
  except:
    pass

  # M2O fields with no related_name set in the FK use the *_set
  # naming convention. 
  if field_name.endswith('_set'):
    return getattr(model, field_name, False)

  return False


class DynamicField(fields.Field):

  """
  Generic field to capture additional custom field attributes
  """

  def __init__(self, deferred=False, field_type=None, **kwargs):
    """
    Arguments:
      deferred: Whether or not this field is deferred,
          i.e. not included in the response unless specifically requested.
      field_type: Field data type, if not inferrable from model.
    """
    self.deferred = kwargs.pop('deferred', deferred)
    self.field_type = kwargs.pop('field_type', field_type)
    super(DynamicField, self).__init__(**kwargs)

  def to_representation(self, value):
    return value


class DynamicComputedField(DynamicField):
  """
  Computed field base-class (i.e. fields that are dynamically computed,
  rather than being tied to model fields.)
  """
  is_computed = True

  def __init__(self, *args, **kwargs):
    return super(DynamicComputedField, self).__init__(*args, **kwargs)


class DynamicRelationField(DynamicField):

  """Proxy for a sub-serializer.

  Supports passing in the target serializer as a class or string,
  resolves after binding to the parent serializer.
  """

  SERIALIZER_KWARGS = set(('many', 'source'))

  def __init__(self, serializer_class, many=False, **kwargs):
    """
    Arguments:
      serializer_class: Serializer class (or string representation) to proxy.
    """
    self.kwargs = kwargs
    self._serializer_class = serializer_class
    self.bound = False
    if '.' in self.kwargs.get('source', ''):
      raise Exception('Nested relationships are not supported')
    super(DynamicRelationField, self).__init__(**kwargs)
    self.kwargs['many'] = many

  def get_model(self):
    return getattr(self.serializer_class.Meta, 'model', None) 

  def bind(self, *args, **kwargs):
    super(DynamicRelationField, self).bind(*args, **kwargs)
    self.bound = True
    parent_model = self.parent.Meta.model

    remote = field_is_remote(parent_model, self.source)
    try:
      model_field = parent_model._meta.get_field_by_name(self.source)[0]
    except:
      # model field may not be available for m2o fields with no related_name
      model_field = None

    if not 'required' in self.kwargs and (remote or (
        model_field and (model_field.has_default() or model_field.null))):
      self.required = False
    if not 'allow_null' in self.kwargs and getattr(model_field, 'null', False):
      self.allow_null = True

    self.model_field = model_field

  @property
  def serializer(self):
    if hasattr(self, '_serializer'):
      return self._serializer

    serializer = self.serializer_class(
        **{k: v for k, v in self.kwargs.iteritems() if k in self.SERIALIZER_KWARGS})
    self._serializer = serializer
    return serializer

  def get_attribute(self, instance):
    return instance

  def to_representation(self, instance):
    serializer = self.serializer
    source = self.source
    if not self.kwargs['many'] and serializer.id_only():
      # attempt to optimize by reading the related ID directly
      # from the current instance rather than from the related object
      source_id = '%s_id' % source
      if hasattr(instance, source_id):
        return getattr(instance, source_id)
    try:
      related = getattr(instance, source)
    except:
      return None
    if related is None:
      return None
    return serializer.to_representation(related)

  def to_internal_value_single(self, data, serializer):
    related_model = serializer.Meta.model
    if isinstance(data, related_model):
      return data
    try:
      instance = related_model.objects.get(pk=data)
    except related_model.DoesNotExist:
      raise NotFound("'%s object with ID=%s not found" % (related_model.__name__, data))
    return instance

  def to_internal_value(self, data):
    if self.kwargs['many']:
      serializer = self.serializer.child
      if not isinstance(data, list):
        raise ParseError("'%s' value must be a list" % self.field_name)
      return [self.to_internal_value_single(instance, serializer) for instance in data]
    return self.to_internal_value_single(data, self.serializer)

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


class CountField(DynamicComputedField):
  """
  Field that counts number of elements in another specified field.
  """

  def __init__(self, source, *args, **kwargs):
    self.field_type = int
    kwargs['source'] = source
    return super(CountField, self).__init__(*args, **kwargs)

  def get_attribute(self, obj):
    if self.source in self.parent.fields:
      data = self.parent.fields[self.source].to_representation(obj)
      return len(data) if isinstance(data, list) else None
    return None 

