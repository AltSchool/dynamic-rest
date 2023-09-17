"""This module contains custom data-structures."""
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from dynamic_rest.meta import get_model_field
from dynamic_rest.related import RelatedObject


class FilterNode(object):
    """A node in a filter tree."""

    def __init__(self, field, operator, value):
        """Create an object representing a filter, to be stored in a TreeMap.

        For example, a filter query like `filter{users.events.capacity.lte}=1`
        would be passed into a `FilterNode` as follows:

        ```
            field = ['users', 'events', 'capacity']
            operator = 'lte'
            value = 1
            node = FilterNode(field, operator, value)
        ```

        Arguments:
            field: A list of field parts.
            operator: A valid filter operator, or None.
                Per Django convention, `None` means the equality operator.
            value: The value to filter on.
        """
        self.field = field
        self.operator = operator
        self.value = value

    @property
    def key(self):
        """Key property."""
        return f"{'__'.join(self.field)}{f'__{self.operator}' if self.operator else ''}"

    def generate_query_key(self, serializer):
        """Get the key that can be passed to Django's filter method.

        To account for serializer field name rewrites, this method
        translates serializer field names to model field names
        by inspecting `serializer`.

        For example, a query like `filter{users.events}` would be
        returned as `users__events`.

        Arguments:
            serializer: A DRF serializer

        Returns:
            A filter key.
        """
        rewritten = []
        last = len(self.field) - 1
        s = serializer
        field = None
        for i, field_name in enumerate(self.field):
            # Note: .fields can be empty for related serializers that aren't
            # side-loaded. Fields that are deferred also won't be present.
            # If field name isn't in serializer.fields, get full list from
            # get_all_fields() method. This is somewhat expensive, so only do
            # this if we have to.
            fields = s.fields
            if field_name not in fields:
                fields = getattr(s, "get_all_fields", lambda: {})()

            if field_name == "pk":
                rewritten.append("pk")
                continue

            if field_name not in fields:
                raise ValidationError(f"Invalid filter field: {field_name}")

            field = fields[field_name]

            # For remote fields, strip off '_set' for filtering. This is a
            # weird Django inconsistency.
            model_field_name = field.source or field_name
            model_field = get_model_field(s.get_model(), model_field_name)
            if isinstance(model_field, RelatedObject):
                model_field_name = model_field.field.related_query_name()

            # If get_all_fields() was used above, field could be unbound,
            # and field.source would be None
            rewritten.append(model_field_name)

            if i == last:
                break

            # Recurse into nested field
            s = getattr(field, "serializer", None)
            if isinstance(s, serializers.ListSerializer):
                s = s.child
            if not s:
                raise ValidationError(f"Invalid nested filter field: {field_name}")

        if self.operator:
            rewritten.append(self.operator)

        return "__".join(rewritten), field


class TreeMap(dict):
    """Tree structure implemented with nested dictionaries."""

    def get_paths(self):
        """Get all paths from the root to the leaves.

        For example, given a chain like `{'a':{'b':{'c':None}}}`,
        this method would return `[['a', 'b', 'c']]`.

        Returns:
            A list of lists of paths.
        """
        paths = []
        for key, child in self.items():
            if isinstance(child, TreeMap) and child:
                # current child is an intermediate node
                for path in child.get_paths():
                    path.insert(0, key)
                    paths.append(path)
            else:
                # current child is an endpoint
                paths.append([key])
        return paths

    def insert(self, parts, leaf_value, update=False):
        """Add a list of nodes into the tree.

        The list will be converted into a TreeMap (chain) and then
        merged with the current TreeMap.

        For example, this method would insert `['a','b','c']` as
        `{'a':{'b':{'c':{}}}}`.

        Arguments:
            parts: List of nodes representing a chain.
            leaf_value: Value to insert into the leaf of the chain.
            update: Whether or not to update the leaf with the given value or
                to replace the value.

        Returns:
            self
        """
        tree = self
        if not parts:
            return tree

        cur = tree
        last = len(parts) - 1
        for i, part in enumerate(parts):
            if part not in cur:
                cur[part] = TreeMap() if i != last else leaf_value
            elif i == last:  # found leaf
                if update:
                    cur[part].update(leaf_value)
                else:
                    cur[part] = leaf_value

            cur = cur[part]

        return self
