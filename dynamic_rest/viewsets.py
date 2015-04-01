from django.db.models import Prefetch
from dynamic_rest.fields import DynamicRelationField
from dynamic_rest.renderers import DynamicJSONRenderer
from rest_framework import viewsets, response, exceptions, serializers
from rest_framework.renderers import BrowsableAPIRenderer


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
  renderer_classes = (DynamicJSONRenderer, BrowsableAPIRenderer)
  features = (INCLUDE, EXCLUDE)
  sideload = True
  meta = None

  def get_queryset(self, serializer=None):
    if serializer:
      queryset = serializer.Meta.model.objects.all()
    else:
      serializer = self.get_serializer()
      queryset = getattr(self, 'queryset', serializer.Meta.model.objects.all())

    prefetch_related = []
    for name, field in serializer.get_fields().iteritems():
      source = field.source or name
      if isinstance(field, DynamicRelationField):
        field = field.serializer
      if isinstance(field, serializers.ListSerializer):
        field = field.child
      if isinstance(field, serializers.BaseSerializer):
        prefetch_related.append(Prefetch(source, self.get_queryset(field)))
    return queryset.prefetch_related(*prefetch_related)

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
    return context

  def list(self, request, *args, **kwargs):
    return response.Response(self.get_serializer(self.get_queryset(), many=True).data)

  def retrieve(self, request, *args, **kwargs):
    return response.Response(self.get_serializer(self.get_object()).data)
