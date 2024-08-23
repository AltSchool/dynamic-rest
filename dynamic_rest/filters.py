"""This module contains custom filter backends."""

from django.core.exceptions import ValidationError as InternalValidationError
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q, Prefetch, Manager
from functools import reduce
from rest_framework import __version__ as drf_version
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
try:
    from rest_framework.fields import BooleanField, NullBooleanField
except ImportError:
    # DRF >= 3.14.0
    from rest_framework.fields import BooleanField
from rest_framework.filters import BaseFilterBackend, OrderingFilter

from dynamic_rest.utils import is_truthy
from dynamic_rest.conf import settings
from dynamic_rest.datastructures import TreeMap
from dynamic_rest.fields import DynamicRelationField
from dynamic_rest.meta import (
    get_model_field,
    is_field_remote,
    is_model_field,
    get_related_model,
)
from dynamic_rest.patches import patch_prefetch_one_level
from dynamic_rest.prefetch import FastQuery, FastPrefetch
from dynamic_rest.related import RelatedObject

patch_prefetch_one_level()

DRF_VERSION = drf_version.split('.')
if int(DRF_VERSION[0]) >= 3 and int(DRF_VERSION[1]) >= 14:
    # NullBooleanField deprecated in DRF >= 3.14
    DRF_BOOLEAN_FIELD = BooleanField
else:
    DRF_BOOLEAN_FIELD = (BooleanField, NullBooleanField)


def OR(a, b):
    return a | b


def AND(a, b):
    return a & b


def has_joins(queryset):
    """Return True iff. a queryset includes joins.

    If this is the case, it is possible for the queryset
    to return duplicate results.
    """
    for join in queryset.query.alias_map.values():
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
            '__' + self.operator if self.operator else '',
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
                raise ValidationError("Invalid filter field: %s" % field_name)

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
                raise ValidationError("Invalid nested filter field: %s" % field_name)

        if self.operator:
            rewritten.append(self.operator)

        return ('__'.join(rewritten), field)


def rewrite_filters(fs, serializer):
    out = {}
    for node in fs.values():
        filter_key, field = node.generate_query_key(serializer)
        if isinstance(field, DRF_BOOLEAN_FIELD):
            node.value = is_truthy(node.value)
        out[filter_key] = node.value

    return out


