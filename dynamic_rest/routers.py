"""This module contains custom router classes."""
from collections import OrderedDict

from django.utils import six
from rest_framework import views
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.routers import DefaultRouter, Route, replace_methodname

from dynamic_rest.fields import DynamicRelationField

directory = {}
resource_map = {}


def get_directory(request):
    """Get API directory as a nested list of lists."""

    def get_url(url):
        return reverse(url, request=request) if url else url

    def is_active_url(path, url):
        return path.startswith(url) if url and path else False

    path = request.path
    directory_list = []
    sort_key = lambda r: r[0]
    # TODO(ant): support arbitrarily nested
    # structure, for now it is capped at a single level
    # for UX reasons
    for group_name, endpoints in sorted(
        six.iteritems(directory),
        key=sort_key
    ):
        endpoints_list = []
        for endpoint_name, endpoint in sorted(
            six.iteritems(endpoints),
            key=sort_key
        ):
            if endpoint_name[:1] == '_':
                continue
            endpoint_url = get_url(endpoint.get('_url', None))
            active = is_active_url(path, endpoint_url)
            endpoints_list.append(
                (endpoint_name, endpoint_url, [], active)
            )

        url = get_url(endpoints.get('_url', None))
        active = is_active_url(path, url)
        directory_list.append(
            (group_name, url, endpoints_list, active)
        )
    return directory_list


class DynamicRouter(DefaultRouter):

    def __init__(self, *args, **kwargs):
        optional_trailing_slash = kwargs.pop('optional_trailing_slash', True)
        super(DynamicRouter, self).__init__(*args, **kwargs)
        if optional_trailing_slash:
            self.trailing_slash = '/?'

    def get_api_root_view(self):
        """Return API root view, using the global directory."""
        class API(views.APIView):
            _ignore_model_permissions = True

            def get(self, request, *args, **kwargs):
                directory_list = get_directory(request)
                result = OrderedDict()
                for group_name, url, endpoints, _ in directory_list:
                    if url:
                        result[group_name] = url
                    else:
                        group = OrderedDict()
                        for endpoint_name, url, _, _ in endpoints:
                            group[endpoint_name] = url
                        result[group_name] = group
                return Response(result)

        return API.as_view()

    def register(self, prefix, viewset, base_name=None):
        """Add any registered route into a global API directory.

        If the prefix includes a path separator,
        store the URL in the directory under the first path segment.
        Otherwise, store it as-is.

        For example, if there are two registered prefixes,
        'v1/users' and 'groups', `directory` will look liks:

        {
            'v1': {
                'users': {
                    '_url': 'users-list'
                    '_viewset': <class 'UserViewSet'>
                },
            }
            'groups': {
               '_url': 'groups-list'
               '_viewset': <class 'GroupViewSet'>
            }
        }
        """
        if base_name is None:
            base_name = prefix

        super(DynamicRouter, self).register(prefix, viewset, base_name)

        prefix_parts = prefix.split('/')
        if len(prefix_parts) > 1:
            prefix = prefix_parts[0]
            endpoint = '/'.join(prefix_parts[1:])
        else:
            endpoint = prefix
            prefix = None

        if prefix and prefix not in directory:
            current = directory[prefix] = {}
        else:
            current = directory.get(prefix, directory)

        list_name = self.routes[0].name
        url_name = list_name.format(basename=base_name)
        if endpoint not in current:
            current[endpoint] = {}
        current[endpoint]['_url'] = url_name
        current[endpoint]['_viewset'] = viewset

    def register_resource(self, viewset, namespace=None):
        """
        Register a viewset that should be considered the canonical
        endpoint for a particular resource. In addition to generating
        and registering the route, it adds the route in a reverse map
        to allow DREST to build the canonical URL for a given resource.

        Arguments:
            viewset - viewset class, should have `serializer_class` attr.
            namespace - (optional) URL namespace, e.g. 'v3'.
        """

        # Try to extract resource name from viewset.
        try:
            serializer = viewset.serializer_class()
            resource_key = serializer.get_resource_key()
            resource_name = serializer.get_plural_name()
        except:
            import traceback
            traceback.print_exc()
            raise Exception(
                "Failed to extract resource name from viewset: '%s'."
                " It, or its serializer, may not be DREST-compatible." % (
                    viewset
                )
            )

        # Construct canonical path and register it.
        if namespace:
            namespace = namespace.rstrip('/') + '/'
        base_path = namespace or ''
        base_path = r'%s' % base_path + resource_name
        self.register(base_path, viewset)

        # Make sure resource isn't already registered.
        if resource_key in resource_map:
            raise Exception(
                "The resource '%s' has already been mapped to '%s'."
                " Each resource can only be mapped to one canonical"
                " path. " % (
                    resource_key,
                    resource_map[resource_key]['path']
                )
            )

        # Register resource in reverse map.
        resource_map[resource_key] = {
            'path': base_path,
            'viewset': viewset
        }

    def get_canonical_path(self, resource, pk=None):
        """
        Return canonical resource path.

        Arguments:
            resource - Canonical resource name (i.e. Serializer.get_name()).
            pk - (Optional) Object's primary key for a single-resource URL.
        Returns: Absolute URL as string.
        """

        if resource not in resource_map:
            # Note: Maybe raise?
            return None

        base_path = '/' + resource_map[resource]['path']
        if pk:
            return base_path + '/%s/' % pk
        else:
            return base_path

    @staticmethod
    def get_canonical_serializer(resource_key):
        """
        Return canonical serializer for a given resource name.

        Arguments:
            resource_key - Resource key, usually DB table for model-based
                           resources, otherwise the plural name.
        Returns: serializer class
        """

        if resource_key not in resource_map:
            return None

        return resource_map[resource_key]['viewset'].serializer_class

    def get_routes(self, viewset):
        """
        DREST routes injection, overrides DRF's get_routes() method, which
        gets called for each registered viewset.
        """
        routes = super(DynamicRouter, self).get_routes(viewset)
        routes += self.get_relation_routes(viewset)
        return routes

    def get_relation_routes(self, viewset):
        """
        Generate routes to serve relational objects. This method will add
        a sub-URL for each relational field.

        e.g.
        A viewset for the following serializer:

          class UserSerializer(..):
              events = DynamicRelationField(EventSerializer, many=True)
              groups = DynamicRelationField(GroupSerializer, many=True)
              location = DynamicRelationField(LocationSerializer)

        will have the following URLs added:

          /users/<pk>/events/
          /users/<pk>/groups/
          /users/<pk>/location/
        """

        routes = []

        if not hasattr(viewset, 'serializer_class'):
            return routes
        if not hasattr(viewset, 'list_related'):
            return routes

        serializer = viewset.serializer_class()
        fields = getattr(serializer, 'get_all_fields', serializer.get_fields)()

        route_name = '{basename}-{methodnamehyphen}'

        for field_name, field in six.iteritems(fields):
            # Only apply to DynamicRelationFields
            # TODO(ryo): Maybe also apply in cases where fields are mapped
            #            directly to serializers?
            if not isinstance(field, DynamicRelationField):
                continue

            methodname = 'list_related'
            url = (
                r'^{prefix}/{lookup}/(?P<field_name>%s)'
                '{trailing_slash}$' % field_name
            )
            routes.append(Route(
                url=url,
                mapping={'get': methodname},
                name=replace_methodname(route_name, field_name),
                initkwargs={}
            ))
        return routes
