from collections import defaultdict
from rest_framework import renderers


class DynamicJSONRenderer(renderers.JSONRenderer):
  """
  Custom renderer that handles post-processing operations such as
  sideloading and metadata injection.

  Optional view parameters that control this behavior:

  * _sideload: (Default: True) if False, turns off sideloading
  * _metadata: (Default: None) if non-empty, added to the response data

  """
  def render(self, data, accepted_media_type=None, renderer_context=None):
    # if data is a string, render it using the default method
    if isinstance(data, basestring):
      return super(DynamicJSONRenderer, self).render(data, accepted_media_type, renderer_context)

    # this renderer must be associated with a DRF view
    view = renderer_context.get('view')

    self._data = {}
    self._sideload = getattr(view, '_sideload', True)

    self._seen = defaultdict(set)
    self._plural_name = getattr(view.serializer_class(), '_get_plural_name', lambda: 'objects')()
    self._name = getattr(view.serializer_class(), '_get_name', lambda: 'object')()

    # process the data
    self._process(data)

    if self._sideload:
      # add the primary resource data into the response data
      resource_name = self._name if isinstance(data, dict) else self._plural_name
      self._data[resource_name] = data
    else:
      # use the data as-is
      self._data = data

    # add metadata to the response if specified by the view
    if getattr(view, '_metadata', None):
      self._data['meta'] = view._metadata

    # call superclass to render the response
    return super(DynamicJSONRenderer, self).render(self._data, accepted_media_type, renderer_context)

  def _process(self, obj, parent=None, parent_key=None, depth=0):
    """
    Recursively traverse the response data, remove identifying tags added by serializers
    and sideload if necessary.
    """
    if isinstance(obj, list):
      for key, o in enumerate(obj):
        # traverse into lists of objects
        self._process(o, parent=obj, parent_key=key, depth=depth)
    elif isinstance(obj, dict):
      if '_model' in obj and '_pk' in obj:
        model = obj.pop('_model')
        pk = obj.pop('_pk')

        # recursively check all fields
        for key, o in obj.iteritems():
          if isinstance(o, list) or isinstance(o, dict):
            # lists or dicts indicate a relation
            self._process(o, parent=obj, parent_key=key, depth=depth + 1)

        # if sideloading is off, stop here
        if not self._sideload:
          return

        # sideloading

        seen = True
        # if this object has not yet been seen
        if not pk in self._seen[model]:
          seen = False
          self._seen[model].add(pk)

        # prevent sideloading the primary objects
        if depth == 0:
          return

        # TODO: spec out the exact behavior for secondary instances of
        # the primary resource

        # if the primary resource is embedded, add it to a prefixed key
        if model == self._plural_name:
          model = '+%s' % model

        if not seen:
          # allocate a top-level key in the data for this resource type
          if model not in self._data:
            self._data[model] = []

          # move the object into a new top-level bucket
          # and mark it as seen
          self._data[model].append(obj)

        # replace the object with a reference
        if parent is not None and parent_key is not None:
          parent[parent_key] = pk
