"""This module contains custom filter backends."""

from django.core.exceptions import ValidationError as InternalValidationError
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q, Prefetch
from django.utils import six
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.filters import BaseFilterBackend, OrderingFilter

from dynamic_rest.utils import is_truthy
from dynamic_rest.conf import settings
from dynamic_rest.datastructures import TreeMap
from dynamic_rest.fields import DynamicRelationField
from dynamic_rest.meta import (
    Meta,
    get_related_model
)
from dynamic_rest.patches import patch_prefetch_one_level

patch_prefetch_one_level()


def has_joins(queryset):
    """Return True iff. a queryset includes joins.

    If this is the case, it is possible for the queryset
    to return duplicate results.
    """
    for join in six.itervalues(queryset.query.alias_map):
        if join.join_type:
            return True
    return False


class WithGetSerializerClass(object):
    def get_serializer_class(self, view=None):
        view = view or getattr(self, 'view', None)
        serializer_class = None
        # prefer the overriding method
        if hasattr(view, 'get_serializer_class'):
            try:
                serializer_class = view.get_serializer_class()
            except AssertionError:
                # Raised by the default implementation if
                # no serializer_class was found
                pass
        # use the attribute
        else:
            serializer_class = getattr(view, 'serializer_class', None)

        if serializer_class is None:
            msg = (
                "Cannot use %s on a view which does not have"
                " a 'serializer_class' attribute."
            )
            raise ImproperlyConfigured(msg % self.__class__.__name__)

        return serializer_class


