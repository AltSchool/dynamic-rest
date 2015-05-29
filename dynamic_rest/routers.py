from rest_framework.routers import DefaultRouter, Route, replace_methodname
from dynamic_rest.fields import DynamicRelationField


class DynamicRouter(DefaultRouter):

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

            methodname = field_name
            if hasattr(viewset, methodname):
                # See if a method with this name already exists, and is a
                # DRF @detail_route or @list_route. If so, skip it.
                if hasattr(getattr(viewset, methodname), 'bind_to_methods'):
                    continue
            else:
                # Use DynamicViewSet.list_related()
                methodname = 'list_related'

            url = r'^{prefix}/{lookup}/%s{trailing_slash}$' % field_name
            routes.append(Route(
                url=url,
                mapping={'get': methodname},
                name=replace_methodname(route_name, field_name),
                initkwargs={'field_name': field_name} # attaches to viewset
            ))
        return routes
