"""This module contains custom router classes."""
from collections import OrderedDict

from django.utils import six
from django.shortcuts import redirect
from rest_framework import views
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter, Route, replace_methodname

from dynamic_rest.meta import get_model_table
from dynamic_rest.conf import settings
from dynamic_rest.compat import (
    get_script_prefix,
)

from django.core.urlresolvers import resolve

resource_map = {}
resource_name_map = {}


def get_directory(request, icons=False):
    """Get API directory as a dictionary of name -> URL"""
    view = resolve(request.path)
    view = view.func
    if hasattr(view, 'view_class'):
        view = view.view_class
    elif hasattr(view, 'cls'):
        view = view.cls
    router = view._router
    return router.get_directory(request, icons=icons)


def modify_list_route(routes):
    # Identify the list route, add PATCH so we can
    # have bulk PATCH requests
    if not settings.ENABLE_BULK_UPDATE:
        return
    list_route = next(i for i in routes if i.name == '{basename}-list')
    list_route.mapping['patch'] = 'partial_update'
    list_route.mapping['delete'] = 'destroy'


class DynamicRouter(DefaultRouter):
    routes = list(DefaultRouter.routes)
    modify_list_route(routes)

    def __init__(self, *args, **kwargs):
        optional_trailing_slash = kwargs.pop('optional_trailing_slash', True)
        super(DynamicRouter, self).__init__(*args, **kwargs)
        if optional_trailing_slash:
            self.trailing_slash = '/?'

    def get_api_root_view(self, **kwargs):
        """Return API root view, using the global directory."""
        class API(views.APIView):
            _router = self

            def get_view_name(self, *args, **kwargs):
                return settings.API_NAME

            def get(self, request, *args, **kwargs):
                if (
                    settings.API_ROOT_SECURE and
                    not request.user.is_authenticated()
                ):
                    return redirect(
                        '%s?next=%s' % (
                            settings.ADMIN_LOGIN_URL,
                            request.path
                        )
                    )
                result = get_directory(request)
                return Response(result)

        view = API.as_view()
        return view

    def get_directory(self, request, icons=False):
        result = OrderedDict()
        user = request.user
        for prefix, viewset, basename in self.registry:
            if hasattr(viewset, 'get_user_permissions'):
                permissions = viewset.get_user_permissions(user)
                if permissions and not permissions.list:
                    continue
            if not hasattr(viewset, 'serializer_class'):
                continue

            serializer_class = viewset.serializer_class
            url = serializer_class.get_url()
            name = serializer_class.get_plural_name()
            name = name.title().replace('_', ' ')
            if icons:
                icon = serializer_class.get_icon()
                result[name] = (url, icon)
            else:
                result[name] = url
        return result

    def register(self, prefix, viewset, base_name=None, namespace=None):
        if base_name is None:
            base_name = prefix
        if namespace is not None:
            base_name = '%s-%s' % (namespace, base_name)

        result = super(DynamicRouter, self).register(
            prefix, viewset, base_name
        )

        url_name = self.routes[0].name.format(basename=base_name)
        serializer_class = getattr(viewset, 'serializer_class', None)
        viewset._router = self
        if serializer_class:
            # Set URL on the serializer class so that it can determine its
            # endpoint URL.
            # If a serializer class is associated with multiple views,
            # it will take on the URL of the last view.
            # TODO: is this a problem?
            serializer_class._router = self
            serializer_class._url = url_name

        return result

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
            resource_name = serializer.get_name()
            path_name = serializer.get_plural_name()
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
        base_path = r'%s' % base_path + path_name
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

        # Make sure the resource name isn't registered, either
        # TODO: Think of a better way to clean this up, there's a lot of
        # duplicated effort here, between `resource_name` and `resource_key`
        # This resource name -> key mapping is currently only used by
        # the DynamicGenericRelationField
        if resource_name in resource_name_map:
            resource_key = resource_name_map[resource_name]
            raise Exception(
                "The resource name '%s' has already been mapped to '%s'."
                " A resource name can only be used once." % (
                    resource_name,
                    resource_map[resource_key]['path']
                )
            )

        # map the resource name to the resource key for easier lookup
        resource_name_map[resource_name] = resource_key

    @staticmethod
    def get_canonical_path(resource_key, pk=None):
        """
        Return canonical resource path.

        Arguments:
            resource_key - Canonical resource key
                           i.e. Serializer.get_resource_key().
            pk - (Optional) Object's primary key for a single-resource URL.
        Returns: Absolute URL as string.
        """

        if resource_key not in resource_map:
            # Note: Maybe raise?
            return None

        base_path = get_script_prefix() + resource_map[resource_key]['path']
        if pk:
            return '%s/%s/' % (base_path, pk)
        else:
            return base_path

    @staticmethod
    def get_canonical_serializer(
        resource_key,
        model=None,
        instance=None,
        resource_name=None
    ):
        """
        Return canonical serializer for a given resource name.

        Arguments:
            resource_key - Resource key, usually DB table for model-based
                           resources, otherwise the plural name.
            model - (Optional) Model class to look up by.
            instance - (Optional) Model object instance.
        Returns: serializer class
        """

        if model:
            resource_key = get_model_table(model)
        elif instance:
            resource_key = instance._meta.db_table
        elif resource_name:
            resource_key = resource_name_map[resource_name]

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

        serializer = viewset.serializer_class()
        fields = getattr(serializer, 'get_link_fields', lambda: [])()

        route_name = '{basename}-{methodnamehyphen}'

        for field_name, field in six.iteritems(fields):
            has_list_related = hasattr(viewset, 'list_related')
            has_create_related = hasattr(viewset, 'create_related')
            url = (
                r'^{prefix}/{lookup}/(?P<field_name>%s)'
                '{trailing_slash}$' % field_name
            )
            mapping = {}
            if has_list_related:
                mapping['get'] = 'list_related'
            if has_create_related:
                mapping['post'] = 'create_related'
            if mapping:
                routes.append(Route(
                    url=url,
                    mapping=mapping,
                    name=replace_methodname(route_name, field_name),
                    initkwargs={}
                ))
        return routes
