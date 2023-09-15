"""This module contains tagging utilities for DREST data structures."""


class TaggedDict(dict):

    """
    Return object from `to_representation` for the `Serializer` class.
    Includes a reference to the `instance` and the `serializer` represented.
    """

    def __init__(self, *args, **kwargs):
        self.serializer = kwargs.pop('serializer')
        self.instance = kwargs.pop('instance')
        self.embed = kwargs.pop('embed', False)
        self.pk_value = kwargs.pop('pk_value', None)
        super().__init__(*args, **kwargs)

    def copy(self):
        return TaggedDict(
            self,
            serializer=self.serializer,
            instance=self.instance,
            embed=self.embed,
            pk_value=self.pk_value
        )

    def __repr__(self):
        return dict.__repr__(self)

    def __reduce__(self):
        return dict, (dict(self),)
