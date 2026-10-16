"""Module containing Django meta helpers."""
from __future__ import annotations

from functools import lru_cache
from itertools import chain

from django.core.exceptions import FieldDoesNotExist
from django.db.models import ManyToOneRel
from django.db.models import OneToOneRel
from django.db.models import (
    ForeignKey,
    ManyToManyField,
    ManyToManyRel,
    Model,
    OneToOneField,
)

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


@lru_cache()
def get_model_relationships(meta) -> dict:
    """Return a dictionary of all relationships on a model."""
    related_objs = (
        f
        for f in meta.get_fields()
        if (f.one_to_many or f.one_to_one) and f.auto_created and not f.concrete
    )
    related_m2m_objs = (
        f
        for f in meta.get_fields(include_hidden=True)
        if f.many_to_many and f.auto_created
    )
    return {o.get_accessor_name(): o for o in chain(related_objs, related_m2m_objs)}


def get_model_field(model: Model | None, field_name):
    """Return a field given a model and field name.

    Arguments:
        model: a Django model
        field_name: the name of a field

    Returns:
        A Django field if `field_name` is a valid field for `model`,
            None otherwise.
    """
    if not model:
        # TODO: This might be a bug.
        return None

    meta = model._meta  # pylint: disable=protected-access
    try:
        return meta.get_field(field_name)
    except FieldDoesNotExist as exc:
        cache = get_model_relationships(meta)

        if field_name in cache:
            return cache[field_name]

        raise AttributeError(f"{field_name} is not a valid field for {model}") from exc


def get_model_field_and_type(model, field_name):
    """Return a field and its type given a model and field name."""
    field = get_model_field(model, field_name)

    type_map = [
        (OneToOneField, "o2o"),
        (OneToOneRel, "o2or"),  # is subclass of m2o so check first
        (ManyToManyField, "m2m"),
        (ManyToOneRel, "m2o"),
        (ManyToManyRel, "m2m"),
        (ForeignKey, "fk"),  # check last
    ]
    for cls, type_str in type_map:
        if isinstance(field, cls):
            return (
                field,
                type_str,
            )

    return (
        field,
        "",
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
    if not hasattr(model, "_meta"):
        # ephemeral model with no metaclass
        return False

    model_field = get_model_field(model, field_name)
    return isinstance(model_field, (ManyToManyField, RelatedObject))


def get_lookup_path(model, source):
    """Convert a serializer field source into an ORM lookup path.

    A source may span relations using dots, for example
    'profile.display_name'. The ORM expects '__' between the parts, and
    refers to reverse relations by their related query name rather than
    by the accessor name used on model instances ('user_set' -> 'user').
    Parts after the first one that cannot be resolved are kept as they are.

    Arguments:
        model: the model the source is relative to, or None if unknown
        source: a serializer field source

    Returns:
        The lookup path, for example 'location__user__name'.
    """
    parts = []
    for name in source.split("."):
        field = None
        if model is not None:
            try:
                field = get_model_field(model, name)
            except AttributeError:
                field = None
        if isinstance(field, RelatedObject):
            name = field.field.related_query_name()
        parts.append(name)
        model = getattr(field, "related_model", None)
    return "__".join(parts)


def get_model_table(model):
    """Return the table name for a given model."""
    return model._meta.db_table  # pylint: disable=protected-access
