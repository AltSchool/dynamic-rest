from dynamic_rest.patches import patch_prefetch_one_level
patch_prefetch_one_level()

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import (
    Prefetch,
    Q
)

from django.db.models.related import RelatedObject
from rest_framework.exceptions import ValidationError
from rest_framework import serializers
from rest_framework.filters import BaseFilterBackend
from rest_framework.filters import OrderingFilter


from dynamic_rest.datastructures import TreeMap
from dynamic_rest.fields import (
    DynamicRelationField,
    is_field_remote,
    get_model_field,
    is_model_field
)


class FilterNode(object):

    def __init__(self, field, operator, value):
        """
        Create an object representing filter, to be stored in TreeMap.

        Arguments:
            field: List of field parts
                   i.e. 'filter{users.events}' -> ['users', 'events']
            opreator: Valid operator (e.g. 'lt', 'in', etc). None == equals.
        """
        self.field = field
        self.operator = operator
        self.value = value
        self.is_remote = False  # is filter on a join

    @property
    def key(self):
        return '%s%s' % (
            '__'.join(self.field),
            '__' + self.operator if self.operator else ''
        )

    def generate_query_key(self, serializer):
        """
        Return filter key that can be passed to Django's filter() method.
        Translates serializer field names to model field names by inspecting
        serializer.
        """
        rewritten = []
        last = len(self.field) - 1
        s = serializer
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

        self.is_remote = len(rewritten) > 1

        if self.operator:
            rewritten.append(self.operator)

        return '__'.join(rewritten)


