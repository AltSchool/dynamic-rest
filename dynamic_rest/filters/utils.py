"""Filter utils."""
from __future__ import annotations

from django.core.exceptions import FieldDoesNotExist
from django.db.models import Max, Min, Q, QuerySet
from rest_framework.exceptions import ValidationError

from dynamic_rest.compat import RestFrameworkBooleanField
from dynamic_rest.constants import VALID_FILTER_OPERATORS
from dynamic_rest.datastructures import FilterNode, TreeMap
from dynamic_rest.serializers import DynamicModelSerializer
from dynamic_rest.utils import is_truthy


def _or(a: Q, b: Q) -> Q:
    """Return a or b."""
    return a | b


def _and(a: Q, b: Q) -> Q:
    """Return a and b."""
    return a & b


def has_joins(queryset: QuerySet) -> bool:
    """Return True iff. a queryset includes joins.

    If this is the case, it is possible for the queryset
    to return duplicate results.

    Superseded by `has_multivalued_joins`, which only reports joins that
    can actually repeat rows. Kept for backwards compatibility.

    Arguments:
        queryset: A queryset.

    Returns:
        True if the queryset includes joins.
    """
    return any(join.join_type for join in queryset.query.alias_map.values())


def _is_multivalued(field) -> bool:
    """Return True if following a relation field can match several rows.

    That is the case for many-to-many and reverse foreign key / generic
    relations, and for a field that does not guarantee a unique target (see
    `has_multivalued_joins`). Used for joins and for ordering alike.
    """
    return (
        field.one_to_many
        or field.many_to_many
        or not getattr(field, "requires_unique_target", True)
    )


def path_is_multivalued(model, path: str) -> bool:
    """Return True if a lookup path crosses a multi-valued relation.

    Arguments:
        model: the model the path starts at.
        path: a lookup path such as 'groups__name'.

    Returns:
        True if any relation along the path can match several rows. Once a
        part is not a field of the model (a transform, an annotation) the
        rest of the path is ignored.
    """
    for part in path.split("__"):
        try:
            field = model._meta.get_field(part)  # pylint: disable=protected-access
        except FieldDoesNotExist:
            return False
        if not field.is_relation or field.related_model is None:
            return False
        if _is_multivalued(field):
            return True
        model = field.related_model
    return False


def default_ordering(queryset: QuerySet) -> tuple:
    """Return the model's default ordering if it applies to a queryset.

    The default ordering only applies when no ordering was requested.
    """
    query = queryset.query
    if query.order_by or not query.default_ordering:
        return ()
    return tuple(query.get_meta().ordering or ())


def ordering_is_multivalued(model, terms) -> bool:
    """Return True if any ordering term crosses a multi-valued relation.

    Ordering by an expression is not inspected.
    """
    return any(
        path_is_multivalued(model, term.lstrip("-"))
        for term in terms
        if isinstance(term, str) and term != "?"
    )


def order_by_unique_rows(queryset: QuerySet, terms) -> QuerySet:
    """Order a queryset without repeating rows.

    Ordering by a column across a multi-valued relation joins to every
    related row, which repeats the row once per related row, and DISTINCT
    cannot remove them because the ordering column is part of the SELECT.
    Such a term orders by the smallest related value instead (the largest
    when descending), computed per row, so each row appears once.

    Arguments:
        queryset: the queryset to order.
        terms: ordering terms as given to `order_by()`.

    Returns:
        The ordered queryset.
    """
    annotations = {}
    ordering = []
    for index, term in enumerate(terms):
        if not isinstance(term, str) or term == "?":
            ordering.append(term)
            continue
        descending = term.startswith("-")
        path = term.lstrip("-")
        if not path_is_multivalued(queryset.model, path):
            ordering.append(term)
            continue
        alias = f"dynamic_rest_order_{index}"
        annotations[alias] = (Max if descending else Min)(path)
        ordering.append(f"-{alias}" if descending else alias)
    if annotations:
        queryset = queryset.annotate(**annotations)
    return queryset.order_by(*ordering)


def has_multivalued_joins(queryset: QuerySet) -> bool:
    """Return True iff. a queryset joins across a multi-valued relation.

    Only joins that can match several rows per row of the base table
    (many-to-many and reverse foreign key / generic relations) can make
    the queryset return duplicate results. Joins that follow a forward
    foreign key or a one-to-one relation cannot.

    Django's system checks (fields.E310 / fields.E311) require the target of a
    forward foreign key or foreign object to be unique, which is why such a
    join is single-valued. A custom field class that opts out by setting
    `requires_unique_target = False` gives no such guarantee, so joins across
    it are treated as multi-valued. So is a join that cannot be classified.
    A project that silences those system checks for a field takes
    responsibility for the field's joins returning one row.

    Arguments:
        queryset: A queryset.

    Returns:
        True if the queryset can return duplicate results.
    """
    for join in queryset.query.alias_map.values():
        if not join.join_type:
            continue
        join_field = getattr(join, "join_field", None)
        if join_field is None or _is_multivalued(join_field):
            return True
    return False


def rewrite_filters(
    filters: TreeMap, serializer: DynamicModelSerializer
) -> dict[str, str | bool]:
    """Rewrite filter keys to use model field names."""
    out = {}
    for node in filters.values():
        filter_key, field = node.generate_query_key(serializer)
        if isinstance(field, RestFrameworkBooleanField):
            node.value = is_truthy(node.value)
        out[filter_key] = node.value
    return out


def _is_scalar(value) -> bool:
    """Return True if a JSON value is a string, number, boolean or null."""
    return value is None or isinstance(value, (str, int, float, bool))


def _check_clause_value(name: str, operator: str | None, value) -> None:
    """Check that the value of a filter clause has the shape its operator needs.

    Arguments:
        name: the clause key, as the client wrote it, for the error message.
        operator: the operator of the clause, or None for an exact match.
        value: the value from the filter{} JSON object.

    Raises:
        ValidationError: if the value is not usable with the operator.
    """
    if operator == "in":
        if not isinstance(value, list) or not all(_is_scalar(v) for v in value):
            raise ValidationError(f'"{name}" expects a list of single values.')
    elif operator == "range":
        if (
            not isinstance(value, list)
            or len(value) != 2
            or not all(_is_scalar(v) and v is not None for v in value)
        ):
            raise ValidationError(f'"{name}" expects two single values, neither null.')
    elif operator == "isnull":
        if not isinstance(value, bool):
            raise ValidationError(f'"{name}" expects true or false.')
    elif not _is_scalar(value):
        hint = "" if operator else f' Use "{name}.in" to match several values.'
        raise ValidationError(f'"{name}" expects a single value.{hint}')


def clause_to_q(clause: tuple[str, str | int], serializer: DynamicModelSerializer) -> Q:
    """Convert a filter clause to a Django Q object."""
    key, value = clause
    name = key.lstrip("-")
    negate = False
    if key.startswith("-"):
        negate = True
        key = key[1:]
    parts = key.split(".")
    operator = parts.pop() if parts[-1] in VALID_FILTER_OPERATORS else "eq"
    if operator == "eq":
        operator = None
    node = FilterNode(parts, operator, value)
    key, _ = node.generate_query_key(serializer)
    _check_clause_value(name, operator, value)
    q = Q(**{key: node.value})
    if negate:
        q = ~q
    return q
