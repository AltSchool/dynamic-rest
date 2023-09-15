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
        self._resettable_cached_properties = (  # pylint: disable=protected-access
            cache
        ) = getattr(self, "_resettable_cached_properties", {})
        func_name = func.__name__
        if func_name not in cache:
            cache[func_name] = func(self)
        return cache[func_name]

    # Returns a property whose getter is the 'wrapper' function
    return property(wrapper)


def cacheable_object(cls):
    """Decorator to add a reset() method that clears cached data.

    Cached data is set by the @resettable_cached_property decorator.
    Technically this could be a mixin...
    """

    def reset(self):
        """Reset the cached properties."""
        self._resettable_cached_properties = {}  # pylint: disable=protected-access

    cls.reset = reset
    return cls


@cacheable_object
class CacheableFieldMixin(object):
    """
    Cachable field mixin.

    Override Field.root and Field.context to make fields/serializers
    cacheable and reusable.

    The DRF version uses @cached_property which doesn't have a
    public API for resetting.
    This version uses normal object variables with and adds a `reset()` API.
    """

    @resettable_cached_property
    def root(self):
        """Find the top level root."""
        root = self
        while root.parent is not None:
            root = root.parent
        return root

    @resettable_cached_property
    def context(self):
        """Get the context from the root."""
        return getattr(self.root, "_context", {})


class GetModelMixin(object):
    """
    Mixin to retrieve model hashid.

    Implementation from
    https://github.com/evenicoulddoit/django-rest-framework-serializer-extensions
    """

    def __init__(self, *args, **kwargs):
        """Initialise the GetModelMixin."""
        self.model = kwargs.pop("model", None)
        super().__init__(*args, **kwargs)

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
        model = self.model
        if model is None:
            if model is None:
                custom_fn_name = f"get_{self.field_name}_model"
                parent = self.parent
                if hasattr(parent, custom_fn_name):
                    self.model = getattr(parent, custom_fn_name)()
                else:
                    try:
                        self.model = parent.Meta.model
                    except AttributeError as exc:
                        raise AssertionError(
                            f'No "model" value passed to field "{type(self).__name__}"'
                        ) from exc
            elif isinstance(model, str):
                self.model = model_from_definition(model)
            else:
                self.model = model
        return self.model
