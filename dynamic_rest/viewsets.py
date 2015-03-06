from rest_framework import viewsets, response, exceptions


class DynamicModelViewSet(viewsets.ModelViewSet):
  # TODO: add support for other features

  INCLUDE = 'include[]'
  EXCLUDE = 'exclude[]'

  """
  Supported API features
  """
  _features = (INCLUDE, EXCLUDE)

  """
  Whether or not to enable sideloading
  in the DynamicRenderer.
  """
  _sideload = True

  """
  Extra data that will be added into
  the response by the DynamicRenderer.
  """
  _metadata = None

  def _get_request_feature(self, name):
    """
    Parses the request for a particular feature.
    If the feature is not supported, returns None.
    """
    return self.request.QUERY_PARAMS.getlist(name) if name in self._features else None

  def _get_request_fields(self):
    """
    Parses the `include[]` and `exclude[]` features into a
    field map that is passed into the serializer.
    """
    include_fields = self._get_request_feature('include[]')
    exclude_fields = self._get_request_feature('exclude[]')
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
    context['request_fields'] = self._get_request_fields()
    return context

  def list(self, request, *args, **kwargs):
    return response.Response(self.get_serializer(self.get_queryset(), many=True).data)

  def retrieve(self, request, *args, **kwargs):
    return response.Response(self.get_serializer(self.get_object()).data)
