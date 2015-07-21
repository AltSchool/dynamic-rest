from contextlib import contextmanager

from django.conf import settings
from django.db import transaction

from dynamic_rest.pagination import DynamicPageNumberPagination
from dynamic_rest.metadata import DynamicMetadata
from dynamic_rest.filters import DynamicFilterBackend
from dynamic_rest.query import QueryParams
from dynamic_rest.signals import (
    pre_create, post_create,
    pre_update, post_update,
    pre_delete, post_delete
)

from rest_framework import viewsets, exceptions
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer

dynamic_settings = getattr(settings, 'DYNAMIC_REST', {})

UPDATE_REQUEST_METHODS = ('PUT', 'PATCH', 'POST')

CREATE = 1
UPDATE = 3
DELETE = 4

PRE_CREATE = 1
POST_CREATE = 2
PRE_UPDATE = 3
POST_UPDATE = 4
PRE_DELETE = 5
POST_DELETE = 6


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
    transactions = ()
    signals = ()
    filter_backends = (DynamicFilterBackend,)

    def perform_update(self, serializer):
        with self.in_transaction(UPDATE):
            instance = serializer.instance
            if PRE_UPDATE in self.signals:
                pre_update.send(
                    sender=self.__class__,
                    request=self.request,
                    instance=instance,
                    serializer=serializer
                )
            if POST_UPDATE in self.signals:
                full_serializer = self.serializer_class(dynamic=False)
                pre_data = full_serializer.to_representation(instance)

            super(WithDynamicViewSetMixin, self).perform_update(serializer)

            if POST_UPDATE in self.signals:
                post_update.send(
                    sender=self.__class__,
                    request=self.request,
                    pre_data=pre_data,
                    instance=serializer.instance,
                    serializer=serializer
                )

    def perform_create(self, serializer):
        with self.in_transaction(CREATE):
            if PRE_CREATE in self.signals:
                pre_create.send(
                    sender=self.__class__,
                    request=self.request,
                    serializer=serializer
                )

            super(WithDynamicViewSetMixin, self).perform_create(serializer)

            if POST_CREATE in self.signals:
                post_create.send(
                    sender=self.__class__,
                    request=self.request,
                    instance=serializer.instance,
                    serializer=serializer
                )

    def perform_destroy(self, instance):
        with self.in_transaction(DELETE):
            if PRE_DELETE in self.signals:
                pre_delete.send(
                    sender=self.__class__,
                    request=self.request,
                    instance=instance
                )

            if POST_DELETE in self.signals:
                full_serializer = self.serializer_class(dynamic=False)
                pre_data = full_serializer.to_representation(instance)

            super(WithDynamicViewSetMixin, self).perform_destroy(instance)

            if POST_DELETE in self.signals:
                post_delete.send(
                    sender=self.__class__,
                    request=self.request,
                    instance=instance,
                    pre_data=pre_data
                )

    @contextmanager
    def in_transaction(self, request_type):
        if request_type in self.transactions:
            with transaction.atomic():
                yield
        else:
            yield

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


class DynamicModelViewSet(WithDynamicViewSetMixin, viewsets.ModelViewSet):
    pass
