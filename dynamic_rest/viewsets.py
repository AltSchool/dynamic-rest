from django.conf import settings
from django.db.models import Q, Prefetch, ManyToManyField
from django.db.models.related import RelatedObject
from django.http import QueryDict

from dynamic_rest.fields import DynamicRelationField, field_is_remote
from dynamic_rest.pagination import DynamicPageNumberPagination
from dynamic_rest.metadata import DynamicMetadata
from dynamic_rest.datastructures import TreeMap

from rest_framework import viewsets, response, exceptions, serializers
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer

dynamic_settings = getattr(settings, 'DYNAMIC_REST', {})

class QueryParams(QueryDict):
  """
  Extension of Django's QueryDict. Instantiated from a DRF Request
  object, and returns a mutable QueryDict subclass.
  Also adds methods that might be useful for our usecase.
  """

  def __init__(self, query_params, *args, **kwargs):
    query_string = getattr(query_params, 'urlencode', lambda: '')() 
    kwargs['mutable'] = True 
    super(QueryParams, self).__init__(query_string, *args, **kwargs)

  def add(self, key, value):
    """
    Method to accept a list of values and append to flat list.
    QueryDict.appendlist(), if given a list, will append the list, 
    which creates nested lists. In most cases, we want to be able
    to pass in a list (for convenience) but have it appended into
    a flattened list.
    TODO: Possibly throw an error if add() is used on a non-list param.
    """
    if isinstance(value, list):
      for val in value:
        self.appendlist(key, val)
    else:
      self.appendlist(key, value)


