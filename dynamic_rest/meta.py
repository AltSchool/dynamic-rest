"""Module containing Django meta helpers."""
from itertools import chain

from django.db import models

from dynamic_rest.related import RelatedObject
from dynamic_rest.compat import DJANGO110


class Meta(object):
    _instances = {}

    def __new__(cls, model):
        key = model._meta.db_table if hasattr(model, '_meta') else model
        if key not in cls._instances:
            cls._instances[key] = object.__new__(cls, model)
        return cls._instances.get(key)

    def __init__(self, model):
        self.model = model
        self.fields = {}  # lazy
        self.meta = getattr(self.model, '_meta', None)

    @classmethod
    def get_related_model(cls, field):
        return field.related_model if field else None

    def is_field(self, field_name):
        """Check whether a given field exists on a model.

        Arguments:
            model: a Django model
            field_name: the name of a field

        Returns:
            True if `field_name` exists on `model`, False otherwise.
        """
        try:
            self.get_field(field_name)
            return True
        except AttributeError:
            return False

    def get_pk_field(self):
        return self.get_field(self.meta.pk.name)

    def get_field(self, field_name):
        """Return a field given a model and field name.

        The field name may contain dots (.), indicating
        a remote field.

        Arguments:
            model: a Django model
            field_name: the name of a field

        Returns:
            A Django field if `field_name` is a valid field for `model`,
                None otherwise.
        """
        if field_name in self.fields:
            return self.fields[field_name]

        field = None
        model = self.model
        meta = self.meta

        if '.' in field_name:
            parts = field_name.split('.')
            last = len(parts) - 1
            for i, part in enumerate(parts):
                if i == last:
                    field_name = part
                    break
                field = get_model_field(model, part)
                model = get_related_model(field)
                if not model:
                    raise AttributeError(
                        '%s is not a related field on %s' % (
                            part,
                            model
                        )
                    )
                meta = model._meta

        try:
            if DJANGO110:
                field = meta.get_field(field_name)
            else:
                field = meta.get_field_by_name(field_name)[0]
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
                field = related_objects[field_name]

        if not field:
            raise AttributeError(
                '%s is not a valid field for %s' % (field_name, model)
            )

        self.fields[field_name] = field
        return field

    def is_field_remote(self, field_name):
        """Check whether a given model field is a remote field.

        A remote field is the inverse of a one-to-many or a
        many-to-many relationship.

        Arguments:
            model: a Django model
            field_name: the name of a field

        Returns:
            True if `field_name` is a remote field, False otherwise.
        """
        try:
            model_field = self.get_field(field_name)
            return isinstance(
                model_field,
                (models.ManyToManyField, RelatedObject)
            )
        except AttributeError:
            return False

    def get_table(self):
        return self.meta.db_table


def get_model_table(model):
    return Meta(model).get_table()


def get_related_model(field):
    return Meta.get_related_model(field)


def is_model_field(model, field_name):
    return Meta(model).is_field(field_name)


def get_model_field(model, field_name):
    return Meta(model).get_field(field_name)


def is_field_remote(model, field_name):
    return Meta(model).is_field_remote(field_name)
