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


class DynamicField(fields.ReadOnlyField):

  """
  Generic field to capture additional custom field attributes
  """

  def __init__(self, deferred=False, field_type=None, nullable=True, **kwargs):
    """
    Arguments:
      deferred: Whether or not this field is deferred,
          i.e. not included in the response unless specifically requested.
      field_type: Field data type, if not inferrable from model.
      nullable: True if value can be null/None. Set if not inferrable from model.
    """
    super(DynamicField, self).__init__(**kwargs)
    self.deferred = deferred
    self.field_type = field_type
    self.allow_null = nullable


class DynamicComputedField(DynamicField):
  """
  Computed field base-class (i.e. fields that are dynamically computed,
  rather than being tied to model fields.)
  """
  is_computed = True

  def __init__(self, *args, **kwargs):
    return super(DynamicField, self).__init__(*args, **kwargs)


class DynamicRelationField(DynamicField):

  """Proxy for a sub-serializer.

  Supports passing in the target serializer as a class or string,
  resolves after binding to the parent serializer.
  """

  FOREIGN_KEY = 'fk'
  MANY_TO_MANY = 'm2m'
  MANY_TO_ONE = 'm2o' # "other side" of a foreign key
  SERIALIZER_KWARGS = set(('many', 'source'))

  def __init__(self, serializer_class, relation_type=None, many=False, **kwargs):
    """
    Arguments:
      serializer_class: Serializer class (or string representation) to proxy.
    """
    self.kwargs = kwargs
    self._serializer_class = serializer_class
    self.relation_type= relation_type
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
    if not self.relation_type:
      self.relation_type = self.get_relation_type()

  def is_many(self):
    return self.get_relation_type() in [ self.MANY_TO_MANY, self.MANY_TO_ONE ] 

  def get_relation_type(self):
    """
    Get relation type. If not set explicitly as relation_type,
    try to infer by looking up the corresponding model field.
    NOTE: Fields are not bound to serializers until the serializer's
          .field attribute is accessed. That means it's not guaranteed
          that this call will succeed, though in most realistic cases,
          it'll probably succeed. To check if this field has been bound,
          check the .bound attribute.
    """
    if self.relation_type:
      return self.relation_type

    if not self.bound: # set by Field base class, on initialize()/bind()
      raise Exception("get_relation_type called before field binding")

    model = getattr(self.parent.Meta, 'model', None)

    # NOTE: this approach will not get many-to-one fields
    field = None
    try:
      field = model._meta.get_field(self.source)
    except Exception as e:
      pass

    if field:
      if isinstance(field, ManyToManyField):
        return self.MANY_TO_MANY
      elif isinstance(field, ForeignKey):
        return self.FOREIGN_KEY
    elif self.source.endswith('_set'):
      field = getattr(model, self.source)
      if isinstance(field, ForeignRelatedObjectsDescriptor):
        return self.MANY_TO_ONE
    else:
      return self.MANY_TO_MANY # probably a pretty safe assumption

    return None

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

  def __init__(self, source_field, *args, **kwargs):
    self.source_field = source_field
    self.field_type = int
    return super(CountField, self).__init__(*args, **kwargs)

  def get_attribute(self, obj):
    """ DRF 3.x """
    return self.field_to_native(obj, self.field_name)

  def field_to_native(self, obj, field):
    """ Django REST 2.x """
    if self.source_field in self.parent.fields:
      data = self.parent.fields[self.source_field].field_to_native(obj, field)
      return len(data) 
    return None
