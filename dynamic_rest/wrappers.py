from collections import OrderedDict


class TaggedDict(object):
    pass


class TaggedDictMixin(TaggedDict):

    """
    Return object from `to_representation` for the `Serializer` class.
    Includes a reference to the `instance` and the `serializer` represented.
    """

    def __init__(self, *args, **kwargs):
        self.serializer = kwargs.pop('serializer')
        self.instance = kwargs.pop('instance')
        self.embed = kwargs.pop('embed', False)
        super(TaggedDictMixin, self).__init__(*args, **kwargs)

    def copy(self):
        return TaggedDict(
            self, serializer=self.serializer, instance=self.instance)

    def __repr__(self):
        return dict.__repr__(self)

    def __reduce__(self):
        return (dict, (dict(self),))


class TaggedOrderedDict(TaggedDictMixin, OrderedDict):
    pass


class TaggedPlainDict(TaggedDictMixin, dict):
    pass