class DynamicFilterBackend(WithGetSerializerClass, BaseFilterBackend):

    """A DRF filter backend that constructs DREST querysets.

    This backend is responsible for interpretting and applying
    filters, includes, and excludes to the base queryset of a view.

    Attributes:
        VALID_FILTER_OPERATORS: A list of filter operators.
    """

    VALID_FILTER_OPERATORS = (
        'in',
        'any',
        'all',
        'icontains',
        'contains',
        'startswith',
        'istartswith',
        'endswith',
        'iendswith',
        'year',
        'month',
        'day',
        'week_day',
        'regex',
        'range',
        'gt',
        'lt',
        'gte',
        'lte',
        'isnull',
        'eq',
        None,
    )

    def filter_queryset(self, request, queryset, view):
        """Filter the queryset.

        This is the main entry-point to this class, and
        is called by DRF's list handler.
        """
        self.request = request
        self.view = view

        self.DEBUG = settings.DEBUG
        queryset = self._build_queryset(queryset=queryset)
        return queryset

    def _get_requested_filters(self, **kwargs):
        """
        Convert 'filters' query params into a dict that can be passed
        to Q. Returns a dict with two fields, 'include' and 'exclude',
        which can be used like:

            result = self._get_requested_filters()
            q = Q(**result['_include'] & ~Q(**result['_exclude'])

        """

        filters_map = kwargs.get('filters_map')

        view = getattr(self, 'view', None)
        if view:
            serializer_class = view.get_serializer_class()
            serializer = serializer_class()
            if not filters_map:
                filters_map = view.get_request_feature(view.FILTER)
        else:
            serializer = None

        out = TreeMap()

        for key, value in six.iteritems(filters_map):

            # Inclusion or exclusion?
            if key[0] == '-':
                key = key[1:]
                category = '_exclude'
            else:
                category = '_include'

            # for relational filters, separate out relation path part
            if '|' in key:
                rel, key = key.split('|')
                rel = rel.split('.')
            else:
                rel = None

            terms = key.split('.')
            # Last part could be operator, e.g. "events.capacity.gte"
            if len(terms) > 1 and terms[-1] in self.VALID_FILTER_OPERATORS:
                operator = terms.pop()
            else:
                operator = None

            # All operators except 'range' and 'in' should have one value
            if operator == 'range':
                value = value[:2]
            elif operator == 'in':
                # no-op: i.e. accept `value` as an arbitrarily long list
                pass
            elif operator in self.VALID_FILTER_OPERATORS:
                value = value[0]
                if (
                    operator == 'isnull' and
                    isinstance(value, six.string_types)
                ):
                    value = is_truthy(value)
                elif operator == 'eq':
                    operator = None

            if serializer:
                s = serializer

                if rel:
                    # get related serializer
                    model_fields, serializer_fields = serializer.resolve(rel)
                    s = serializer_fields[-1]
                    s = getattr(s, 'serializer', s)
                    rel = [
                        Meta.get_query_name(f) for f in model_fields
                    ]

                # perform model-field resolution
                model_fields, serializer_fields = s.resolve(terms)
                field = serializer_fields[-1] if serializer_fields else None
                # if the field is a boolean,
                # coerce the value
                if field and isinstance(
                    field,
                    (
                        serializers.BooleanField,
                        serializers.NullBooleanField
                    )
                ):
                    value = is_truthy(value)
                key = '__'.join(
                    [Meta.get_query_name(f) for f in model_fields]
                )

            else:
                key = '__'.join(terms)

            if operator:
                key += '__%s' % operator

            # insert into output tree
            path = rel if rel else []
            path += [category, key]
            out.insert(path, value)
        return out

    def _filters_to_query(self, filters):
        """
        Construct Django Query object from request.
        Arguments are dictionaries, which will be passed to Q() as kwargs.

        e.g.
            includes = { 'foo' : 'bar', 'baz__in' : [1, 2] }
        produces:
            Q(foo='bar', baz__in=[1, 2])

        Arguments:
            filters: TreeMap representing inclusion/exclusion filters

        Returns:
            Q() instance or None if no inclusion or exclusion filters
            were specified.
        """

        includes = filters.get('_include')
        excludes = filters.get('_exclude')
        q = Q()

        if not includes and not excludes:
            return None

        if includes:
            q &= Q(**includes)
        if excludes:
            for k, v in six.iteritems(excludes):
                q &= ~Q(**{k: v})
        return q

    def _build_implicit_prefetches(
        self,
        model,
        prefetches,
        requirements
    ):
        """Build a prefetch dictionary based on internal requirements."""

        meta = Meta(model)
        for source, remainder in six.iteritems(requirements):
            if not remainder or isinstance(remainder, six.string_types):
                # no further requirements to prefetch
                continue

            related_field = meta.get_field(source)
            related_model = get_related_model(related_field)

            queryset = self._build_implicit_queryset(
                related_model,
                remainder
            ) if related_model else None

            prefetches[source] = Prefetch(
                source,
                queryset=queryset
            )

        return prefetches

    def _build_implicit_queryset(self, model, requirements):
        """Build a queryset based on implicit requirements."""

        queryset = model.objects.all()
        prefetches = {}
        self._build_implicit_prefetches(
            model,
            prefetches,
            requirements
        )
        prefetch = prefetches.values()
        queryset = queryset.prefetch_related(*prefetch).distinct()
        queryset._using_prefetches = prefetches
        return queryset

    def _build_requested_prefetches(
        self,
        prefetches,
        requirements,
        model,
        fields,
        filters
    ):
        """Build a prefetch dictionary based on request requirements."""
        is_gui = getattr(self.view, 'is_gui', False)
        meta = Meta(model)
        for name, field in six.iteritems(fields):
            original_field = field
            if isinstance(field, DynamicRelationField):
                field = field.serializer
            if isinstance(field, serializers.ListSerializer):
                field = field.child
            if not isinstance(field, serializers.ModelSerializer):
                continue

            source = field.source or name
            if '.' in source:
                raise ValidationError(
                    'Nested relationship values '
                    'are not supported'
                )
            if source == '*':
                # ignore custom getter/setter
                continue

            if source in prefetches:
                # ignore duplicated sources
                continue

            related_queryset = getattr(original_field, 'queryset', None)
            if callable(related_queryset):
                related_queryset = related_queryset(field)

            is_id_only = getattr(field, 'id_only', lambda: False)()
            is_remote = meta.is_field_remote(source)
            if (
                related_queryset is None and
                not is_gui and is_id_only and not is_remote
            ):
                # GUI rendering, full representation, and remote fields
                # should all trigger prefetching
                continue

            # Popping the source here (during explicit prefetch construction)
            # guarantees that implicitly required prefetches that follow will
            # not conflict.
            required = requirements.pop(source, None)

            query_name = Meta.get_query_name(original_field.model_field)
            prefetch_queryset = self._build_queryset(
                serializer=field,
                filters=filters.get(query_name, {}),
                queryset=related_queryset,
                requirements=required
            )

            # There can only be one prefetch per source, even
            # though there can be multiple fields pointing to
            # the same source. This could break in some cases,
            # but is mostly an issue on writes when we use all
            # fields by default.
            prefetches[source] = Prefetch(
                source,
                queryset=prefetch_queryset
            )

        return prefetches

    def _get_implicit_requirements(
        self,
        fields,
        requirements
    ):
        """Extract internal prefetch requirements from serializer fields."""
        for name, field in six.iteritems(fields):
            source = field.source
            # Requires may be manually set on the field -- if not,
            # assume the field requires only its source.
            requires = getattr(field, 'requires', None) or [source]
            for require in requires:
                if not require:
                    # ignore fields with empty source
                    continue

                requirement = require.split('.')
                if requirement[-1] == '':
                    # Change 'a.b.' -> 'a.b.*',
                    # supporting 'a.b.' for backwards compatibility.
                    requirement[-1] = '*'
                requirements.insert(requirement, TreeMap(), update=True)

    def _build_queryset(
        self,
        serializer=None,
        filters=None,
        queryset=None,
        requirements=None
    ):
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
        """

        is_root_level = False
        if serializer:
            if queryset is None:
                queryset = serializer.Meta.model.objects
        else:
            serializer = self.view.get_serializer()
            is_root_level = True

        model = serializer.get_model()

        if not model:
            return queryset

        meta = Meta(model)

        prefetches = {}

        # build a nested Prefetch queryset
        # based on request parameters and serializer fields
        fields = serializer.fields

        if requirements is None:
            requirements = TreeMap()

        self._get_implicit_requirements(
            fields,
            requirements
        )

        if filters is None:
            filters = self._get_requested_filters()

        # build nested Prefetch queryset
        self._build_requested_prefetches(
            prefetches,
            requirements,
            model,
            fields,
            filters
        )

        # build remaining prefetches out of internal requirements
        # that are not already covered by request requirements
        self._build_implicit_prefetches(
            model,
            prefetches,
            requirements
        )

        # use requirements at this level to limit fields selected
        # only do this for GET requests where we are not requesting the
        # entire fieldset
        is_gui = getattr(self.view, 'is_gui', False)
        if (
            '*' not in requirements and
            not self.view.is_update() and
            not self.view.is_delete() and
            not is_gui
        ):
            id_fields = getattr(serializer, 'get_id_fields', lambda: [])()
            # only include local model fields
            only = [
                field for field in set(
                    id_fields + list(requirements.keys())
                ) if meta.is_field(field) and
                not meta.is_field_remote(field)
            ]
            queryset = queryset.only(*only)

        # add request filters
        query = self._filters_to_query(filters)

        if query:
            # Convert internal django ValidationError to
            # APIException-based one in order to resolve validation error
            # from 500 status code to 400.
            try:
                queryset = queryset.filter(query)
            except InternalValidationError as e:
                raise ValidationError(
                    dict(e) if hasattr(e, 'error_dict') else list(e)
                )
            except Exception as e:
                # Some other Django error in parsing the filter.
                # Very likely a bad query, so throw a ValidationError.
                err_msg = getattr(e, 'message', '')
                raise ValidationError(err_msg)

        # A serializer can have this optional function
        # to dynamically apply additional filters on
        # any queries that will use that serializer
        # You could use this to have (for example) different
        # serializers for different subsets of a model or to
        # implement permissions which work even in sideloads
        if hasattr(serializer, 'filter_queryset'):
            queryset = serializer.filter_queryset(queryset)

        # add prefetches and remove duplicates if necessary
        prefetch = prefetches.values()
        queryset = queryset.prefetch_related(*prefetch)
        if has_joins(queryset) or not is_root_level:
            queryset = queryset.distinct()

        if self.DEBUG:
            queryset._using_prefetches = prefetches
        return queryset


class DynamicSortingFilter(WithGetSerializerClass, OrderingFilter):

    """Subclass of DRF's OrderingFilter.

    This class adds support for multi-field ordering and rewritten fields.
    """

    def filter_queryset(self, request, queryset, view):
        """"Filter the queryset, applying the ordering.

        The `ordering_param` can be overwritten here.
        In DRF, the ordering_param is 'ordering', but we support changing it
        to allow the viewset to control the parameter.
        """
        self.ordering_param = view.SORT

        ordering = self.get_ordering(request, queryset, view)
        if ordering:
            return queryset.order_by(*ordering)

        return queryset

    def get_ordering(self, request, queryset, view):
        """Return an ordering for a given request.

        DRF expects a comma separated list, while DREST expects an array.
        This method overwrites the DRF default so it can parse the array.
        """
        params = view.get_request_feature(view.SORT)
        if params:
            fields = [param.strip() for param in params]
            valid_ordering, invalid_ordering = self.remove_invalid_fields(
                queryset, fields, view
            )

            # if any of the sort fields are invalid, throw an error.
            # else return the ordering
            if invalid_ordering:
                raise ValidationError(
                    "Invalid ordering: %s" % (
                        ','.join((
                            '%s: %s' % (ex[0], str(ex[1])) for ex in
                            invalid_ordering
                        ))
                    )
                )
            else:
                return valid_ordering

        # No sorting was included
        return self.get_default_ordering(view)

    def remove_invalid_fields(self, queryset, fields, view):
        """Remove invalid fields from an ordering.

        Overwrites the DRF default remove_invalid_fields method to return
        both the valid orderings and any invalid orderings.
        """
        valid_orderings = []
        invalid_orderings = []

        # for each field sent down from the query param,
        # determine if its valid or invalid
        if fields:
            serializer = self.get_serializer_class(view)()
            for term in fields:
                stripped_term = term.lstrip('-')
                # add back the '-' add the end if necessary
                reverse_sort_term = (
                    '' if len(stripped_term) is len(term)
                    else '-'
                )
                try:
                    ordering = self.resolve(serializer, stripped_term, view)
                    valid_orderings.append(reverse_sort_term + ordering)
                except ValidationError as e:
                    invalid_orderings.append((term, e))

        return valid_orderings, invalid_orderings

    def resolve(self, serializer, query, view=None):
        """Resolve an ordering.

        Arguments:
            query: a string representing an API field
                e.g: "location.name"
            serializer: a serializer instance
                e.g. UserSerializer
            view: a view instance (optional)
                e.g. UserViewSet

        Returns:
            Double-underscore-separated list of strings,
            representing a model field.
                e.g. "location__real_name"

        Raises:
            ValidationError if the query cannot be rewritten
        """
        if not self._is_allowed_query(query, view):
            raise ValidationError('Invalid sort option: %s' % query)

        model_fields, _ = serializer.resolve(query)
        return '__'.join([
            Meta.get_query_name(f) for f in model_fields
        ])

    def _is_allowed_query(self, query, view=None):
        if not view:
            return True

        # views can define ordering_fields to limit ordering
        valid_fields = getattr(view, 'ordering_fields', self.ordering_fields)
        all_fields_allowed = valid_fields is None or valid_fields == '__all__'
        return all_fields_allowed or query in valid_fields

    def get_valid_fields(self, queryset, view, context={}):
        """Return valid fields for ordering.

        Overwrites DRF's get_valid_fields method so that valid_fields returns
        serializer fields, not model fields.
        """
        valid_fields = getattr(view, 'ordering_fields', self.ordering_fields)

        try:
            serializer_class = self.get_serializer_class(view)
        except (AssertionError, ImproperlyConfigured):
            serializer_class = None

        if valid_fields is None or valid_fields == '__all__':
            # Default to allowing filtering on serializer fields
            valid_fields = [
                (field_name, field.source or field_name)
                for field_name, field in serializer_class().fields.items()
                if not getattr(
                    field, 'write_only', False
                ) and not field.source == '*'
            ]
        else:
            valid_fields = [
                (field_name, field.source or field_name)
                for field_name, field in serializer_class().fields.items()
                if not getattr(field, 'write_only', False) and
                not field.source == '*' and field_name in valid_fields
            ]

        return valid_fields
