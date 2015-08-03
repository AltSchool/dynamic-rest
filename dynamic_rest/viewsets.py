from django.conf import settings
from django.http import QueryDict

from rest_framework import viewsets, exceptions
from rest_framework.exceptions import ValidationError
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response

from dynamic_rest.pagination import DynamicPageNumberPagination
from dynamic_rest.metadata import DynamicMetadata
from dynamic_rest.filters import DynamicFilterBackend


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

        # Primary usecase is to return related data identically to if it
        # were sideloaded, so no field inclusion/exclusion and filtering is
        # supported.
        # NOTE: This also means sideload filters in the parent query also
        #       do not get transferred to the link object. However, default
        #       querysets on DynamicRelationFields are respected.
        if self.get_request_feature(self.INCLUDE) \
                or self.get_request_feature(self.EXCLUDE) \
                or self.get_request_feature(self.FILTER):
            raise ValidationError(
                "Inclusion/exclusion and filtering is not enabled on "
                "relation endpoints."
            )

        # Filter for parent object, include related field.
        self.request.query_params.add('filter{pk}', pk)
        self.request.query_params.add('include[]', field_name + '.')

        # Get serializer and field.
        serializer = self.get_serializer()
        field = serializer.fields.get(field_name)
        if field is None:
            raise ValidationError("Unknown field: %s" % field_name)

        # Query for root object, with related field sideloaded/prefetched
        # Note: Filter against related field works here using standard
        #       sideload filter query.
        queryset = self.get_queryset()
        queryset = self.filter_queryset(queryset)
        obj = queryset.first()

        if not obj:
            return Response("Not found", status=404)

        # Serialize the related data
        serializer = field.get_serializer(
            getattr(obj, field.source),
            sideload=getattr(self, 'sideload', True)
        )
        return Response(serializer.data)


class DynamicModelViewSet(WithDynamicViewSetMixin, viewsets.ModelViewSet):
    pass
