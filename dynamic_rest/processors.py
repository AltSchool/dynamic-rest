"""This module contains response processors."""
from collections import defaultdict

import six
from rest_framework.serializers import ListSerializer
from rest_framework.utils.serializer_helpers import ReturnDict

from dynamic_rest.conf import settings
from dynamic_rest.tagged import TaggedDict


POST_PROCESSORS = {}


def register_post_processor(func):
    """
    Register a post processor function to be run as the final step in
    serialization. The data passed in will already have gone through the
    sideloading processor.

    Usage:
        @register_post_processor
        def my_post_processor(data):
            # do stuff with `data`
            return data
    """

    global POST_PROCESSORS

    key = func.__name__
    POST_PROCESSORS[key] = func
    return func


def post_process(data):
    """Apply registered post-processors to data."""

    for post_processor in POST_PROCESSORS.values():
        data = post_processor(data)

    return data


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

                serializer = obj.serializer
                name = serializer.get_plural_name()
                instance = getattr(obj, 'instance', serializer.instance)
                instance_pk = instance.pk if instance else None
                pk = getattr(obj, 'pk_value', instance_pk) or instance_pk

                # For polymorphic relations, `pk` can be a dict, so use the
                # string representation (dict isn't hashable).
                pk_key = repr(pk)

                # sideloading
                seen = True
                # if this object has not yet been seen
                if pk_key not in self.seen[name]:
                    seen = False
                    self.seen[name].add(pk_key)

                # prevent sideloading the primary objects
                if depth == 0:
                    return

                # TODO: spec out the exact behavior for secondary instances of
                # the primary resource

                # if the primary resource is embedded, add it to a prefixed key
                if name == self.plural_name:
                    name = '%s%s' % (
                        settings.ADDITIONAL_PRIMARY_RESOURCE_PREFIX,
                        name
                    )

                if not seen:
                    # allocate a top-level key in the data for this resource
                    # type
                    if name not in self.data:
                        self.data[name] = []

                    # move the object into a new top-level bucket
                    # and mark it as seen
                    self.data[name].append(obj)
                else:
                    # obj sideloaded, but maybe with other fields
                    for o in self.data.get(name, []):
                        if o.instance.pk == pk:
                            o.update(obj)
                            break

                # replace the object with a reference
                if parent is not None and parent_key is not None:
                    parent[parent_key] = pk