def clause_to_q(clause, serializer):
    key, value = clause
    negate = False
    q = {}
    if key.startswith('-'):
        negate = True
        key = key[1:]
    parts = key.split('.')
    operator = 'eq'
    if parts[-1] in DynamicFilterBackend.VALID_FILTER_OPERATORS:
        operator = parts.pop()
    if operator == 'eq':
        operator = None
    node = FilterNode(parts, operator, value)
    key, _ = node.generate_query_key(serializer)
    q = Q(**{key: node.value})
    if negate:
        q = ~q
    return q


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
        'iexact',
        None,
    )

    def filter_queryset(self, request, queryset, view):
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

        self.DEBUG = settings.DEBUG

        return self._build_queryset(
            queryset=queryset,
            extra_filters=extra_filters,
            disable_prefetches=disable_prefetches,
        )

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

        out = TreeMap()
        filters_map = kwargs.get('filters_map') or self.view.get_request_feature(
            self.view.FILTER
        )
        if getattr(self, 'view', None):
            out['_complex'] = self.view.get_request_feature(self.view.FILTER, raw=True)

        for spec, value in filters_map.items():

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
                if operator == 'isnull' and isinstance(value, str):
                    value = is_truthy(value)
                elif operator == 'eq':
                    operator = None

            node = FilterNode(parts, operator, value)

            # insert into output tree
            path = rel if rel else []
            path += [inex, node.key]
            out.insert(path, node)

        return out

    def _filters_to_query(self, filters, serializer, q=None):
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
          filters: TreeMap with include/exclude filters OR query map
          serializer: serializer instance of top-level object
          q: Q() object (optional)

        Returns:
          Q() instance or None if no inclusion or exclusion filters
          were specified.
        """

        if (
            not filters.get('_complex')
        ):
            includes = filters.get('_include')
            excludes = filters.get('_exclude')
            q = q or Q()

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
        else:
            filters = filters.get('_complex')
            ors = filters.get('.or') or filters.get('$or')
            ands = filters.get('.and') or filters.get('$and')
            if q is None:
                q = Q()
            if ors:
                result = reduce(
                    OR,
                    [self._filters_to_query({"_complex": f}, serializer) for f in ors]
                )
                return result
            if ands:
                return reduce(
                    AND,
                    [self._filters_to_query({"_complex": f}, serializer) for f in ands]
                )
            clauses = [
                clause_to_q(clause, serializer) for clause in filters.items()
            ]
            return reduce(AND, clauses) if clauses else q

    def _create_prefetch(self, source, queryset):
        return Prefetch(source, queryset=queryset)

    def _build_implicit_prefetches(self, model, prefetches, requirements):
        """Build a prefetch dictionary based on internal requirements."""

        for source, remainder in requirements.items():
            if not remainder or isinstance(remainder, str):
                # no further requirements to prefetch
                continue

            related_field = get_model_field(model, source)
            related_model = get_related_model(related_field)

            queryset = (
                self._build_implicit_queryset(related_model, remainder)
                if related_model
                else None
            )

            prefetches[source] = self._create_prefetch(source, queryset)

        return prefetches

    def _make_model_queryset(self, model):
        return model.objects.all()

    def _build_implicit_queryset(self, model, requirements):
        """Build a queryset based on implicit requirements."""

        queryset = self._make_model_queryset(model)
        prefetches = {}
        self._build_implicit_prefetches(model, prefetches, requirements)
        prefetch = prefetches.values()
        queryset = queryset.prefetch_related(*prefetch).distinct()
        if self.DEBUG:
            queryset._using_prefetches = prefetches
        return queryset

    def _build_requested_prefetches(
        self, prefetches, requirements, model, fields, filters
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
            if '.' in source:
                raise ValidationError('nested relationship values are not supported')

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
                requirements=required,
            )

            # Note: There can only be one prefetch per source, even
            #       though there can be multiple fields pointing to
            #       the same source. This could break in some cases,
            #       but is mostly an issue on writes when we use all
            #       fields by default.
            prefetches[source] = self._create_prefetch(source, prefetch_queryset)

        return prefetches

    def _get_implicit_requirements(self, fields, requirements):
        """Extract internal prefetch requirements from serializer fields."""
        for name, field in fields.items():
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

    def _get_queryset(self, queryset=None, serializer=None):
        if serializer and queryset is None:
            queryset = serializer.Meta.model.objects

        return queryset

    def _serializer_filter(self, serializer=None, queryset=None):
        return serializer.filter_queryset(queryset)

    def _build_queryset(
        self,
        serializer=None,
        filters=None,
        queryset=None,
        requirements=None,
        extra_filters=None,
        disable_prefetches=False,
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
        if not serializer:
            serializer = self.view.get_serializer()
            is_root_level = True

        queryset = self._get_queryset(queryset=queryset, serializer=serializer)

        model = getattr(serializer.Meta, 'model', None)

        if not model:
            return queryset

        prefetches = {}

        # build a nested Prefetch queryset
        # based on request parameters and serializer fields
        fields = serializer.fields

        if requirements is None:
            requirements = TreeMap()

        self._get_implicit_requirements(fields, requirements)

        # Implicit requirements (i.e. via `requires`) can potentially
        # include fields that haven't been explicitly included.
        # Such fields would not be in `fields`, so they need to be added.
        implicitly_included = set(requirements.keys()) - set(fields.keys())
        if implicitly_included:
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
            '*' not in requirements
            and not self.view.is_update()
            and not self.view.is_delete()
        ):
            id_fields = getattr(serializer, 'get_id_fields', lambda: [])()
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
                raise ValidationError(dict(e) if hasattr(e, 'error_dict') else list(e))
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
            queryset = self._serializer_filter(serializer=serializer, queryset=queryset)

        # add prefetches and remove duplicates if necessary
        prefetch = prefetches.values()
        if prefetch and not disable_prefetches:
            queryset = queryset.prefetch_related(*prefetch)
        elif isinstance(queryset, Manager):
            queryset = queryset.all()
        if has_joins(queryset) or not is_root_level:
            queryset = queryset.distinct()

        if self.DEBUG:
            queryset._using_prefetches = prefetches
        return queryset


class FastDynamicFilterBackend(DynamicFilterBackend):
    def _create_prefetch(self, source, queryset):
        return FastPrefetch(source, queryset=queryset)

    def _get_queryset(self, queryset=None, serializer=None):
        queryset = super(FastDynamicFilterBackend, self)._get_queryset(
            queryset=queryset, serializer=serializer
        )

        if not isinstance(queryset, FastQuery):
            queryset = FastQuery(queryset)

        return queryset

    def _make_model_queryset(self, model):
        queryset = super(FastDynamicFilterBackend, self)._make_model_queryset(model)
        return FastQuery(queryset)

    def _serializer_filter(self, serializer=None, queryset=None):
        queryset.queryset = serializer.filter_queryset(queryset.queryset)
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
            queryset = queryset.order_by(*ordering)
            if any(['__' in o for o in ordering]):
                # add distinct() to remove duplicates
                # in case of order-by-related
                queryset = queryset.distinct()
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
                raise ValidationError("Invalid filter field: %s" % invalid_ordering)
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
        for term in fields:
            stripped_term = term.lstrip('-')
            # add back the '-' add the end if necessary
            reverse_sort_term = '' if len(stripped_term) is len(term) else '-'
            ordering = self.ordering_for(stripped_term, view)

            if ordering:
                valid_orderings.append(reverse_sort_term + ordering)
            else:
                invalid_orderings.append(term)

        return valid_orderings, invalid_orderings

    def ordering_for(self, term, view):
        """
        Return ordering (model field chain) for term (serializer field chain)
        or None if invalid

        Raise ImproperlyConfigured if serializer_class not set on view
        """
        if not self._is_allowed_term(term, view):
            return None

        serializer = self._get_serializer_class(view)()
        serializer_chain = term.split('.')

        model_chain = []

        for segment in serializer_chain[:-1]:
            field = serializer.get_all_fields().get(segment)

            if not (
                field
                and field.source != '*'
                and isinstance(field, DynamicRelationField)
            ):
                return None

            model_chain.append(field.source or segment)

            serializer = field.serializer_class()

        last_segment = serializer_chain[-1]
        last_field = serializer.get_all_fields().get(last_segment)

        if not last_field or last_field.source == '*':
            return None

        model_chain.append(last_field.source or last_segment)

        return '__'.join(model_chain)

    def _is_allowed_term(self, term, view):
        valid_fields = getattr(view, 'ordering_fields', self.ordering_fields)
        all_fields_allowed = valid_fields is None or valid_fields == '__all__'

        return all_fields_allowed or term in valid_fields

    def _get_serializer_class(self, view):
        # prefer the overriding method
        if hasattr(view, 'get_serializer_class'):
            try:
                serializer_class = view.get_serializer_class()
            except AssertionError:
                # Raised by the default implementation if
                # no serializer_class was found
                serializer_class = None
        # use the attribute
        else:
            serializer_class = getattr(view, 'serializer_class', None)

        # neither a method nor an attribute has been specified
        if serializer_class is None:
            msg = (
                "Cannot use %s on a view which does not have either a "
                "'serializer_class' or an overriding 'get_serializer_class'."
            )
            raise ImproperlyConfigured(msg % self.__class__.__name__)

        return serializer_class
