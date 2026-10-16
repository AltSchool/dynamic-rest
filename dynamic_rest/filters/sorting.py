"""Sorting filter."""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ImproperlyConfigured
from django.db.models import QuerySet
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.serializers import SerializerMetaclass

from dynamic_rest.datastructures import get_filter_choices, protects_write_only_fields
from dynamic_rest.fields import DynamicRelationField
from dynamic_rest.filters.utils import (
    default_ordering,
    order_by_unique_rows,
    ordering_is_multivalued,
)
from dynamic_rest.meta import get_lookup_path

if TYPE_CHECKING:
    from dynamic_rest.viewsets import DynamicModelViewSet


class DynamicSortingFilter(OrderingFilter):
    """Subclass of DRF's OrderingFilter.

    This class adds support for multi-field ordering and rewritten fields.
    """

    def filter_queryset(
        self, request: Request, queryset: QuerySet, view: "DynamicModelViewSet"
    ) -> QuerySet:
        """Filter the queryset, applying the ordering.

        The `ordering_param` can be overwritten here.
        In DRF, the ordering_param is 'ordering', but we support changing it
        to allow the viewset to control the parameter.
        """
        self.ordering_param = view.SORT
        model = queryset.model
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            # The model's default ordering applies when the query is
            # compiled. Take it over only if it needs to be made unique.
            default = default_ordering(queryset)
            if not ordering_is_multivalued(model, default):
                return queryset
            ordering = list(default)

        if ordering_is_multivalued(model, ordering):
            if view.is_update() or view.is_delete():
                # The order does not matter when changing records, and
                # ordering across the relation would repeat them.
                return queryset.order_by()
            # Order each row by its smallest (or largest) related value, so
            # that it is listed once.
            queryset = order_by_unique_rows(queryset, ordering)
        else:
            queryset = queryset.order_by(*ordering)
        # No distinct() here: ordering across a relation that can repeat rows
        # is made unique above (DISTINCT could not do it, because the
        # ordering column is part of the SELECT), the other relations cannot
        # repeat rows, and duplicates from filters are handled by the filter
        # backend.
        return queryset

    def get_ordering(
        self, request: Request, queryset: QuerySet, view: "DynamicModelViewSet"
    ):
        """Return an ordering for a given request.

        DRF expects a comma separated list, while DREST expects an array.
        This method overwrites the DRF default, so it can parse the array.
        """
        if params := view.get_request_feature(view.SORT):
            fields = [param.strip() for param in params]
            valid_ordering, invalid_ordering = self.remove_invalid_fields(
                queryset, fields, view, request
            )

            # if any of the sort fields are invalid, throw an error.
            # else return the ordering
            if invalid_ordering:
                choices = ", ".join(self._get_choices(view))
                raise ValidationError(
                    f"Invalid filter field: {', '.join(invalid_ordering)}. "
                    f"Choices are: {choices}."
                )
            else:
                return valid_ordering

        # No sorting was included
        return self.get_default_ordering(view)

    def remove_invalid_fields(
        self,
        queryset: QuerySet,
        fields: list[str],
        view: "DynamicModelViewSet",
        _: Request,
    ) -> tuple[list[str], list[str]]:
        """Remove invalid fields from an ordering.

        Overwrites the DRF default remove_invalid_fields method to return
        both the valid orderings and any invalid orderings.
        """
        valid_orderings = []
        invalid_orderings = []

        # for each field sent down from the query param,
        # determine if its valid or invalid
        for term in fields:
            stripped_term = term.lstrip("-")
            # add back the '-' add the end if necessary
            reverse_sort_term = "" if len(stripped_term) == len(term) else "-"
            if ordering := self.ordering_for(stripped_term, view):
                valid_orderings.append(reverse_sort_term + ordering)
            else:
                invalid_orderings.append(term)

        return valid_orderings, invalid_orderings

    def ordering_for(self, term: str, view: "DynamicModelViewSet") -> str | None:
        """Override DRF's ordering_for method to support rewritten fields.

        Return ordering (model field chain) for term (serializer field chain)
        or None if invalid

        Raise ImproperlyConfigured if serializer_class not set on view
        """
        if not self._is_allowed_term(term, view):
            return None

        serializer = self._get_serializer_class(view)()
        serializer_chain = term.split(".")

        model_chain = []

        for segment in serializer_chain[:-1]:
            field = serializer.get_all_fields().get(segment)

            if not (
                field
                and field.source != "*"
                and not (field.write_only and protects_write_only_fields(serializer))
                and isinstance(field, DynamicRelationField)
            ):
                return None

            model_chain.append(
                get_lookup_path(serializer.get_model(), field.source or segment)
            )

            serializer = field.serializer_class()

        last_segment = serializer_chain[-1]
        last_field = serializer.get_all_fields().get(last_segment)

        if not last_field or last_field.source == "*":
            return None

        # When write-only fields are protected, they cannot be ordered by:
        # they are never rendered, so this would reveal their values.
        if last_field.write_only and protects_write_only_fields(serializer):
            return None

        # Sources that span relations ('profile.display_name') use '.',
        # but the ORM expects '__'.
        model_chain.append(
            get_lookup_path(serializer.get_model(), last_field.source or last_segment)
        )

        return "__".join(model_chain)

    def _get_choices(self, view: "DynamicModelViewSet") -> list[str]:
        """Return the fields a client can sort on."""
        valid_fields = getattr(view, "ordering_fields", self.ordering_fields)
        if valid_fields is None or valid_fields == "__all__":
            serializer = self._get_serializer_class(view)()
            return get_filter_choices(serializer.get_all_fields())
        return sorted(valid_fields)

    def _is_allowed_term(self, term: str, view: "DynamicModelViewSet") -> bool:
        """Check if a term is allowed to be ordered on."""
        valid_fields = getattr(view, "ordering_fields", self.ordering_fields)
        all_fields_allowed = valid_fields is None or valid_fields == "__all__"

        return all_fields_allowed or term in valid_fields

    def _get_serializer_class(self, view: "DynamicModelViewSet") -> SerializerMetaclass:
        """Get the serializer class from the view."""
        # prefer the overriding method
        if hasattr(view, "get_serializer_class"):
            try:
                serializer_class = view.get_serializer_class()
            except AssertionError:
                # Raised by the default implementation if
                # no serializer_class was found
                serializer_class = None
        # use the attribute
        else:
            serializer_class = getattr(view, "serializer_class", None)

        # neither a method nor an attribute has been specified
        if serializer_class is None:
            raise ImproperlyConfigured(
                f"Cannot use {self.__class__.__name__} on a view which does"
                " not have either a 'serializer_class' or an overriding "
                "'get_serializer_class'."
            )
        return serializer_class
