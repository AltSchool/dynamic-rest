from dynamic_rest.patches import patch_prefetch_one_level
patch_prefetch_one_level()

from django.db.models import (
    ForeignKey,
    OneToOneField,
    Prefetch,
    Q,
)

from django.db.models.related import RelatedObject
from dynamic_rest.datastructures import TreeMap
from dynamic_rest.fields import (
    DynamicRelationField, field_is_remote, get_model_field
)

from rest_framework.exceptions import ValidationError
from rest_framework import serializers
from rest_framework.filters import BaseFilterBackend


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

            if field_name not in fields:
                raise ValidationError(
                    "Invalid filter field: %s" % field_name)

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
            for k, node in filters.iteritems():
                filter_key = node.generate_query_key(serializer)
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
            for k, v in excludes.iteritems():
                q &= ~Q(**{k: v})
        return q

    def _build_prefetch_queryset(self, name, original_field, field, filters):
        related_queryset = getattr(original_field, 'queryset', None)

        if callable(related_queryset):
            related_queryset = related_queryset(field)

        return self._filter_queryset(
            serializer=field,
            filters=filters.get(name, {}),
            queryset=related_queryset
        )

    def _add_nested_prefetches(self, source, prefetch_related):
        source_parts = source.split('.')
        for i in range(1, len(source_parts)):
            k = '.'.join(source_parts[0:i])
            if k in prefetch_related:
                continue
            prefetch_related[k] = '__'.join(source_parts[0:i])
        return prefetch_related

    def _filter_queryset(
            self, serializer=None, filters=None, queryset=None):
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
        """

        if serializer:
            if queryset is None:
                queryset = serializer.Meta.model.objects
        else:
            serializer = self.view.get_serializer()

        prefetch_related = {}
        only = set()
        use_only = True
        model = getattr(serializer.Meta, 'model', None)
        if not model:
            return queryset

        if filters is None:
            filters = self._extract_filters()

        fields = serializer.fields
        for name, field in fields.iteritems():
            original_field = field
            if isinstance(field, DynamicRelationField):
                field = field.serializer
            if isinstance(field, serializers.ListSerializer):
                field = field.child

            source = field.source or name
            source0 = source.split('.')[0]
            remote = False

            if isinstance(field, serializers.ModelSerializer):
                remote = field_is_remote(model, source0)
                id_only = getattr(field, 'id_only', lambda: False)()
                if not id_only or remote:
                    prefetch_qs = self._build_prefetch_queryset(
                        name, original_field, field, filters
                    )

                    # Note: There can only be one prefetch per source, even
                    #       though there can be multiple fields pointing to
                    #       the same source. This could break in some cases,
                    #       but is mostly an issue on writes when we use all
                    #       fields by default.
                    prefetch_related[source] = Prefetch(
                        source,
                        queryset=prefetch_qs)
            elif source0 is not source and (isinstance(
                get_model_field(model, source0),
                (OneToOneField, RelatedObject, ForeignKey))
            ):

                # Prefetch nested references, where children are either
                # deferred or not defined. If source is 'user.location.name'
                # then we add prefetches for 'user' and 'user__location'.
                prefetch_related = self._add_nested_prefetches(
                    source, prefetch_related)

            if use_only:
                if source == '*':
                    use_only = False
                elif not remote and not getattr(field, 'is_computed', False):
                    # TODO: optimize for nested sources
                    only.add(source0)

        if getattr(serializer, 'id_only', lambda: False)():
            use_only = True

        if use_only:
            id_fields = getattr(serializer, 'get_id_fields', lambda: [])()
            only = set(id_fields + list(only))
            queryset = queryset.only(*only)

        q = self._filters_to_query(
            includes=filters.get('_include'), excludes=filters.get('_exclude'),
            serializer=serializer)
        if q:
            queryset = queryset.filter(q)
        return queryset.prefetch_related(*prefetch_related.values()).distinct()
