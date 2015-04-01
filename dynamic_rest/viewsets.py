from rest_framework import viewsets, response, exceptions
from django.db.models import Q, Prefetch

class DynamicModelViewSet(viewsets.ModelViewSet):

  """A viewset that can support dynamic API features.

  Attributes:
    features: A list of features supported by the viewset.
    sideload: Whether or not to enable sideloading in the DynamicRenderer.
    meta: Extra data that is added to the response by the DynamicRenderer.
  """

  INCLUDE = 'include[]'
  EXCLUDE = 'exclude[]'

  # TODO: add support for `filter{}`, `sort{}`, `page`, and `per_page`
  features = (INCLUDE, EXCLUDE)
  sideload = True
  meta = None

  def get_queryset(self):
    filters = self.get_filters()
    prefetches = self.get_prefetches()
    return self.queryset.filter(filters).prefetch_related(*prefetches)

  def get_filters(self):
    # TOOD: implement this
    return Q()

  def get_prefetches(self):
    # TODO: implement this
    return []

  def get_request_feature(self, name):
    """Parses the request for a particular feature.

    Arguments:
      name: A feature name.

    Returns:
      A feature parsed from the URL if the feature is supported, or None.
    """
    return self.request.QUERY_PARAMS.getlist(name) if name in self.features else None

  def get_request_fields(self):
    """Parses the `include[]` and `exclude[]` features.

    Extracts the dynamic field features from the request parameters
    into a field map that can be passed to a serializer.

    Returns:
      A nested dict mapping serializer keys to True (include) or False (exclude).
    """
    include_fields = self.get_request_feature('include[]')
    exclude_fields = self.get_request_feature('exclude[]')
    field_map = {}
    for fields, include in ((include_fields, True), (exclude_fields, False)):
      if fields is None:
        continue
      for field in fields:
        field_segments = field.split('.')
        num_segments = len(field_segments)
        current_map = field_map
        for i, segment in enumerate(field_segments):
          last = i == num_segments - 1
          if segment:
            if last:
              current_map[segment] = include
            else:
              if not segment in current_map:
                current_map[segment] = {}
              current_map = current_map[segment]
          elif not last:
            # empty segment must be the last segment
            raise exceptions.ParseError("'%s' is not a valid field" % field)
    return field_map

  def get_serializer_context(self):
    context = super(DynamicModelViewSet, self).get_serializer_context()
    context['request_fields'] = self.get_request_fields()
    return context

  def list(self, request, *args, **kwargs):
    return response.Response(self.get_serializer(self.get_queryset(), many=True).data)

  def retrieve(self, request, *args, **kwargs):
    return response.Response(self.get_serializer(self.get_object()).data)
