"""Filter utils."""
from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet

from dynamic_rest.compat import RestFrameworkBooleanField
from dynamic_rest.constants import VALID_FILTER_OPERATORS
from dynamic_rest.datastructures import FilterNode
from dynamic_rest.utils import is_truthy


def _or(a, b):
    """Return a or b."""
    return a | b


def _and(a, b):
    """Return a and b."""
    return a & b


def has_joins(queryset: QuerySet) -> bool:
    """Return True iff. a queryset includes joins.

    If this is the case, it is possible for the queryset
    to return duplicate results.

    Arguments:
        queryset: A queryset.

    Returns:
        True if the queryset includes joins.
    """
    return any(join.join_type for join in queryset.query.alias_map.values())


def rewrite_filters(fs: dict[Any, Any], serializer):
    """Rewrite filter keys to use model field names."""
    out = {}
    for node in fs.values():
        filter_key, field = node.generate_query_key(serializer)
        if isinstance(field, RestFrameworkBooleanField):
            node.value = is_truthy(node.value)
        out[filter_key] = node.value

    return out


def clause_to_q(clause, serializer):
    """Convert a filter clause to a Django Q object."""
    key, value = clause
    negate = False
    if key.startswith("-"):
        negate = True
        key = key[1:]
    parts = key.split(".")
    operator = "eq"
    if parts[-1] in VALID_FILTER_OPERATORS:
        operator = parts.pop()
    if operator == "eq":
        operator = None
    node = FilterNode(parts, operator, value)
    key, _ = node.generate_query_key(serializer)
    q = Q(**{key: node.value})
    if negate:
        q = ~q
    return q
