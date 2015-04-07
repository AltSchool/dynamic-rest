from django.db.models import Prefetch, ManyToManyField
from django.db.models.related import RelatedObject
from dynamic_rest.fields import DynamicRelationField
from dynamic_rest.pagination import DynamicPageNumberPagination
from rest_framework import viewsets, response, exceptions, serializers
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from django.conf import settings

dynamic_settings = getattr(settings, 'DYNAMIC_REST', {})
class DynamicModelViewSet(viewsets.ModelViewSet):

  """A viewset that can support dynamic API features.

  Attributes:
    features: A list of features supported by the viewset.
    sideload: Whether or not to enable sideloading in the DynamicRenderer.
    meta: Extra data that is added to the response by the DynamicRenderer.
  """

  INCLUDE = 'include[]'
  EXCLUDE = 'exclude[]'
  PAGE = dynamic_settings.get('PAGE_QUERY_PARAM', 'page')
  PER_PAGE = dynamic_settings.get('PAGE_SIZE_QUERY_PARAM', 'per_page')

  # TODO: add support for `filter{}`, `sort{}`, `page`, and `per_page`
  pagination_class = DynamicPageNumberPagination
  renderer_classes = (JSONRenderer, BrowsableAPIRenderer)
  features = (INCLUDE, EXCLUDE, PAGE, PER_PAGE)
  sideload = True
  meta = None

  def get_queryset(self, serializer=None):
    """Returns a queryset for this request.

    Handles nested prefetching of related data and deferring fields
    at the queryset level.

    Arguments:
      serializer: An optional serializer to use a base for the queryset.
        If no serializer is passed, the `get_serializer` method will be used
        to initialize the base serializer for the viewset.
    """
    if serializer:
      queryset = serializer.Meta.model.objects.all()
    else:
      serializer = self.get_serializer()
      queryset = getattr(self, 'queryset', serializer.Meta.model.objects.all())

    prefetch_related = []
    only = set()
    use_only = True
    model = serializer.Meta.model

    for name, field in serializer.get_fields().iteritems():
      if isinstance(field, DynamicRelationField):
        field = field.serializer
      if isinstance(field, serializers.ListSerializer):
        field = field.child

      source = field.source or name
      source0 = source.split('.')[0]
      remote = False

      if isinstance(field, serializers.ModelSerializer):
        model_field = model._meta.get_field_by_name(source0)[0]
        remote = isinstance(model_field, (ManyToManyField, RelatedObject))
        if not getattr(field, 'id_only', lambda: False)() or remote:
          prefetch_related.append(Prefetch(source, queryset=self.get_queryset(field)))

      if use_only:
        if source == '*':
          use_only = False
        elif not remote:
          # TODO: optimize for nested sources
          only.add(source0)

    if use_only:
      queryset = queryset.only(*only)
    return queryset.prefetch_related(*prefetch_related)

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
    context = super(DynamicModelViewSet, self).get_serializer_context()
    context['request_fields'] = self.get_request_fields()
    context['sideload'] = self.sideload
    return context

  def paginate_queryset(self, *args, **kwargs):
    if self.PAGE in self.features:
      # make sure pagination is enabled
      if not self.PER_PAGE in self.features and \
        self.PER_PAGE in self.request.QUERY_PARAMS:
        # remove per_page if it is disabled
        self.request.QUERY_PARAMS[self.PER_PAGE] = None
      return super(DynamicModelViewSet, self).paginate_queryset(*args, **kwargs)
    return None
