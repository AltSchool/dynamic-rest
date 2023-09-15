"""Common fields for dynamic_rest."""
from __future__ import annotations

from typing import Any


class WithRelationalFieldMixin(object):
    """Relational field mixin.

    Mostly code shared by DynamicRelationField and DynamicGenericRelationField.
    """

    def _get_request_fields_from_parent(self) -> Any | None:
        """Get request fields from the parent serializer."""
        parent = self.parent
        if not parent:
            return

        fields = getattr(parent, "request_fields", None)
        if not fields:
            return

        if not isinstance(fields, dict):
            return

        return fields.get(self.field_name)
