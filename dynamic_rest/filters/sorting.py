"""Sorting filter."""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ImproperlyConfigured
from django.db.models import QuerySet
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.serializers import SerializerMetaclass

from dynamic_rest.fields import DynamicRelationField

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
        if ordering := self.get_ordering(request, queryset, view):
            queryset = queryset.order_by(*ordering)
            if any("__" in o for o in ordering):
                # add distinct() to remove duplicates
                # in case of order-by-related
                queryset = queryset.distinct()
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
                raise ValidationError(f"Invalid filter field: {invalid_ordering}")
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
            reverse_sort_term = "" if len(stripped_term) is len(term) else "-"
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
                and isinstance(field, DynamicRelationField)
            ):
                return None

            model_chain.append(field.source or segment)

            serializer = field.serializer_class()

        last_segment = serializer_chain[-1]
        last_field = serializer.get_all_fields().get(last_segment)

        if not last_field or last_field.source == "*":
            return None

        model_chain.append(last_field.source or last_segment)

        return "__".join(model_chain)

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
                f"Cannot use { self.__class__.__name__} on a view which does"
                " not have either a 'serializer_class' or an overriding "
                "'get_serializer_class'."
            )
        return serializer_class
