"""Generic relation field for dynamic_rest."""
from __future__ import annotations

from django.db import models
from rest_framework.exceptions import ValidationError

from dynamic_rest.fields.common import WithRelationalFieldMixin
from dynamic_rest.fields.fields import DynamicField
from dynamic_rest.routers import DynamicRouter
from dynamic_rest.tagged import TaggedDict


class DynamicGenericRelationField(WithRelationalFieldMixin, DynamicField):
    """Generic relation field for dynamic_rest."""

    def __init__(self, *args, embed=False, **kwargs):
        """Initialise the DynamicGenericRelationField."""
        if "requires" in kwargs:
            raise RuntimeError(
                "DynamicGenericRelationField does not support manual"
                " overriding of 'requires'."
            )
        super().__init__(*args, **kwargs)
        self.embed = embed

    def bind(self, field_name, parent):
        """Bind the field to the parent serializer."""
        super().bind(field_name, parent)

        source = self.source or field_name

        # Inject `requires` so required fields get prefetched properly.
        # TODO: It seems like we should be able to require the type and
        #       id fields, but that seems to conflict with some internal
        #       Django magic. Disabling `.only()` by requiring '*' seem
        #       to work more reliably...
        self.requires = [f"{source}.*", "*"]

        # Get request fields to support sideloading, but disallow field
        # inclusion/exclusion.
        request_fields = self._get_request_fields_from_parent()
        if isinstance(request_fields, dict) and len(request_fields):
            raise ValidationError(
                f"{self.parent.get_name()}.{self.field_name}"
                " does not support field inclusion/exclusion"
            )
        self.request_fields = request_fields

    def id_only(self):
        """Return whether the field is id_only."""
        # For DynamicRelationFields, id_only() is a serializer responsibility
        # but for generic relations, we want IDs to be represented differently
        # and that is a field-level concern, not an object-level concern,
        # so we handle it here.
        return not self.parent.is_field_sideloaded(self.field_name)

    @staticmethod
    def get_pk_object(type_key, id_value):
        """Get the pk object."""
        return {"type": type_key, "id": id_value}

    @staticmethod
    def get_serializer_class_for_instance(instance):
        """Get the serializer class for the instance."""
        return DynamicRouter.get_canonical_serializer(
            resource_key=None, instance=instance
        )

    def to_representation(self, value):
        """Convert the instance to a representation."""
        # Find serializer for the instance
        serializer_class = self.get_serializer_class_for_instance(value)
        if not serializer_class:
            # Can't find canonical serializer! For now, just return
            # object name and ID, and hope the client knows what to do
            # with it.
            return self.get_pk_object(
                value._meta.object_name, value.pk  # pylint: disable=protected-access
            )

        # We want the pk to be represented as an object with type,
        # rather than just the ID.
        pk_value = self.get_pk_object(serializer_class.get_name(), value.pk)
        if self.id_only():
            return pk_value

        # Serialize the object. Note that request_fields is set, but
        # field inclusion/exclusion is disallowed via check in bind()
        representation = serializer_class(
            dynamic=True,
            request_fields=self.request_fields,
            context=self.context,
            embed=self.embed,
        ).to_representation(value)

        # Pass pk object that contains type and ID to TaggedDict object
        # so that Processor can use it when the field gets side-loaded.
        if isinstance(representation, TaggedDict):
            representation.pk_value = pk_value
        return representation

    def to_internal_value(self, data: dict) -> models.Model | None:
        """Convert the data to an internal value."""
        model_name = data.get("type", None)
        model_id = data.get("id", None)
        if not (model_name and model_id):
            return None

        serializer_class = DynamicRouter.get_canonical_serializer(
            resource_key=None, resource_name=model_name
        )
        if not serializer_class:
            return None
        model = serializer_class.get_model()
        return model.objects.get(id=model_id) if model else None
