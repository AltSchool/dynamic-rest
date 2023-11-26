"""This module contains tagging utilities for DREST data structures."""
from collections import OrderedDict


def tag_dict(obj, *args, **kwargs):
    """Create a TaggedDict instance. Will either be a TaggedOrderedDict
    or TaggedPlainDict depending on the type of `obj`."""

    if isinstance(obj, OrderedDict):
        return _TaggedOrderedDict(obj, *args, **kwargs)
    else:
        return _TaggedPlainDict(obj, *args, **kwargs)


class TaggedDict(object):

    """
    Return object from `to_representation` for the `Serializer` class.
    Includes a reference to the `instance` and the `serializer` represented.
    """

    def __init__(self, *args, **kwargs):
        self.serializer = kwargs.pop('serializer')
        self.instance = kwargs.pop('instance')
        self.embed = kwargs.pop('embed', False)
        self.pk_value = kwargs.pop('pk_value', None)
        if not isinstance(self, dict):
            raise Exception(
                "TaggedDict constructed not as a dict"
            )
        super(TaggedDict, self).__init__(*args, **kwargs)

    def copy(self):
        return tag_dict(
            self,
            serializer=self.serializer,
            instance=self.instance,
            embed=self.embed,
            pk_value=self.pk_value
        )

    def __repr__(self):
        return dict.__repr__(self)

    def __reduce__(self):
        return (dict, (dict(self),))


class _TaggedPlainDict(TaggedDict, dict):
    pass


class _TaggedOrderedDict(TaggedDict, OrderedDict):
    pass
