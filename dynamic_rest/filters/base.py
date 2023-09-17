"""Base filter backend for DREST."""
from __future__ import annotations

from functools import reduce
from typing import Any

from django.core.exceptions import ValidationError as InternalValidationError
from django.db.models import Manager, Model, Prefetch, Q, QuerySet
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import Field
from rest_framework.filters import BaseFilterBackend
from rest_framework.request import Request

from dynamic_rest.conf import settings
from dynamic_rest.constants import VALID_FILTER_OPERATORS
from dynamic_rest.datastructures import FilterNode, TreeMap
from dynamic_rest.fields import DynamicRelationField
from dynamic_rest.filters.utils import (
    _and,
    _or,
    clause_to_q,
    has_joins,
    rewrite_filters,
)
from dynamic_rest.meta import get_model_field, is_field_remote, is_model_field
from dynamic_rest.prefetch import FastPrefetch
from dynamic_rest.serializers import DynamicModelSerializer
from dynamic_rest.utils import is_truthy

DEBUG = settings.DEBUG


class DynamicFilterBackend(BaseFilterBackend):
    """A DRF filter backend that constructs DREST QuerySets.

    This backend is responsible for interpreting and applying
    filters, includes, and excludes to the base queryset of a view.
    """

    def filter_queryset(self, request: Request, queryset: QuerySet, view) -> QuerySet:
        """Filter the queryset.

        This is the main entry-point to this class, and
        is called by DRF's list handler.
        """
        self.request = request
        self.view = view

        # enable addition of extra filters (i.e., a Q())
        # so custom filters can be added to the queryset without
        # running into https://code.djangoproject.com/ticket/18437
        # which, without this, would mean that filters added to the queryset
        # after this is called may not behave as expected
        extra_filters = self.view.get_extra_filters(request)

        disable_prefetches = self.view.is_update()

        return self._build_queryset(
            queryset=queryset,
            extra_filters=extra_filters,
            disable_prefetches=disable_prefetches,
        )

    # This function was renamed and broke downstream dependencies that haven't
    # been updated to use the new naming convention.

    def _extract_filters(self, **kwargs) -> TreeMap:
        """Extract filters from the request."""
        return self._get_requested_filters(**kwargs)

    def _get_requested_filters(self, **kwargs) -> TreeMap:
        """Get filters from the request.

        Convert 'filters' query params into a dict that can be passed
        to Q. Returns a dict with two fields, 'include' and 'exclude',
        which can be used like:

          result = self._get_requested_filters()
          q = Q(**result['include'] & ~Q(**result['exclude'])
        """
        out = TreeMap()
        filters_map = kwargs.get("filters_map") or self.view.get_request_feature(
            self.view.FILTER
        )
        if getattr(self, "view", None):
            out["_complex"] = self.view.get_request_feature(self.view.FILTER, raw=True)

        for spec, value in filters_map.items():
            # Inclusion or exclusion?
            if spec[0] == "-":
                spec = spec[1:]
                inex = "_exclude"
            else:
                inex = "_include"

            # for relational filters, separate out relation path part
            if "|" in spec:
                rel, spec = spec.split("|")
                rel = rel.split(".")
            else:
                rel = None

            parts = spec.split(".")

            # Last part could be operator, e.g. "events.capacity.gte"
            if len(parts) > 1 and parts[-1] in VALID_FILTER_OPERATORS:
                operator = parts.pop()
            else:
                operator = None

            # All operators except 'range' and 'in' should have one value
            if operator == "range":
                value = value[:2]
            elif operator == "in":
                # no-op: i.e. accept `value` as an arbitrarily long list
                pass
            elif operator in VALID_FILTER_OPERATORS:
                value = value[0]
                if operator == "isnull" and isinstance(value, str):
                    value = is_truthy(value)
                elif operator == "eq":
                    operator = None

            node = FilterNode(parts, operator, value)

            # insert into output tree
            path = rel if rel else []
            path += [inex, node.key]
            out.insert(path, node)

        return out

    def _filters_to_query(
        self, filters: dict[str, dict[Any, Any]], serializer, q: Q = None
    ) -> Q | None:
        """Construct Django Query object from request.

        Arguments are dictionaries, which will be passed to Q() as kwargs.

        e.g.
            includes = { 'foo' : 'bar', 'baz__in' : [1, 2] }
          produces:
            Q(foo='bar', baz__in=[1, 2])

        Arguments:
          includes: TreeMap representing inclusion filters.
          excludes: TreeMap representing exclusion filters.
          filters: TreeMap with include/exclude filters OR query map
          serializer: serializer instance of top-level object
          q: Q() object (optional)

        Returns:
          Q() instance or None if no inclusion or exclusion filters
          were specified.
        """
        complex_filters = filters.get("_complex")
        q = q or Q()
        if not complex_filters:
            includes = filters.get("_include")
            excludes = filters.get("_exclude")

            if not includes and not excludes:
                return None

            if includes:
                includes = rewrite_filters(includes, serializer)
                q &= Q(**includes)
            if excludes:
                excludes = rewrite_filters(excludes, serializer)
                for k, v in excludes.items():
                    q &= ~Q(**{k: v})
            return q

        filters = complex_filters

        if ors := filters.get(".or") or filters.get("$or"):
            return reduce(
                _or,
                [self._filters_to_query({"_complex": f}, serializer) for f in ors],
            )

        if ands := filters.get(".and") or filters.get("$and"):
            return reduce(
                _and,
                [self._filters_to_query({"_complex": f}, serializer) for f in ands],
            )

        clauses = [clause_to_q(clause, serializer) for clause in filters.items()]
        return reduce(_and, clauses) if clauses else q

    def _create_prefetch(self, source: str, queryset: QuerySet) -> Prefetch:
        """Create a Prefetch object."""
        return Prefetch(source, queryset=queryset)

    def _build_implicit_prefetches(
        self,
        model: Model,
        prefetches: dict[str, Prefetch | FastPrefetch],
        requirements: dict[str, str | dict],
    ) -> dict[str, Prefetch]:
        """Build a prefetch dictionary based on internal requirements."""
        for source, remainder in requirements.items():
            if not remainder or isinstance(remainder, str):
                # no further requirements to prefetch
                continue

            related_field = get_model_field(model, source)
            related_model = related_field.related_model

            queryset = (
                self._build_implicit_queryset(related_model, remainder)
                if related_model
                else None
            )

            prefetches[source] = self._create_prefetch(source, queryset)

        return prefetches

    def _make_model_queryset(self, model: Model) -> QuerySet:
        """Make a queryset for a model."""
        return model.objects.all()

    def _build_implicit_queryset(self, model: Model, requirements: TreeMap) -> QuerySet:
        """Build a queryset based on implicit requirements."""
        queryset = self._make_model_queryset(model)
        prefetches = {}
        self._build_implicit_prefetches(model, prefetches, requirements)
        prefetch = prefetches.values()
        queryset = queryset.prefetch_related(*prefetch).distinct()
        if DEBUG:
            queryset._using_prefetches = prefetches  # pylint: disable=protected-access
        return queryset

    def _build_requested_prefetches(
        self,
        prefetches: dict[str, Prefetch | FastPrefetch],
        requirements: TreeMap,
        model: Model,
        fields: dict[str, Field],
        filters: TreeMap,
    ):
        """Build a prefetch dictionary based on request requirements."""
        for name, field in fields.items():
            original_field = field
            if isinstance(field, DynamicRelationField):
                field = field.serializer
            if isinstance(field, serializers.ListSerializer):
                field = field.child
            if not isinstance(field, serializers.ModelSerializer):
                continue

            source = field.source or name
            if "." in source:
                raise ValidationError("nested relationship values are not supported")

            if source in prefetches:
                # ignore duplicated sources
                continue

            is_remote = is_field_remote(model, source)
            is_id_only = getattr(field, "id_only", lambda: False)()
            if is_id_only and not is_remote:
                continue

            related_queryset = getattr(original_field, "queryset", None)

            if callable(related_queryset):
                related_queryset = related_queryset(field)

            source = field.source or name
            # Popping the source here (during explicit prefetch construction)
            # guarantees that implicitly required prefetches that follow will
            # not conflict.
            required = requirements.pop(source, None)

            prefetch_queryset = self._build_queryset(
                serializer=field,
                filters=filters.get(name, {}),
                queryset=related_queryset,
                requirements=required,
            )

            # Note: There can only be one prefetch per source, even
            #       though there can be multiple fields pointing to
            #       the same source. This could break in some cases,
            #       but is mostly an issue on writes when we use all
            #       fields by default.
            prefetches[source] = self._create_prefetch(source, prefetch_queryset)

        return prefetches

    @staticmethod
    def _get_implicit_requirements(
        fields: dict[str, Field], requirements: TreeMap
    ) -> None:
        """Extract internal prefetch requirements from serializer fields."""
        for field in fields.values():
            source = field.source
            # Requires may be manually set on the field -- if not,
            # assume the field requires only its source.
            requires = getattr(field, "requires", None) or [source]
            for require in requires:
                if not require:
                    # ignore fields with empty source
                    continue

                requirement = require.split(".")
                if requirement[-1] == "":
                    # Change 'a.b.' -> 'a.b.*',
                    # supporting 'a.b.' for backwards compatibility.
                    requirement[-1] = "*"
                requirements.insert(requirement, TreeMap(), update=True)

    def _get_queryset(
        self, queryset: QuerySet | None = None, serializer=None
    ) -> QuerySet:
        """Get the base queryset for this request."""
        if serializer and queryset is None:
            queryset = serializer.Meta.model.objects

        return queryset

    def _serializer_filter(
        self, serializer: DynamicModelSerializer, queryset: QuerySet
    ) -> QuerySet:
        """Filter a queryset using a serializer's filter_queryset method."""
        return serializer.filter_queryset(queryset)

    def _build_queryset(
        self,
        serializer: DynamicModelSerializer | None = None,
        filters: TreeMap = None,
        queryset: QuerySet = None,
        requirements: TreeMap = None,
        extra_filters: Q | None = None,
        disable_prefetches: bool = False,
    ) -> QuerySet:
        """Build a queryset that pulls in all data required by this request.

        Handles nested prefetching of related data and deferring fields
        at the queryset level.

        Arguments:
            serializer: An optional serializer to use a base for the queryset.
                If no serializer is passed, the `get_serializer` method will
                be used to initialize the base serializer for the viewset.
            filters: An optional TreeMap of nested filters.
            queryset: An optional base queryset.
            requirements: An optional TreeMap of nested requirements.
            extra_filters: An optional Q() object to add to the queryset.
            disable_prefetches: An optional flag to disable prefetching.
        """
        is_root_level = False
        if not serializer:
            serializer = self.view.get_serializer()
            is_root_level = True

        queryset = self._get_queryset(queryset=queryset, serializer=serializer)

        model = getattr(serializer.Meta, "model", None)

        if not model:
            return queryset

        prefetches = {}

        # build a nested Prefetch queryset
        # based on request parameters and serializer fields
        fields = serializer.fields

        if requirements is None:
            requirements = TreeMap()

        self._get_implicit_requirements(fields, requirements)

        if implicitly_included := set(requirements.keys()) - set(fields.keys()):
            all_fields = serializer.get_all_fields()
            fields.update(
                {
                    field: all_fields[field]
                    for field in implicitly_included
                    if field in all_fields
                }
            )

        if filters is None:
            filters = self._get_requested_filters()

        # build nested Prefetch queryset
        self._build_requested_prefetches(
            prefetches, requirements, model, fields, filters
        )

        # build remaining prefetches out of internal requirements
        # that are not already covered by request requirements
        self._build_implicit_prefetches(model, prefetches, requirements)

        # use requirements at this level to limit fields selected
        # only do this for GET requests where we are not requesting the
        # entire fieldset
        if (
            "*" not in requirements
            and not self.view.is_update()
            and not self.view.is_delete()
        ):
            id_fields = getattr(serializer, "get_id_fields", lambda: [])()
            # only include local model fields
            only = [
                field
                for field in set(id_fields + list(requirements.keys()))
                if is_model_field(model, field) and not is_field_remote(model, field)
            ]
            queryset = queryset.only(*only)

        # add request filters
        query = self._filters_to_query(filters=filters, serializer=serializer)

        # add additional filters specified by calling view
        if extra_filters:
            query = extra_filters if not query else extra_filters & query

        if query:
            # Convert internal django ValidationError to
            # APIException-based one in order to resolve validation error
            # from 500 status code to 400.
            try:
                queryset = queryset.filter(query)
            except InternalValidationError as e:
                raise ValidationError(
                    dict(e) if hasattr(e, "error_dict") else list(e)
                ) from e
            except Exception as exc:
                # Some other Django error in parsing the filter.
                # Very likely a bad query, so throw a ValidationError.
                err_msg = getattr(exc, "message", "")
                raise ValidationError(err_msg) from exc

        # A serializer can have this optional function
        # to dynamically apply additional filters on
        # any queries that will use that serializer
        # You could use this to have (for example) different
        # serializers for different subsets of a model or to
        # implement permissions which work even in side-loads
        if hasattr(serializer, "filter_queryset"):
            queryset = self._serializer_filter(serializer=serializer, queryset=queryset)

        # add prefetches and remove duplicates if necessary
        prefetch = prefetches.values()
        if prefetch and not disable_prefetches:
            queryset = queryset.prefetch_related(*prefetch)
        elif isinstance(queryset, Manager):
            queryset = queryset.all()
        if has_joins(queryset) or not is_root_level:
            queryset = queryset.distinct()

        if DEBUG:
            queryset._using_prefetches = prefetches  # pylint: disable=protected-access
        return queryset
