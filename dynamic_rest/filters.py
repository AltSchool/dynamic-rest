from django.db.models import Q, Prefetch
from dynamic_rest.datastructures import TreeMap
from dynamic_rest.fields import DynamicRelationField, field_is_remote

from rest_framework import serializers
from rest_framework.filters import BaseFilterBackend


class DynamicFilterBackend(BaseFilterBackend):
    VALID_FILTER_OPERATORS = (
        'in',
        'any',
        'all',
        'like',
        'range',
        'gt',
        'lt',
        'gte',
        'lte',
        'isnull',
        None,
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

            # if dot-delimited, assume last part is the operator, otherwise
            # assume whole thing is a field name (with 'eq' implied).
            field = '__'.join(parts[:-1]) if len(parts) > 1 else parts[0]

            # Assume last part of a dot-delimited field spec is an operator.
            # Note, however, that 'foo.bar' is a valid field spec with an 'eq'
            # implied as operator. This will be resolved below.
            operator = (parts[-1] if len(parts) > 1
                        and parts[-1] != 'eq' else None)

            # All operators except 'range' and 'in' should have one value
            if operator == 'range':
                value = value[:2]
            elif operator == 'in':
                # no-op: i.e. accept `value` as an arbitrarily long list
                pass
            elif operator in self.VALID_FILTER_OPERATORS:
                value = value[0]
            else:
                # Unknown operator, we'll treat it like a field
                # e.g: filter{foo.bar}=baz
                field += '__' + operator
                operator = None
                value = value[0]

            param = field
            if operator:
                param += '__' + operator

            path = rel if rel else []
            path.extend([inex, param])
            out.insert(path, value)

        return out

    def _filters_to_query(self, includes, excludes, rewrites=None, q=None):
        """
        Construct Django Query object from request.
        Arguments are dictionaries, which will be passed to Q() as kwargs.

        e.g.
            includes = { 'foo' : 'bar', 'baz__in' : [1, 2] }
          produces:
            Q(foo='bar', baz__in=[1, 2])

        Arguments:
          includes: Dictionary of inclusion filters.
          excludes: Dictionary of inclusion filters.
          rewrites: Dictionary of field rewrites. (e.g. when field and source
              are different)

        Returns:
          Q() instance or None if no inclusion or exclusion filters
          were specified.
        """

        def rewrite_filters(filters, rewrites):
            if not rewrites:
                return filters
            out = {}
            for k, v in filters.iteritems():
                if k in rewrites:
                    out[rewrites[k].replace('.', '__')] = v
                else:
                    out[k] = v
            return out

        q = q or Q()

        if not includes and not excludes:
            return None

        if includes:
            includes = rewrite_filters(includes, rewrites)
            q &= Q(**includes)
        if excludes:
            excludes = rewrite_filters(excludes, rewrites)
            for k, v in excludes.iteritems():
                q &= ~Q(**{k: v})
        return q

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
          queryset: Optional queryset. Only applies to top-level.
        """

        if serializer:
            queryset = queryset or serializer.Meta.model.objects
        else:
            queryset = queryset
            serializer = self.view.get_serializer()

        prefetch_related = {}
        only = set()
        use_only = True
        model = getattr(serializer.Meta, 'model', None)
        if not model:
            return queryset

        if filters is None:
            filters = self._extract_filters()

        field_rewrites = {}

        for name, field in serializer.fields.iteritems():
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
                    prefetch_qs = self._filter_queryset(
                        serializer=field,
                        filters=filters.get(name, {}),
                        queryset=getattr(original_field, 'queryset', None)
                    )

                    # Note: There can only be one prefetch per source, even
                    #       though there can be multiple fields pointing to
                    #       the same source. This could break in some cases,
                    #       but is mostly an issue on writes when we use all
                    #       fields by default.
                    prefetch_related[source] = Prefetch(
                        source,
                        queryset=prefetch_qs)

            if name != source:
                field_rewrites[name] = source

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
            rewrites=field_rewrites)
        if q:
            queryset = queryset.filter(q)
        return queryset.prefetch_related(*prefetch_related.values())
