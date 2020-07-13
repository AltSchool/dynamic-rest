"""This module contains custom viewset classes."""
from django.core.exceptions import ObjectDoesNotExist
from django.http import QueryDict
import six
from django.db import transaction, IntegrityError
from rest_framework import exceptions, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.response import Response

from dynamic_rest.conf import settings
from dynamic_rest.filters import DynamicFilterBackend, DynamicSortingFilter
from dynamic_rest.metadata import DynamicMetadata
from dynamic_rest.pagination import DynamicPageNumberPagination
from dynamic_rest.processors import SideloadingProcessor
from dynamic_rest.utils import is_truthy

UPDATE_REQUEST_METHODS = ('PUT', 'PATCH', 'POST')
DELETE_REQUEST_METHOD = 'DELETE'
PATCH = 'PATCH'


class QueryParams(QueryDict):
    """
    Extension of Django's QueryDict. Instantiated from a DRF Request
    object, and returns a mutable QueryDict subclass. Also adds methods that
    might be useful for our usecase.
    """

    def __init__(self, query_params, *args, **kwargs):
        if hasattr(query_params, 'urlencode'):
            query_string = query_params.urlencode()
        else:
            assert isinstance(
                query_params,
                (six.string_types, six.binary_type)
            )
            query_string = query_params
        kwargs['mutable'] = True
        super(QueryParams, self).__init__(query_string, *args, **kwargs)

    def add(self, key, value):
        """
        Method to accept a list of values and append to flat list.
        QueryDict.appendlist(), if given a list, will append the list,
        which creates nested lists. In most cases, we want to be able
        to pass in a list (for convenience) but have it appended into
        a flattened list.
        TODO: Possibly throw an error if add() is used on a non-list param.
        """
        if isinstance(value, list):
            for val in value:
                self.appendlist(key, val)
        else:
            self.appendlist(key, value)


