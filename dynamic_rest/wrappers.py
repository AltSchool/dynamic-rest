from collections import OrderedDict
from django.conf import settings


dynamic_settings = getattr(settings, 'DYNAMIC_REST', {})


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
            embed=self.embed
        )

    def __repr__(self):
        return dict.__repr__(self)

    def __reduce__(self):
        return (dict, (dict(self),))


class _TaggedPlainDict(TaggedDict, dict):
    pass


class _TaggedOrderedDict(TaggedDict, OrderedDict):
    pass


def hash_dict(obj):
    """Hash a dict (which aren't normally hashable)."""

    def _convert(o):
        # Recursively convert to hashable types
        if isinstance(o, dict):
            o = o.items()
        if hasattr(o, '__iter__'):
            out = []
            for i in o:
                out.append(_convert(i))
            return frozenset(out)
        else:
            return o

    return hash(_convert(obj))
