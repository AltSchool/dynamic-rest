from django.conf import settings
from django.db.models import Q, Prefetch, ManyToManyField
from django.db.models.related import RelatedObject
from django.http import QueryDict

from dynamic_rest.fields import DynamicRelationField, field_is_remote
from dynamic_rest.pagination import DynamicPageNumberPagination
from dynamic_rest.metadata import DynamicMetadata
from dynamic_rest.datastructures import TreeMap
from dynamic_rest.filters import DynamicFilterBackend

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

  # TODO: add support for `sort{}`
  pagination_class = DynamicPageNumberPagination
  metadata_class = DynamicMetadata
  renderer_classes = (JSONRenderer, BrowsableAPIRenderer)
  features = (INCLUDE, EXCLUDE, FILTER, PAGE, PER_PAGE)
  sideload = True
  meta = None
  filter_backends = (DynamicFilterBackend,)

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
      return self._extract_object_params(name) if name in self.features else {} 
    else:
      # single-type
      return self.request.QUERY_PARAMS.get(name) if name in self.features else None

  def _extract_object_params(self, name):
    """
    Extract object params, return as dict
    """

    params = self.request.query_params.lists()
    params_map = {}
    prefix = name[:-1]
    offset = len(prefix)
    for name, value in params:
      if name.startswith(prefix) and name.endswith('}'):
        name = name[offset:-1]
      else:
        continue
      params_map[name] = value

    return params_map 

  def get_queryset(self, queryset=None):
    """
    Returns a queryset for this request.

    Arguments:
      queryset: Optional root-level queryset.
    """
    serializer = self.get_serializer()
    return getattr(self, 'queryset', serializer.Meta.model.objects.all())


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
    if self.request and self.request.method.lower() in ('put', 'post', 'patch'):
      context['dynamic'] = False 
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
