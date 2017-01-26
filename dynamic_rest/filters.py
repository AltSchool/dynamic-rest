"""This module contains custom filter backends."""

from django.core.exceptions import ValidationError as InternalValidationError
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q, Prefetch
from django.utils import six
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import BooleanField, NullBooleanField
from rest_framework.filters import BaseFilterBackend, OrderingFilter

from dynamic_rest.utils import is_truthy
from dynamic_rest.conf import settings
from dynamic_rest.datastructures import TreeMap
from dynamic_rest.fields import DynamicRelationField
from dynamic_rest.meta import (
    get_model_field,
    is_field_remote,
    is_model_field,
    get_related_model
)
from dynamic_rest.patches import patch_prefetch_one_level
from dynamic_rest.related import RelatedObject

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


class FilterNode(object):

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
        return '%s%s' % (
            '__'.join(self.field),
            '__' + self.operator if self.operator else ''
        )

    def generate_query_key(self, serializer):
        """Get the key that can be passed to Django's filter method.

        To account for serialier field name rewrites, this method
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
            # sideloaded. Fields that are deferred also won't be present.
            # If field name isn't in serializer.fields, get full list from
            # get_all_fields() method. This is somewhat expensive, so only do
            # this if we have to.
            fields = s.fields
            if field_name not in fields:
                fields = getattr(s, 'get_all_fields', lambda: {})()

            if field_name == 'pk':
                rewritten.append('pk')
                continue

            if field_name not in fields:
                raise ValidationError(
                    "Invalid filter field: %s" % field_name
                )

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
            s = getattr(field, 'serializer', None)
            if isinstance(s, serializers.ListSerializer):
                s = s.child
            if not s:
                raise ValidationError(
                    "Invalid nested filter field: %s" % field_name
                )

        if self.operator:
            rewritten.append(self.operator)

        return ('__'.join(rewritten), field)


class DynamicFilterBackend(BaseFilterBackend):

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
        return self._build_queryset(queryset=queryset)

    """
    This function was renamed and broke downstream dependencies that haven't
    been updated to use the new naming convention.
    """
    def _extract_filters(self, **kwargs):
        return self._get_requested_filters(**kwargs)

    def _get_requested_filters(self, **kwargs):
        """
        Convert 'filters' query params into a dict that can be passed
        to Q. Returns a dict with two fields, 'include' and 'exclude',
        which can be used like:

          result = self._get_requested_filters()
          q = Q(**result['include'] & ~Q(**result['exclude'])

        """

        filters_map = (
            kwargs.get('filters_map') or
            self.view.get_request_feature(self.view.FILTER)
        )

        out = TreeMap()

        for spec, value in six.iteritems(filters_map):

            # Inclusion or exclusion?
            if spec[0] == '-':
                spec = spec[1:]
                inex = '_exclude'
            else:
                inex = '_include'

            # for relational filters, separate out relation path part
            if '|' in spec:
                rel, spec = spec.split('|')
                rel = rel.split('.')
            else:
                rel = None

            parts = spec.split('.')

            # Last part could be operator, e.g. "events.capacity.gte"
            if len(parts) > 1 and parts[-1] in self.VALID_FILTER_OPERATORS:
                operator = parts.pop()
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

            node = FilterNode(parts, operator, value)

            # insert into output tree
            path = rel if rel else []
            path += [inex, node.key]
            out.insert(path, node)

        return out

    def _filters_to_query(self, includes, excludes, serializer, q=None):
        """
        Construct Django Query object from request.
        Arguments are dictionaries, which will be passed to Q() as kwargs.

        e.g.
            includes = { 'foo' : 'bar', 'baz__in' : [1, 2] }
          produces:
            Q(foo='bar', baz__in=[1, 2])

        Arguments:
          includes: TreeMap representing inclusion filters.
          excludes: TreeMap representing exclusion filters.
          serializer: serializer instance of top-level object
          q: Q() object (optional)

        Returns:
          Q() instance or None if no inclusion or exclusion filters
          were specified.
        """

        def rewrite_filters(filters, serializer):
            out = {}
            for k, node in six.iteritems(filters):
                filter_key, field = node.generate_query_key(serializer)
                if isinstance(field, (BooleanField, NullBooleanField)):
                    node.value = is_truthy(node.value)
                out[filter_key] = node.value

            return out

        q = q or Q()

        if not includes and not excludes:
            return None

        if includes:
            includes = rewrite_filters(includes, serializer)
            q &= Q(**includes)
        if excludes:
            excludes = rewrite_filters(excludes, serializer)
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

        for source, remainder in six.iteritems(requirements):
            if not remainder or isinstance(remainder, six.string_types):
                # no further requirements to prefetch
                continue

            related_field = get_model_field(model, source)
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
        if self.DEBUG:
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
                    'nested relationship values '
                    'are not supported'
                )

            if source in prefetches:
                # ignore duplicated sources
                continue

            is_remote = is_field_remote(model, source)
            is_id_only = getattr(field, 'id_only', lambda: False)()
            if is_id_only and not is_remote:
                continue

            related_queryset = getattr(original_field, 'queryset', None)

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
                requirements=required
            )

            # Note: There can only be one prefetch per source, even
            #       though there can be multiple fields pointing to
            #       the same source. This could break in some cases,
            #       but is mostly an issue on writes when we use all
            #       fields by default.
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

        model = getattr(serializer.Meta, 'model', None)

        if not model:
            return queryset

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
        if (
            '*' not in requirements and
            not self.view.is_update() and
            not self.view.is_delete()
        ):
            id_fields = getattr(serializer, 'get_id_fields', lambda: [])()
            # only include local model fields
            only = [
                field for field in set(
                    id_fields + list(requirements.keys())
                ) if is_model_field(model, field) and
                not is_field_remote(model, field)
            ]
            queryset = queryset.only(*only)

        # add request filters
        query = self._filters_to_query(
            includes=filters.get('_include'),
            excludes=filters.get('_exclude'),
            serializer=serializer
        )

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


class DynamicSortingFilter(OrderingFilter):

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
                    "Invalid filter field: %s" % invalid_ordering
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
        # get valid field names for sorting
        valid_fields_map = {
            name: source for name, source in self.get_valid_fields(
                queryset, view)
        }

        valid_orderings = []
        invalid_orderings = []

        # for each field sent down from the query param,
        # determine if its valid or invalid
        for term in fields:
            stripped_term = term.lstrip('-')
            # add back the '-' add the end if necessary
            reverse_sort_term = '' if len(stripped_term) is len(term) else '-'
            if stripped_term in valid_fields_map:
                name = reverse_sort_term + valid_fields_map[stripped_term]
                valid_orderings.append(name)
            else:
                invalid_orderings.append(term)

        return valid_orderings, invalid_orderings

    def get_valid_fields(self, queryset, view, context={}):
        """Return valid fields for ordering.

        Overwrites DRF's get_valid_fields method so that valid_fields returns
        serializer fields, not model fields.
        """
        valid_fields = getattr(view, 'ordering_fields', self.ordering_fields)

        if valid_fields is None or valid_fields == '__all__':
            # Default to allowing filtering on serializer fields
            serializer_class = getattr(view, 'serializer_class')
            if serializer_class is None:
                msg = (
                    "Cannot use %s on a view which does not have either a "
                    "'serializer_class' or 'ordering_fields' attribute."
                )
                raise ImproperlyConfigured(msg % self.__class__.__name__)
            valid_fields = [
                (field_name, field.source or field_name)
                for field_name, field in serializer_class().fields.items()
                if not getattr(
                    field, 'write_only', False
                ) and not field.source == '*'
            ]
        else:
            serializer_class = getattr(view, 'serializer_class')
            valid_fields = [
                (field_name, field.source or field_name)
                for field_name, field in serializer_class().fields.items()
                if not getattr(field, 'write_only', False) and
                not field.source == '*' and field_name in valid_fields
            ]

        return valid_fields