class DynamicFilterBackend(BaseFilterBackend):
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

    FALSEY_STRINGS = (
        '0',
        'false',
        '',
    )

    def filter_queryset(self, request, queryset, view):
        """
        Filter queryset. This is the main/single entry-point to this class, and
        is called by DRF's list handler.
        """
        self.request = request
        self.view = view

        self.DEBUG = getattr(settings, 'DYNAMIC_REST', {}).get('DEBUG', False)

        if self.DEBUG:
            # in DEBUG mode, save a representation of the prefetch tree
            # on the viewset
            self.view._prefetches = self._prefetches = {}

        return self._filter_queryset(queryset=queryset)

    def _extract_filters(self, **kwargs):
        """
        Convert 'filters' query params into a dict that can be passed
        to Q. Returns a dict with two fields, 'include' and 'exclude',
        which can be used like:

          result = self._extract_filters()
          q = Q(**result['include'] & ~Q(**result['exclude'])

        """

        filters_map = kwargs.get('filters_map') or \
            self.view.get_request_feature(self.view.FILTER)

        out = TreeMap()

        for spec, value in filters_map.iteritems():

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
                if operator == 'isnull' and isinstance(value, (str, unicode)):
                    value = value.lower() not in self.FALSEY_STRINGS
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
            has_remote_filter = False
            for k, node in filters.iteritems():
                filter_key = node.generate_query_key(serializer)
                out[filter_key] = node.value
                has_remote_filter |= node.is_remote

            return out, has_remote_filter

        q = q or Q()

        if not includes and not excludes:
            return None, False

        incl_has_remote = excl_has_remote = False
        if includes:
            includes, incl_has_remote = rewrite_filters(includes, serializer)
            q &= Q(**includes)
        if excludes:
            excludes, excl_has_remote = rewrite_filters(excludes, serializer)
            for k, v in excludes.iteritems():
                q &= ~Q(**{k: v})

        return q, (incl_has_remote or excl_has_remote)

    def _build_prefetch_queryset(
        self,
        name,
        original_field,
        field,
        filters,
        requirements
    ):
        related_queryset = getattr(original_field, 'queryset', None)

        if callable(related_queryset):
            related_queryset = related_queryset(field)

        source = field.source or name
        # Popping the source here (during explicit prefetch construction)
        # guarantees that implicitly required prefetches that follow will
        # not conflict.
        required = requirements.pop(source, None)

        if self.DEBUG:
            # push prefetches
            prefetches = self._prefetches
            self._prefetches[source] = {}
            self._prefetches = self._prefetches[source]

        queryset = self._filter_queryset(
            serializer=field,
            filters=filters.get(name, {}),
            queryset=related_queryset,
            requirements=required
        )

        if self.DEBUG:
            # pop back
            self._prefetches = prefetches

        return queryset

    def _add_internal_prefetches(
        self,
        prefetches,
        requirements
    ):
        """Add remaining prefetches as implicit prefetches."""
        paths = requirements.get_paths()
        for path in paths:
            # Remove last segment, which indicates a field name or wildcard.
            # For example, {model_a : {model_b : {field_c}}
            # should be prefetched as a__b
            prefetch_path = path[:-1]
            key = '__'.join(prefetch_path)
            if key:
                prefetches[key] = key
                if self.DEBUG:
                    self._prefetches[key] = {}

    def _add_request_prefetches(
        self,
        prefetches,
        requirements,
        model,
        fields,
        filters
    ):
        for name, field in fields.iteritems():
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

            prefetch_queryset = self._build_prefetch_queryset(
                name,
                original_field,
                field,
                filters,
                requirements
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

    def _extract_requirements(
        self,
        fields,
        requirements
    ):
        """Extract requirements from serializer fields."""
        for name, field in fields.iteritems():
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

    def _filter_queryset(
        self,
        serializer=None,
        filters=None,
        queryset=None,
        requirements=None
    ):
        """
        Recursive queryset builder.
        Handles nested prefetching of related data and deferring fields
        at the queryset level.

        Arguments:
          serializer: An optional serializer to use a base for the queryset.
            If no serializer is passed, the `get_serializer` method will
            be used to initialize the base serializer for the viewset.
          filters: Optional nested filter map (TreeMap)
          queryset: Optional queryset.
          requirements: Optional nested requirements (TreeMap)
        """

        if serializer:
            if queryset is None:
                queryset = serializer.Meta.model.objects
        else:
            serializer = self.view.get_serializer()

        model = getattr(serializer.Meta, 'model', None)

        if not model:
            return queryset

        prefetches = {}
        fields = serializer.fields

        if requirements is None:
            requirements = TreeMap()

        self._extract_requirements(
            fields,
            requirements
        )

        if filters is None:
            filters = self._extract_filters()

        # build nested Prefetch queryset
        self._add_request_prefetches(
            prefetches,
            requirements,
            model,
            fields,
            filters
        )

        # add any remaining requirements as prefetches
        self._add_internal_prefetches(
            prefetches,
            requirements
        )

        # use requirements at this level to limit fields selected
        # only do this for GET requests where we are not requesting the
        # entire fieldset
        if '*' not in requirements and not self.view.is_update():
            id_fields = getattr(serializer, 'get_id_fields', lambda: [])()
            # only include local model fields
            only = [
                field for field in set(id_fields + list(requirements.keys()))
                if is_model_field(model, field)
                and not is_field_remote(model, field)
            ]
            queryset = queryset.only(*only)

        # add filters
        query, has_remote_filter = self._filters_to_query(
            includes=filters.get('_include'),
            excludes=filters.get('_exclude'),
            serializer=serializer
        )

        if query:
            queryset = queryset.filter(query)

        prefetch = prefetches.values()
        queryset = queryset.prefetch_related(*prefetch)

        if has_remote_filter:
            queryset = queryset.distinct()

        return queryset


class DynamicSortingFilter(OrderingFilter):
    def filter_queryset(self, request, queryset, view):
        """"
        Overwrite this method to set the 'ordering_param' on this class.
        Under DRF, the ordering_param is 'ordering', but we are changing it
        to what we specified on the SORT property in our viewset.
        """
        self.ordering_param = view.SORT

        ordering = self.get_ordering(request, queryset, view)
        if ordering:
            return queryset.order_by(*ordering)

        return queryset

    def get_ordering(self, request, queryset, view):
        """
        Ordering is set by a ?sort[]=... query parameter.
        The `sort[]` query parameter is set by the `ordering_param` above.
        The default for django-rest-framework is `ordering`.

        DRF expects a comma separated list, while drest expects an array.
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
        """
        Overwrite the DRF default remove_invalid_fields method to return
        both valid orderings and any invalid orderings
        """
        # get valid field names for sorting
        valid_fields_map = {
            name: source for name, label, source in self.get_valid_fields(
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

    def get_valid_fields(self, queryset, view):
        """
        Overwrite get_valid_fields method so that valid_fields returns only
        serializer fields, not model fields.
        """
        valid_fields = getattr(view, 'ordering_fields', self.ordering_fields)

        if valid_fields is None or valid_fields == '__all__':
            # Default to allowing filtering on serializer fields
            serializer_class = getattr(view, 'serializer_class')
            if serializer_class is None:
                msg = ("Cannot use %s on a view which does not have either a "
                       "'serializer_class' or 'ordering_fields' attribute.")
                raise ImproperlyConfigured(msg % self.__class__.__name__)
            valid_fields = [
                (field_name, field.label, field.source or field_name)
                for field_name, field in serializer_class().fields.items()
                if not getattr(
                    field, 'write_only', False
                ) and not field.source == '*'
            ]
        else:
            serializer_class = getattr(view, 'serializer_class')
            valid_fields = [
                (field_name, field.label, field.source or field_name)
                for field_name, field in serializer_class().fields.items()
                if not getattr(field, 'write_only', False)
                and not field.source == '*' and field_name in valid_fields
            ]
        return valid_fields
