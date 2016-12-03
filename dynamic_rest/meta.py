"""Module containing Django meta helpers."""
from itertools import chain

from django import VERSION
from django.db.models import ManyToManyField

from dynamic_rest.related import RelatedObject

DJANGO110 = VERSION >= (1, 10)


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
        if DJANGO110:
            field = meta.get_field(field_name)
        else:
            field = meta.get_field_by_name(field_name)[0]
        return field
    except:
        if DJANGO110:
            related_objs = (
                f for f in meta.get_fields()
                if (f.one_to_many or f.one_to_one)
                and f.auto_created and not f.concrete
            )
            related_m2m_objs = (
                f for f in meta.get_fields(include_hidden=True)
                if f.many_to_many and f.auto_created
            )
        else:
            related_objs = meta.get_all_related_objects()
            related_m2m_objs = meta.get_all_related_many_to_many_objects()

        related_objects = {
            o.get_accessor_name(): o
            for o in chain(related_objs, related_m2m_objs)
        }
        if field_name in related_objects:
            return related_objects[field_name]
        else:
            # check virtual fields (1.7)
            if hasattr(meta, 'virtual_fields'):
                for field in meta.virtual_fields:
                    if field.name == field_name:
                        return field

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


def get_related_model(field):
    try:
        # django 1.8+
        return field.related_model
    except AttributeError:
        # django 1.7
        if hasattr(field, 'field'):
            return field.field.model
        elif hasattr(field, 'rel'):
            return field.rel.to
        elif field.__class__.__name__ == 'GenericForeignKey':
            return None
        else:
            raise


def get_model_table(model):
    try:
        return model._meta.db_table
    except:
        return None
