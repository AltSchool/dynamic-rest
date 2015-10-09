from rest_framework.routers import DefaultRouter, Route, replace_methodname
from dynamic_rest.fields import DynamicRelationField

directory = {}


class DynamicRouter(DefaultRouter):

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
                },
            }
            'groups': {
               '_url': 'groups-list'
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

        for field_name, field in fields.iteritems():
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