class WithDynamicViewSetMixin(object):
  """A viewset that can support dynamic API features.

  Attributes:
    features: A list of features supported by the viewset.
    sideload: Whether or not to enable sideloading in the DynamicRenderer.
    meta: Extra data that is added to the response by the DynamicRenderer.
  """

  INCLUDE = 'include[]'
  EXCLUDE = 'exclude[]'
  FILTER = 'filter{}'
  PAGE = dynamic_settings.get('PAGE_QUERY_PARAM', 'page')
  PER_PAGE = dynamic_settings.get('PAGE_SIZE_QUERY_PARAM', 'per_page')

  # TODO: add support for `sort{}`, `page`, and `per_page`
  pagination_class = DynamicPageNumberPagination
  metadata_class = DynamicMetadata
  renderer_classes = (JSONRenderer, BrowsableAPIRenderer)
  features = (INCLUDE, EXCLUDE, FILTER, PAGE, PER_PAGE)
  sideload = True
  meta = None

  VALID_OPERATORS = (
    'in',
    'any',
    'all',
    'like',
    'range',
    'gt',
    'lt',
    'gte',
    'lte',
    'isnull',
    None,
    )

  def initialize_request(self, request, *args, **kargs):
    """ 
    Override DRF initialize_request() method to swap request.GET
    (which is aliased by request.QUERY_PARAMS) with a mutable instance
    of QueryParams.
    """
    request.GET = QueryParams(request.GET)
    return super(WithDynamicViewSetMixin, self).initialize_request(
        request, *args, **kargs)

  def get_request_feature(self, name):
    """Parses the request for a particular feature.

    Arguments:
      name: A feature name.

    Returns:
      A feature parsed from the URL if the feature is supported, or None.
    """
    if '[]' in name:
      # array-type
      return self.request.QUERY_PARAMS.getlist(name) if name in self.features else None
    elif '{}' in name:
      # object-type (keys are not consistent)
      return self.request.QUERY_PARAMS.getlist(name) if name in self.features else None
    else:
      # single-type
      return self.request.QUERY_PARAMS.get(name) if name in self.features else None

  def _extract_filters_map(self):
    """
    Extract filter params, return as dict
    NOTE: Supports 'filters{}' and 'filter{}' due to an implementation error.
          In the future, 'filters' will be deprecated.
    """
    params = self.request.query_params.lists()
    filters_map = {}
    for name, value in params:
      if name.startswith('filters{') and name.endswith('}'):
        name = name[8:-1]
      elif name.startswith('filter{') and name.endswith('}'):
        name = name[7:-1]
      else:
        continue
      filters_map[name] = value

    return filters_map

  def _extract_filters(self, **kwargs):
    """ 
    Convert 'filters' query params into a dict that can be passed
    to Q. Returns a dict with two fields, 'include' and 'exclude',
    which can be used like:

      result = self._extract_filters()
      q = Q(**result['include'] & ~Q(**result['exclude'])

    """

    filters_map = kwargs.get('filters_map') or self._extract_filters_map()

    prefix = 'filters{'
    offset = len(prefix)
    out = TreeMap() 

    for spec, value in filters_map.iteritems():

      # Inclusion or exclusion?
      if spec[0]=='-':
        spec= spec[1:]
        inex = '_exclude'
      else:
        inex = '_include'

      # for relational filters, separate out relation path part 
      if '|' in spec:
        rel, spec = spec.split('|')  
        rel = rel.split('.')
      else:
        rel = None

      parts = spec.split('.')

      # if dot-delimited, assume last part is the operator, otherwise
      # assume whole thing is a field name (with 'eq' implied).
      field = '__'.join(parts[:-1]) if len(parts)>1 else parts[0] 

      # Assume last part of a dot-delimited field spec is an operator.
      # Note, however, that 'foo.bar' is a valid field spec with an 'eq'
      # implied as operator. This will be resolved below.
      operator = parts[-1] if len(parts) > 1 and parts[-1]!='eq' else None

      # All operators except 'range' and 'in' should have one value
      if operator == 'range':
        value = value[:2]
      elif operator == 'in':
        # no-op: i.e. accept `value` as an arbitrarily long list
        pass
      elif operator in self.VALID_OPERATORS:
        value = value[0]
      else:
        # Unknown operator, we'll treat it like a field 
        # e.g: filter{foo.bar}=baz
        field += '__' + operator
        operator = None
        value = value[0]

      param = field
      if operator:
        param += '__'+operator 

      path = rel if rel else []
      path.extend([inex, param])
      out.insert(path, value)

    return out 


  def _filters_to_query(self, includes, excludes, q=None): 
    """
    Construct Django Query object from request.
    Arguments are dictionaries, which will be passed to Q() as kwargs.

    e.g.
        includes = { 'foo' : 'bar', 'baz__in' : [1, 2] }
      produces:
        Q(foo='bar', baz__in=[1, 2])

    Arguments:
      includes: dictionary of inclusion filters
      excludes: dictionary of inclusion filters

    Returns:
      Q() instance or None if no inclusion or exclusion filters were specified
    """

    q = q or Q() 

    if not includes and not excludes:
      return None

    if includes:
      q &= Q(**includes)
    if excludes:
      for k,v in excludes.iteritems():
        q &= ~Q(**{k:v})
    return q


  def get_queryset(self, queryset=None):
    """
    Returns a queryset for this request.

    Arguments:
      queryset: Optional root-level queryset.
    """
    return self._get_queryset(root_queryset=queryset)

  def _get_queryset(self, serializer=None, filters=None, root_queryset=None):
    """
    Recursive queryset builder.
    Handles nested prefetching of related data and deferring fields
    at the queryset level.

    Arguments:
      serializer: An optional serializer to use a base for the queryset.
        If no serializer is passed, the `get_serializer` method will be used
        to initialize the base serializer for the viewset.
      filters: Optional nested filter map (TreeMap) 
      queryset: Optional queryset. Only applies to top-level. 
    """
    if serializer:
      queryset = serializer.Meta.model.objects
    else:
      serializer = self.get_serializer()
      queryset = root_queryset or getattr(
          self, 'queryset', serializer.Meta.model.objects.all())

    prefetch_related = []
    only = set()
    use_only = True
    model = serializer.Meta.model

    if filters == None:
      filters = self._extract_filters()  
    q = self._filters_to_query(
        includes=filters.get('_include'), excludes=filters.get('_exclude'))

    for name, field in serializer.get_fields().iteritems(): 
      if isinstance(field, DynamicRelationField):
        field = field.serializer
      if isinstance(field, serializers.ListSerializer):
        field = field.child

      source = field.source or name
      source0 = source.split('.')[0]
      remote = False

      if isinstance(field, serializers.ModelSerializer):
        remote = field_is_remote(model, source0)
        id_only = getattr(field, 'id_only', lambda: False)()
        if not id_only or remote:
          prefetch_qs = self._get_queryset(
              serializer=field, filters=filters.get(name,{}))
          prefetch_related.append(Prefetch(source, queryset=prefetch_qs))

      if use_only:
        if source == '*':
          use_only = False
        elif not remote:
          # TODO: optimize for nested sources
          only.add(source0)

    if getattr(serializer, 'id_only', lambda: False)():
      only = serializer.get_id_fields()
      use_only = True

    if use_only:
      queryset = queryset.only(*only)
    if q:
      queryset = queryset.filter(q)
    return queryset.prefetch_related(*prefetch_related)

  def get_request_fields(self):
    """Parses the `include[]` and `exclude[]` features.

    Extracts the dynamic field features from the request parameters
    into a field map that can be passed to a serializer.

    Returns:
      A nested dict mapping serializer keys to True (include) or False (exclude).
    """
    if hasattr(self, '_request_fields'):
      return self._request_fields

    include_fields = self.get_request_feature('include[]')
    exclude_fields = self.get_request_feature('exclude[]')
    request_fields = {}
    for fields, include in ((include_fields, True), (exclude_fields, False)):
      if fields is None:
        continue
      for field in fields:
        field_segments = field.split('.')
        num_segments = len(field_segments)
        current_fields = request_fields
        for i, segment in enumerate(field_segments):
          last = i == num_segments - 1
          if segment:
            if last:
              current_fields[segment] = include 
            else:
              if not segment in current_fields:
                current_fields[segment] = {}
              current_fields = current_fields[segment]
          elif not last:
            # empty segment must be the last segment
            raise exceptions.ParseError("'%s' is not a valid field" % field)

    self._request_fields = request_fields
    return request_fields

  def get_serializer_context(self):
    context = super(WithDynamicViewSetMixin, self).get_serializer_context()
    context['request_fields'] = self.get_request_fields()
    context['do_sideload'] = self.sideload
    return context

  def paginate_queryset(self, *args, **kwargs):
    if self.PAGE in self.features:
      # make sure pagination is enabled
      if not self.PER_PAGE in self.features and \
        self.PER_PAGE in self.request.QUERY_PARAMS:
        # remove per_page if it is disabled
        self.request.QUERY_PARAMS[self.PER_PAGE] = None
      return super(WithDynamicViewSetMixin, self).paginate_queryset(*args, **kwargs)
    return None


class DynamicModelViewSet(WithDynamicViewSetMixin, viewsets.ModelViewSet):
  pass