class WithDynamicViewSetMixin(object):

    """A viewset that can support dynamic API features.

    Attributes:
      features: A list of features supported by the viewset.
      meta: Extra data that is added to the response by the DynamicRenderer.
    """

    DEBUG = 'debug'
    SIDELOADING = 'sideloading'
    PATCH_ALL = 'patch-all'
    INCLUDE = 'include[]'
    EXCLUDE = 'exclude[]'
    FILTER = 'filter{}'
    SORT = 'sort[]'
    PAGE = settings.PAGE_QUERY_PARAM
    PER_PAGE = settings.PAGE_SIZE_QUERY_PARAM

    # TODO: add support for `sort{}`
    pagination_class = DynamicPageNumberPagination
    metadata_class = DynamicMetadata
    features = (
        DEBUG,
        INCLUDE,
        EXCLUDE,
        FILTER,
        PAGE,
        PER_PAGE,
        SORT,
        SIDELOADING,
        PATCH_ALL
    )
    meta = None
    filter_backends = (DynamicFilterBackend, DynamicSortingFilter)

    def initialize_request(self, request, *args, **kargs):
        """
        Override DRF initialize_request() method to swap request.GET
        (which is aliased by request.query_params) with a mutable instance
        of QueryParams, and to convert request MergeDict to a subclass of dict
        for consistency (MergeDict is not a subclass of dict)
        """

        def handle_encodings(request):
            """
            WSGIRequest does not support Unicode values in the query string.
            WSGIRequest handling has a history of drifting behavior between
            combinations of Python versions, Django versions and DRF versions.
            Django changed its QUERY_STRING handling here:
            https://goo.gl/WThXo6. DRF 3.4.7 changed its behavior here:
            https://goo.gl/0ojIIO.
            """
            try:
                return QueryParams(request.GET)
            except UnicodeEncodeError:
                pass

            s = request.environ.get('QUERY_STRING', '')
            try:
                s = s.encode('utf-8')
            except UnicodeDecodeError:
                pass
            return QueryParams(s)

        request.GET = handle_encodings(request)
        request = super(WithDynamicViewSetMixin, self).initialize_request(
            request, *args, **kargs
        )

        try:
            # Django<1.9, DRF<3.2

            # MergeDict doesn't have the same API as dict.
            # Django has deprecated MergeDict and DRF is moving away from
            # using it - thus, were comfortable replacing it with a QueryDict
            # This will allow the data property to have normal dict methods.
            from django.utils.datastructures import MergeDict
            if isinstance(request._full_data, MergeDict):
                data_as_dict = request.data.dicts[0]
                for d in request.data.dicts[1:]:
                    data_as_dict.update(d)
                request._full_data = data_as_dict
        except:
            pass

        return request

    def get_renderers(self):
        """Optionally block Browsable API rendering. """
        renderers = super(WithDynamicViewSetMixin, self).get_renderers()
        if settings.ENABLE_BROWSABLE_API is False:
            return [
                r for r in renderers if not isinstance(r, BrowsableAPIRenderer)
            ]
        else:
            return renderers

    def get_request_feature(self, name):
        """Parses the request for a particular feature.

        Arguments:
          name: A feature name.

        Returns:
          A feature parsed from the URL if the feature is supported, or None.
        """
        if '[]' in name:
            # array-type
            return self.request.query_params.getlist(
                name) if name in self.features else None
        elif '{}' in name:
            # object-type (keys are not consistent)
            return self._extract_object_params(
                name) if name in self.features else {}
        else:
            # single-type
            return self.request.query_params.get(
                name) if name in self.features else None

    def _extract_object_params(self, name):
        """
        Extract object params, return as dict
        """

        params = self.request.query_params.lists()
        params_map = {}
        prefix = name[:-1]
        offset = len(prefix)
        for name, value in params:
            if name.startswith(prefix):
                if name.endswith('}'):
                    name = name[offset:-1]
                elif name.endswith('}[]'):
                    # strip off trailing []
                    # this fixes an Ember queryparams issue
                    name = name[offset:-3]
                else:
                    # malformed argument like:
                    # filter{foo=bar
                    raise exceptions.ParseError(
                        '"%s" is not a well-formed filter key.' % name
                    )
            else:
                continue
            params_map[name] = value

        return params_map

    def get_queryset(self, queryset=None):
        """
        Returns a queryset for this request.

        Arguments:
          queryset: Optional root-level queryset.
        """
        serializer = self.get_serializer()
        return getattr(self, 'queryset', serializer.Meta.model.objects.all())

    def get_request_fields(self):
        """Parses the INCLUDE and EXCLUDE features.

        Extracts the dynamic field features from the request parameters
        into a field map that can be passed to a serializer.

        Returns:
          A nested dict mapping serializer keys to
          True (include) or False (exclude).
        """
        if hasattr(self, '_request_fields'):
            return self._request_fields

        include_fields = self.get_request_feature(self.INCLUDE)
        exclude_fields = self.get_request_feature(self.EXCLUDE)
        request_fields = {}
        for fields, include in(
                (include_fields, True),
                (exclude_fields, False)):
            if fields is None:
                continue
            for field in fields:
                field_segments = field.split('.')
                num_segments = len(field_segments)
                current_fields = request_fields
                for i, segment in enumerate(field_segments):
                    last = i == num_segments - 1
                    if segment:
                        if last:
                            current_fields[segment] = include
                        else:
                            if segment not in current_fields:
                                current_fields[segment] = {}
                            current_fields = current_fields[segment]
                    elif not last:
                        # empty segment must be the last segment
                        raise exceptions.ParseError(
                            '"%s" is not a valid field.' %
                            field
                        )

        self._request_fields = request_fields
        return request_fields

    def get_request_patch_all(self):
        patch_all = self.get_request_feature(self.PATCH_ALL)
        if not patch_all:
            return None
        patch_all = patch_all.lower()
        if patch_all == 'query':
            pass
        elif is_truthy(patch_all):
            patch_all = True
        else:
            raise exceptions.ParseError(
                '"%s" is not valid for %s' % (
                    patch_all,
                    self.PATCH_ALL
                )
            )
        return patch_all

    def get_request_debug(self):
        debug = self.get_request_feature(self.DEBUG)
        return is_truthy(debug) if debug is not None else None

    def get_request_sideloading(self):
        sideloading = self.get_request_feature(self.SIDELOADING)
        return is_truthy(sideloading) if sideloading is not None else None

    def is_update(self):
        if (
            self.request and
            self.request.method.upper() in UPDATE_REQUEST_METHODS
        ):
            return True
        else:
            return False

    def is_delete(self):
        if (
            self.request and
            self.request.method.upper() == DELETE_REQUEST_METHOD
        ):
            return True
        else:
            return False

    def get_serializer(self, *args, **kwargs):
        if 'request_fields' not in kwargs:
            kwargs['request_fields'] = self.get_request_fields()
        if 'sideloading' not in kwargs:
            kwargs['sideloading'] = self.get_request_sideloading()
        if 'debug' not in kwargs:
            kwargs['debug'] = self.get_request_debug()
        if 'envelope' not in kwargs:
            kwargs['envelope'] = True
        if self.is_update():
            kwargs['include_fields'] = '*'
        return super(
            WithDynamicViewSetMixin, self
        ).get_serializer(
            *args, **kwargs
        )

    def paginate_queryset(self, *args, **kwargs):
        if self.PAGE in self.features:
            # make sure pagination is enabled
            if (
                self.PER_PAGE not in self.features and
                self.PER_PAGE in self.request.query_params
            ):
                # remove per_page if it is disabled
                self.request.query_params[self.PER_PAGE] = None
            return super(
                WithDynamicViewSetMixin, self
            ).paginate_queryset(
                *args, **kwargs
            )
        return None

    def _prefix_inex_params(self, request, feature, prefix):
        values = self.get_request_feature(feature)
        if not values:
            return
        del request.query_params[feature]
        request.query_params.add(
            feature,
            [prefix + val for val in values]
        )

    def list_related(self, request, pk=None, field_name=None):
        """Fetch related object(s), as if sideloaded (used to support
        link objects).

        This method gets mapped to `/<resource>/<pk>/<field_name>/` by
        DynamicRouter for all DynamicRelationField fields. Generally,
        this method probably shouldn't be overridden.

        An alternative implementation would be to generate reverse queries.
        For an exploration of that approach, see:
            https://gist.github.com/ryochiji/54687d675978c7d96503
        """

        # Explicitly disable support filtering. Applying filters to this
        # endpoint would require us to pass through sideload filters, which
        # can have unintended consequences when applied asynchronously.
        if self.get_request_feature(self.FILTER):
            raise ValidationError(
                'Filtering is not enabled on relation endpoints.'
            )

        # Prefix include/exclude filters with field_name so it's scoped to
        # the parent object.
        field_prefix = field_name + '.'
        self._prefix_inex_params(request, self.INCLUDE, field_prefix)
        self._prefix_inex_params(request, self.EXCLUDE, field_prefix)

        # Filter for parent object, include related field.
        self.request.query_params.add('filter{pk}', pk)
        self.request.query_params.add(self.INCLUDE, field_prefix)

        # Get serializer and field.
        serializer = self.get_serializer()
        field = serializer.fields.get(field_name)
        if field is None:
            raise ValidationError('Unknown field: "%s".' % field_name)

        # Query for root object, with related field prefetched
        queryset = self.get_queryset()
        queryset = self.filter_queryset(queryset)
        obj = queryset.first()

        if not obj:
            return Response("Not found", status=404)

        # Serialize the related data. Use the field's serializer to ensure
        # it's configured identically to the sideload case. One difference
        # is we need to set `envelope=True` to get the sideload-processor
        # applied.
        related_szr = field.get_serializer(envelope=True)
        try:
            # TODO(ryo): Probably should use field.get_attribute() but that
            #            seems to break a bunch of things. Investigate later.
            related_szr.instance = getattr(obj, field.source)
        except ObjectDoesNotExist:
            # See:
            # http://jsonapi.org/format/#fetching-relationships-responses-404
            # This is a case where the "link URL exists but the relationship
            # is empty" and therefore must return a 200.
            return Response({}, status=200)

        return Response(related_szr.data)

    def get_extra_filters(self, request):
        # Override this method to enable addition of extra filters
        # (i.e., a Q()) so custom filters can be added to the queryset without
        # running into https://code.djangoproject.com/ticket/18437
        # which, without this, would mean that filters added to the queryset
        # after this is called may not behave as expected.
        return None


