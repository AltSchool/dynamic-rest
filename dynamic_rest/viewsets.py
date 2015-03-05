from rest_framework import viewsets, response

class DynamicModelViewSet(viewsets.ModelViewSet):

  def _get_request_fields(self):
    request_fields = self.request.QUERY_PARAMS.getlist('fields[]')
    field_map = {}
    for field in request_fields:
      if field.startswith('-'):
        field = field[1:]
        include = False
      else:
        include = True
      field_segments = field.split('.')
      num_segments = len(field_segments)
      current_map = field_map
      for i, segment in enumerate(field_segments):
        if segment:
          if i < num_segments - 1:
            if not segment in current_map:
              current_map[segment] = {}
            current_map = current_map[segment]
          else:
            current_map[segment] = include
    return field_map

  def list(self, request, *args, **kwargs):
    return response.Response(self.serializer_class(self.get_queryset(), many=True, context={'request_fields': self._get_request_fields()}).data)

  def retrieve(self, request, *args, **kwargs):
    return response.Response(self.serializer_class(self.get_object(), context={'request_fields': self._get_request_fields()}).data)
