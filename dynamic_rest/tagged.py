"""This module contains tagging utilities for DREST data structures."""


class TaggedDict(dict):
    """A tagged dictionary.

    Return object from `to_representation` for the `Serializer` class.
    Includes a reference to the `instance` and the `serializer` represented.
    """

    def __init__(self, *args, **kwargs):
        """Initialise the TaggedDict."""
        self.serializer = kwargs.pop("serializer")
        self.instance = kwargs.pop("instance")
        self.embed = kwargs.pop("embed", False)
        self.pk_value = kwargs.pop("pk_value", None)
        super().__init__(*args, **kwargs)

    def copy(self):
        """Return a copy of the TaggedDict."""
        return TaggedDict(
            self,
            serializer=self.serializer,
            instance=self.instance,
            embed=self.embed,
            pk_value=self.pk_value,
        )

    def __repr__(self):
        """Return a string representation of the TaggedDict."""
        return dict.__repr__(self)

    def __reduce__(self):
        """Return a tuple representation of the TaggedDict."""
        return dict, (dict(self),)
