from django.conf import settings
from django.http import QueryDict

from dynamic_rest.pagination import DynamicPageNumberPagination
from dynamic_rest.metadata import DynamicMetadata
from dynamic_rest.filters import DynamicFilterBackend

from rest_framework import viewsets, exceptions
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.decorators import detail_route
from rest_framework.response import Response

dynamic_settings = getattr(settings, 'DYNAMIC_REST', {})
UPDATE_REQUEST_METHODS = ('PUT', 'PATCH', 'POST')


class QueryParams(QueryDict):

    """
    Extension of Django's QueryDict. Instantiated from a DRF Request
    object, and returns a mutable QueryDict subclass.
    Also adds methods that might be useful for our usecase.
    """

    def __init__(self, query_params, *args, **kwargs):
        query_string = getattr(query_params, 'urlencode', lambda: '')()
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
      sideload: Whether or not to enable sideloading in the DynamicRenderer.
      meta: Extra data that is added to the response by the DynamicRenderer.
    """

    INCLUDE = 'include[]'
    EXCLUDE = 'exclude[]'
    FILTER = 'filter{}'
    PAGE = dynamic_settings.get('PAGE_QUERY_PARAM', 'page')
    PER_PAGE = dynamic_settings.get('PAGE_SIZE_QUERY_PARAM', 'per_page')

    # TODO: add support for `sort{}`
    pagination_class = DynamicPageNumberPagination
    metadata_class = DynamicMetadata
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer)
    features = (INCLUDE, EXCLUDE, FILTER, PAGE, PER_PAGE)
    sideload = True
    meta = None
    filter_backends = (DynamicFilterBackend,)

    def initialize_request(self, request, *args, **kargs):
        """
        Override DRF initialize_request() method to swap request.GET
        (which is aliased by request.QUERY_PARAMS) with a mutable instance
        of QueryParams.
        """
        request.GET = QueryParams(request.GET)
        return super(WithDynamicViewSetMixin, self).initialize_request(
            request, *args, **kargs)

    def get_request_feature(self, name):
        """Parses the request for a particular feature.

        Arguments:
          name: A feature name.

        Returns:
          A feature parsed from the URL if the feature is supported, or None.
        """
        if '[]' in name:
            # array-type
            return self.request.QUERY_PARAMS.getlist(
                name) if name in self.features else None
        elif '{}' in name:
            # object-type (keys are not consistent)
            return self._extract_object_params(
                name) if name in self.features else {}
        else:
            # single-type
            return self.request.QUERY_PARAMS.get(
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
                        "'%s' is not a well-formed filter key" % name
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
        """Parses the `include[]` and `exclude[]` features.

        Extracts the dynamic field features from the request parameters
        into a field map that can be passed to a serializer.

        Returns:
          A nested dict mapping serializer keys to
          True (include) or False (exclude).
        """
        if hasattr(self, '_request_fields'):
            return self._request_fields

        include_fields = self.get_request_feature('include[]')
        exclude_fields = self.get_request_feature('exclude[]')
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
                            "'%s' is not a valid field" %
                            field)

        self._request_fields = request_fields
        return request_fields

    def get_serializer(self, *args, **kwargs):
        if 'request_fields' not in kwargs:
            kwargs['request_fields'] = self.get_request_fields()
        if 'sideload' not in kwargs:
            kwargs['sideload'] = self.sideload
        if self.request and self.request.method.upper() \
                in UPDATE_REQUEST_METHODS:
            kwargs['include_fields'] = '*'
        return super(
            WithDynamicViewSetMixin, self).get_serializer(
            *args, **kwargs)

    def paginate_queryset(self, *args, **kwargs):
        if self.PAGE in self.features:
            # make sure pagination is enabled
            if self.PER_PAGE not in self.features and \
                    self.PER_PAGE in self.request.QUERY_PARAMS:
                # remove per_page if it is disabled
                self.request.QUERY_PARAMS[self.PER_PAGE] = None
            return super(
                WithDynamicViewSetMixin, self).paginate_queryset(
                *args, **kwargs)
        return None

    @detail_route(methods=['get'])
    def async_field(self, request, pk=None): 
        """
        This method gets mapped by DRF to `/<resource>/<pk>/async_field/`
        and will be available on all DynamicModelViewSets.  The serializer 
        can construct these URLs, and return as JSON API "link" objects.

        TODO: Support for filter. Currently, filtering is handled by the
              root API request, and a set of IDs is passed here. This means
              the root request takes the hit of the DB query. Instead, if
              the filter params are passed in, the filtering can be done
              here.
        """

        field_name = request.QUERY_PARAMS.get('field')
        ids = request.QUERY_PARAMS.getlist('id')

        # Get serializer with dynamic=False so we can get full (and bound)
        # fields list.
        serializer = self.get_serializer(dynamic=False)
        field = serializer.fields.get(field_name)
        if field is None: 
            return Response("Unknown field: %s" % field_name, status=400)

        # Get related objects
        # TODO: Use logic in DynamicFilterBackend to do things like 
        #       recursive prefetching.
        if ids:
            model = field.serializer_class.Meta.model
            related_objs = model.objects.filter(pk__in=ids) 
        else:
            # Get root object, and fetch requested relational objects
            model = serializer.get_model()
            obj = model.objects.select_related(field.source).get(pk=pk)
            related_objs = getattr(obj, field.source, []) 

        # Serialize root object + requested relation, then sideload
        data = field.serializer_class(
              related_objs,
              many=True,
              sideload = True
              ).data

        return Response(data, status=400) 


class DynamicModelViewSet(WithDynamicViewSetMixin, viewsets.ModelViewSet):
    pass
