"""This module contains response processors."""
from collections import defaultdict

from django.utils import six
from rest_framework.serializers import ListSerializer
from rest_framework.utils.serializer_helpers import ReturnDict

from dynamic_rest.tagged import TaggedDict


class SideloadingProcessor(object):
    """A processor that sideloads serializer data.

    Sideloaded records are returned under top-level
    response keys and produces responses that are
    typically smaller than their nested equivalent.
    """

    def __init__(self, serializer, data):
        """Initializes and runs the processor.

        Arguments:
            serializer: a DREST serializer
            data: the serializer's representation
        """

        if isinstance(serializer, ListSerializer):
            serializer = serializer.child
        self.data = {}
        self.seen = defaultdict(set)
        self.plural_name = serializer.get_plural_name()
        self.name = serializer.get_name()

        # process the data, optionally sideloading
        self.process(data)

        # add the primary resource data into the response data
        resource_name = self.name if isinstance(
            data,
            dict
        ) else self.plural_name
        self.data[resource_name] = data

    def is_dynamic(self, data):
        """Check whether the given data dictionary is a DREST structure.

        Arguments:
            data: A dictionary representation of a DRF serializer.
        """
        return isinstance(data, TaggedDict)

    def process(self, obj, parent=None, parent_key=None, depth=0):
        """Recursively process the data for sideloading.

        Converts the nested representation into a sideloaded representation.
        """
        if isinstance(obj, list):
            for key, o in enumerate(obj):
                # traverse into lists of objects
                self.process(o, parent=obj, parent_key=key, depth=depth)
        elif isinstance(obj, dict):
            dynamic = self.is_dynamic(obj)
            returned = isinstance(obj, ReturnDict)
            if dynamic or returned:
                # recursively check all fields
                for key, o in six.iteritems(obj):
                    if isinstance(o, list) or isinstance(o, dict):
                        # lists or dicts indicate a relation
                        self.process(
                            o,
                            parent=obj,
                            parent_key=key,
                            depth=depth +
                            1
                        )

                if not dynamic or getattr(obj, 'embed', False):
                    return

                name = obj.serializer.get_plural_name()
                pk = obj.instance.pk

                # sideloading
                seen = True
                # if this object has not yet been seen
                if pk not in self.seen[name]:
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
                    # allocate a top-level key in the data for this resource
                    # type
                    if name not in self.data:
                        self.data[name] = []

                    # move the object into a new top-level bucket
                    # and mark it as seen
                    self.data[name].append(obj)

                # replace the object with a reference
                if parent is not None and parent_key is not None:
                    parent[parent_key] = pk
