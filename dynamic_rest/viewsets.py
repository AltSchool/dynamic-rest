"""This module contains custom viewset classes."""
from django.core.exceptions import ObjectDoesNotExist
from django.http import QueryDict
from django.utils import six
from rest_framework import exceptions, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response

from dynamic_rest.conf import settings
from dynamic_rest.filters import DynamicFilterBackend, DynamicSortingFilter
from dynamic_rest.metadata import DynamicMetadata
from dynamic_rest.pagination import DynamicPageNumberPagination
from dynamic_rest.processors import SideloadingProcessor
from dynamic_rest.renderers import DynamicBrowsableAPIRenderer
from dynamic_rest.utils import is_truthy

UPDATE_REQUEST_METHODS = ('PUT', 'PATCH', 'POST')
DELETE_REQUEST_METHOD = 'DELETE'


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
    INCLUDE = 'include[]'
    EXCLUDE = 'exclude[]'
    FILTER = 'filter{}'
    SORT = 'sort[]'
    PAGE = settings.PAGE_QUERY_PARAM
    PER_PAGE = settings.PAGE_SIZE_QUERY_PARAM

    # TODO: add support for `sort{}`
    pagination_class = DynamicPageNumberPagination
    metadata_class = DynamicMetadata
    renderer_classes = (JSONRenderer, DynamicBrowsableAPIRenderer)
    features = (
        DEBUG,
        INCLUDE,
        EXCLUDE,
        FILTER,
        PAGE,
        PER_PAGE,
        SORT,
        SIDELOADING
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
        # it's configured identically to the sideload case.
        serializer = field.get_serializer(envelope=True)
        try:
            # TODO(ryo): Probably should use field.get_attribute() but that
            #            seems to break a bunch of things. Investigate later.
            serializer.instance = getattr(obj, field.source)
        except ObjectDoesNotExist:
            # See:
            # http://jsonapi.org/format/#fetching-relationships-responses-404
            # This is a case where the "link URL exists but the relationship
            # is empty" and therefore must return a 200.
            return Response({}, status=200)

        return Response(serializer.data)


class DynamicModelViewSet(WithDynamicViewSetMixin, viewsets.ModelViewSet):

    ENABLE_BULK_PARTIAL_CREATION = settings.ENABLE_BULK_PARTIAL_CREATION
    ENABLE_BULK_UPDATE = settings.ENABLE_BULK_UPDATE

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

    def update(self, request, *args, **kwargs):
        """Either update  a single or many model instances. Use list to
        indicate bulk update.

        Examples:

        PATCH /dogs/1/
        {
            'fur': 'white'
        }

        PATCH /dogs/
        {
            'dogs': [
                {'id': 1, 'fur': 'white'},
                {'id': 2, 'fur': 'black'},
                {'id': 3, 'fur': 'yellow'}
            ]
        }

        PATCH /dogs/?filter{fur.contains}=brown
        [
            {'id': 3, 'fur': 'gold'}
        ]
        """
        if self.ENABLE_BULK_UPDATE:
            partial = 'partial' in kwargs
            bulk_payload = self._get_bulk_payload(request)
            if bulk_payload:
                return self._bulk_update(bulk_payload, partial)
        return super(DynamicModelViewSet, self).update(request, *args,
                                                       **kwargs)

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
