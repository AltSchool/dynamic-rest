from collections import defaultdict
from rest_framework import renderers


class DynamicJSONRenderer(renderers.JSONRenderer):

  def render(self, data, accepted_media_type=None, renderer_context=None):
    # if data is a string, just render it out using the default method
    # this usually indicates an error message
    if isinstance(data, basestring):
      return super(DynamicJSONRenderer, self).render(data, accepted_media_type, renderer_context)

    # populated by _sideload
    self._data = {}

    # used by _sideload to prevent duplicates
    self._seen = defaultdict(set)

    # used by _sideload to prevent adding secondary records of the primary resource
    # from ending up in the primary slot
    self._plural_name = getattr(
        renderer_context.get('view').get_serializer().Meta, 'plural_name', 'objects')

    # recursively sideload everything
    self._sideload(data)

    # add the primary resource data into the response data
    if isinstance(data, dict):
      resource_name = getattr(
          renderer_context.get('view').get_serializer().Meta, 'name', 'object')
    else:
      resource_name = self._plural_name

    self._data[resource_name] = data

    view = renderer_context.get('view')
    if hasattr(view, 'response_meta') and view.response_meta:
      self._data['meta'] = view.response_meta

    # call super to render the response
    return super(DynamicJSONRenderer, self).render(self._data, accepted_media_type, renderer_context)

  # recursively traverse the data and extract all resources
  # that need to be sideloaded
  def _sideload(self, obj, parent=None, parent_key=None, depth=0):
    if isinstance(obj, list):
      # list
      for key, o in enumerate(obj):
        # recurse into lists of objects
        self._sideload(o, parent=obj, parent_key=key, depth=depth)
    elif isinstance(obj, dict):
      # object

      if '_model' in obj and '_pk' in obj:
        model = obj['_model']
        pk = obj['_pk']

        # strip the model and pk tags from the final response
        del obj['_pk']
        del obj['_model']

        # recursively check all fields
        for key, o in obj.iteritems():
          if isinstance(o, list) or isinstance(o, dict):
            # lists or dicts indicate a relation
            self._sideload(o, parent=obj, parent_key=key, depth=depth + 1)

        seen = True
        # if this object has not yet been seen
        if not pk in self._seen[model]:
          seen = False
          self._seen[model].add(pk)

        # prevent sideloading the primary objects
        if depth == 0:
          return

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
