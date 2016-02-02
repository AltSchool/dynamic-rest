"""Module containing Django meta helpers."""
from itertools import chain

from django.db.models import ManyToManyField

from dynamic_rest.related import RelatedObject


def is_model_field(model, field_name):
    """Check whether a given field exists on a model.

    Arguments:
        model: a Django model
        field_name: the name of a field

    Returns:
        True if `field_name` exists on `model`, False otherwise.
    """
    try:
        get_model_field(model, field_name)
        return True
    except AttributeError:
        return False


def get_model_field(model, field_name):
    """Return a field given a model and field name.

    Arguments:
        model: a Django model
        field_name: the name of a field

    Returns:
        A Django field if `field_name` is a valid field for `model`,
            None otherwise.
    """
    meta = model._meta
    try:
        return meta.get_field_by_name(field_name)[0]
    except:
        related_objects = {
            o.get_accessor_name(): o
            for o in chain(
                meta.get_all_related_objects(),
                meta.get_all_related_many_to_many_objects()
            )
        }
        if field_name in related_objects:
            return related_objects[field_name]
        else:
            raise AttributeError(
                '%s is not a valid field for %s' % (field_name, model)
            )


def is_field_remote(model, field_name):
    """Check whether a given model field is a remote field.

    A remote field is the inverse of a one-to-many or a
    many-to-many relationship.

    Arguments:
        model: a Django model
        field_name: the name of a field

    Returns:
        True if `field_name` is a remote field, False otherwise.
    """
    if not hasattr(model, '_meta'):
        # ephemeral model with no metaclass
        return False

    model_field = get_model_field(model, field_name)
    return isinstance(model_field, (ManyToManyField, RelatedObject))
