from collections import defaultdict
from rest_framework.serializers import ListSerializer

class SideloadingProcessor(object):
  def __init__(self, serializer, data):
    if isinstance(serializer, ListSerializer):
      serializer = serializer.child

    self.data = {}
    self.sideload = serializer.sideload
    self.seen = defaultdict(set)
    self.plural_name = serializer.get_plural_name()
    self.name = serializer.get_name()

    # process the data, optionally sideloading
    self.process(data)

    # add the primary resource data into the response data
    resource_name = self.name if isinstance(data, dict) else self.plural_name
    self.data[resource_name] = data

  def is_dynamic(self, data):
    if isinstance(data, list):
      return self.is_dynamic(data[0]) if len(data) else False
    if isinstance(data, dict):
      return '_pk' in data and '_name' in data
    return False

  def process(self, obj, parent=None, parent_key=None, depth=0):
    """
    Recursively traverse the response data, remove identifying tags added by serializers
    and sideload if necessary.
    """
    if isinstance(obj, list):
      for key, o in enumerate(obj):
        # traverse into lists of objects
        self.process(o, parent=obj, parent_key=key, depth=depth)
    elif isinstance(obj, dict):
      if self.is_dynamic(obj):
        name = obj.pop('_name')
        pk = obj.pop('_pk')

        # recursively check all fields
        for key, o in obj.iteritems():
          if isinstance(o, list) or isinstance(o, dict):
            # lists or dicts indicate a relation
            self.process(o, parent=obj, parent_key=key, depth=depth + 1)

        # if sideloading is off, stop here
        if not self.sideload:
          return

        # sideloading

        seen = True
        # if this object has not yet been seen
        if not pk in self.seen[name]:
          seen = False
          self.seen[name].add(pk)

        # prevent sideloading the primary objects
        if depth == 0:
          return

        # TODO: spec out the exact behavior for secondary instances of
        # the primary resource

        # if the primary resource is embedded, add it to a prefixed key
        if name == self.plural_name:
          name = '+%s' % name

        if not seen:
          # allocate a top-level key in the data for this resource type
          if name not in self.data:
            self.data[name] = []

          # move the object into a new top-level bucket
          # and mark it as seen
          self.data[name].append(obj)

        # replace the object with a reference
        if parent is not None and parent_key is not None:
          parent[parent_key] = pk