class DynamicModelViewSet(WithDynamicViewSetMixin, viewsets.ModelViewSet):

    ENABLE_BULK_PARTIAL_CREATION = settings.ENABLE_BULK_PARTIAL_CREATION
    ENABLE_BULK_UPDATE = settings.ENABLE_BULK_UPDATE
    ENABLE_PATCH_ALL = settings.ENABLE_PATCH_ALL

    def _get_bulk_payload(self, request):
        plural_name = self.get_serializer_class().get_plural_name()
        if isinstance(request.data, list):
            return request.data
        elif plural_name in request.data and len(request.data) == 1:
            return request.data[plural_name]
        return None

    def _bulk_update(self, data, partial=False):
        # Restrict the update to the filtered queryset.
        serializer = self.get_serializer(
            self.filter_queryset(self.get_queryset()),
            data=data,
            many=True,
            partial=partial
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _validate_patch_all(self, data):
        if not isinstance(data, dict):
            raise ValidationError(
                'Patch-all data must be in object form'
            )
        serializer = self.get_serializer()
        fields = serializer.get_all_fields()
        validated = {}
        for name, value in six.iteritems(data):
            field = fields.get(name, None)
            if field is None:
                raise ValidationError(
                    'Unknown field: "%s"' % name
                )
            source = field.source or name
            if source == '*' or field.read_only:
                raise ValidationError(
                    'Cannot update field: "%s"' % name
                )
            validated[source] = value
        return validated

    def _patch_all_query(self, queryset, data):
        # update by queryset
        try:
            return queryset.update(**data)
        except Exception as e:
            raise ValidationError(
                'Failed to bulk-update records:\n'
                '%s\n'
                'Data: %s' % (
                    str(e),
                    str(data)
                )
            )

    def _patch_all_loop(self, queryset, data):
        # update by transaction loop
        updated = 0
        try:
            with transaction.atomic():
                for record in queryset:
                    for k, v in six.iteritems(data):
                        setattr(record, k, v)
                    record.save()
                    updated += 1
                return updated
        except IntegrityError as e:
            raise ValidationError(
                'Failed to update records:\n'
                '%s\n'
                'Data: %s' % (
                    str(e),
                    str(data)
                )
            )

    def _patch_all(self, data, query=False):
        queryset = self.filter_queryset(self.get_queryset())
        data = self._validate_patch_all(data)
        updated = (
            self._patch_all_query(queryset, data) if query
            else self._patch_all_loop(queryset, data)
        )
        return Response({
            'meta': {
                'updated': updated
            }
        }, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        """Update one or more model instances.

        If ENABLE_BULK_UPDATE is set, multiple previously-fetched records
        may be updated in a single call, provided their IDs.

        If ENABLE_PATCH_ALL is set, multiple records
        may be updated in a single PATCH call, even without knowing their IDs.

        *WARNING*: ENABLE_PATCH_ALL should be considered an advanced feature
        and used with caution. This feature must be enabled at the viewset level
        and must also be requested explicitly by the client
        via the "patch-all" query parameter.

        This parameter can have one of the following values:

            true (or 1): records will be fetched and then updated in a transaction loop
              - The `Model.save` method will be called and model signals will run
              - This can be slow if there are too many signals or many records in the query
              - This is considered the more safe and default behavior
            query: records will be updated in a single query
              - The `QuerySet.update` method will be called and model signals will not run
              - This will be fast, but may break data constraints that are controlled by signals
              - This is considered unsafe but useful in certain situations

        The server's successful response to a patch-all request
        will NOT include any individual records. Instead, the response content will contain
        a "meta" object with an "updated" count of updated records.

        Examples:

        Update one dog:

            PATCH /dogs/1/
            {
                'fur': 'white'
            }

        Update many dogs by ID:

            PATCH /dogs/
            [
                {'id': 1, 'fur': 'white'},
                {'id': 2, 'fur': 'black'},
                {'id': 3, 'fur': 'yellow'}
            ]

        Update all dogs in a query:

            PATCH /dogs/?filter{fur.contains}=brown&patch-all=true
            {
                'fur': 'gold'
            }
        """  # noqa
        if self.ENABLE_BULK_UPDATE:
            patch_all = self.get_request_patch_all()
            if self.ENABLE_PATCH_ALL and patch_all:
                # patch-all update
                data = request.data
                return self._patch_all(
                    data,
                    query=(patch_all == 'query')
                )
            else:
                # bulk payload update
                partial = 'partial' in kwargs
                bulk_payload = self._get_bulk_payload(request)
                if bulk_payload:
                    return self._bulk_update(bulk_payload, partial)

        # singular update
        try:
            return super(DynamicModelViewSet, self).update(request, *args,
                                                           **kwargs)
        except AssertionError as e:
            err = str(e)
            if 'Fix your URL conf' in err:
                # this error is returned by DRF if a client
                # makes an update request (PUT or PATCH) without an ID
                # since DREST supports bulk updates with IDs contained in data,
                # we return a 400 instead of a 500 for this case,
                # as this is not considered a misconfiguration
                raise exceptions.ValidationError(err)
            else:
                raise

    def _create_many(self, data):
        items = []
        errors = []
        result = {}
        serializers = []

        for entry in data:
            serializer = self.get_serializer(data=entry)
            try:
                serializer.is_valid(raise_exception=True)
            except exceptions.ValidationError as e:
                errors.append({
                    'detail': str(e),
                    'source': entry
                })
            else:
                if self.ENABLE_BULK_PARTIAL_CREATION:
                    self.perform_create(serializer)
                    items.append(
                        serializer.to_representation(serializer.instance))
                else:
                    serializers.append(serializer)
        if not self.ENABLE_BULK_PARTIAL_CREATION and not errors:
            for serializer in serializers:
                self.perform_create(serializer)
                items.append(
                    serializer.to_representation(serializer.instance))

        # Populate serialized data to the result.
        result = SideloadingProcessor(
            self.get_serializer(),
            items
        ).data

        # Include errors if any.
        if errors:
            result['errors'] = errors

        code = (status.HTTP_201_CREATED if not errors else
                status.HTTP_400_BAD_REQUEST)

        return Response(result, status=code)

    def create(self, request, *args, **kwargs):
        """
        Either create a single or many model instances in bulk
        using the Serializer's many=True ability from Django REST >= 2.2.5.

        The data can be represented by the serializer name (single or plural
        forms), dict or list.

        Examples:

        POST /dogs/
        {
          "name": "Fido",
          "age": 2
        }

        POST /dogs/
        {
          "dog": {
            "name": "Lucky",
            "age": 3
          }
        }

        POST /dogs/
        {
          "dogs": [
            {"name": "Fido", "age": 2},
            {"name": "Lucky", "age": 3}
          ]
        }

        POST /dogs/
        [
            {"name": "Fido", "age": 2},
            {"name": "Lucky", "age": 3}
        ]
        """
        bulk_payload = self._get_bulk_payload(request)
        if bulk_payload:
            return self._create_many(bulk_payload)
        return super(DynamicModelViewSet, self).create(
            request, *args, **kwargs)

    def _destroy_many(self, data):
        instances = self.get_queryset().filter(
            id__in=[d['id'] for d in data]
        ).distinct()
        for instance in instances:
            self.check_object_permissions(self.request, instance)
            self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def destroy(self, request, *args, **kwargs):
        """
        Either delete a single or many model instances in bulk

        DELETE /dogs/
        {
            "dogs": [
                {"id": 1},
                {"id": 2}
            ]
        }

        DELETE /dogs/
        [
            {"id": 1},
            {"id": 2}
        ]
        """
        bulk_payload = self._get_bulk_payload(request)
        if bulk_payload:
            return self._destroy_many(bulk_payload)
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        if lookup_url_kwarg not in kwargs:
            # assume that it is a poorly formatted bulk request
            return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
        return super(DynamicModelViewSet, self).destroy(
            request, *args, **kwargs
        )
