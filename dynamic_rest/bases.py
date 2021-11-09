"""This module contains base classes for DREST."""

from dynamic_rest.utils import model_from_definition


class DynamicSerializerBase(object):

    """Base class for all DREST serializers."""
    pass


def resettable_cached_property(func):
    """Decorator to add cached computed properties to an object.
    Similar to Django's `cached_property` decorator, except stores
    all the data under a single well-known key so that it can easily
    be blown away.
    """

    def wrapper(self):
        if not hasattr(self, '_resettable_cached_properties'):
            self._resettable_cached_properties = {}
        if func.__name__ not in self._resettable_cached_properties:
            self._resettable_cached_properties[func.__name__] = func(self)
        return self._resettable_cached_properties[func.__name__]

    # Returns a property whose getter is the 'wrapper' function
    return property(wrapper)


def cacheable_object(cls):
    """Decorator to add a reset() method that clears data cached by
    the @resettable_cached_property decorator. Technically this could
    be a mixin...
    """

    def reset(self):
        if hasattr(self, '_resettable_cached_properties'):
            self._resettable_cached_properties = {}

    cls.reset = reset
    return cls


@cacheable_object
class CacheableFieldMixin(object):
    """Overide Field.root and Field.context to make fields/serializers
    cacheable and reusable. The DRF version uses @cached_property which
    doesn't have a public API for resetting. This version uses normal
    object variables with and adds a `reset()` API.
    """

    @resettable_cached_property
    def root(self):
        root = self
        while root.parent is not None:
            root = root.parent
        return root

    @resettable_cached_property
    def context(self):
        return getattr(self.root, '_context', {})


class GetModelMixin(object):
    """
    Mixin to retrieve model hashid

    Implementation from
    https://github.com/evenicoulddoit/django-rest-framework-serializer-extensions
    """

    def __init__(self, *args, **kwargs):
        self.model = kwargs.pop('model', None)
        super(GetModelMixin, self).__init__(*args, **kwargs)

    def get_model(self):
        """
        Return the model to generate the HashId for.

        By default, this will equal the model defined within the Meta of the
        ModelSerializer, but can be redefined either during initialisation
        of the Field, or by providing a get_<field_name>_model method on the
        parent serializer.

        The Meta can either explicitly define a model, or provide a
        dot-delimited string path to it.
        """
        if self.model is None:
            custom_fn_name = 'get_{0}_model'.format(self.field_name)

            if hasattr(self.parent, custom_fn_name):
                return getattr(self.parent, custom_fn_name)()
            else:
                try:
                    return self.parent.Meta.model
                except AttributeError:
                    raise AssertionError(
                        'No "model" value passed to field "{0}"'.format(
                            type(self).__name__
                        )
                    )
        elif isinstance(self.model, str):
            return model_from_definition(self.model)
        else:
            return self.model
