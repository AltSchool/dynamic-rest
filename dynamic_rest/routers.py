from rest_framework.routers import DefaultRouter, Route, replace_methodname


class DynamicRouter(DefaultRouter):

    def get_relation_routes(self, viewset):
        """
        Generate routes to serve async relation links.
        """

        routes = []

        if not hasattr(viewset, 'serializer_class'):
            return routes
        if not hasattr(viewset, 'async_field'):
            return routes

        serializer = viewset.serializer_class()
        fields = getattr(serializer, 'get_all_fields', serializer.get_fields)()

        route_name = '{basename}-{methodnamehyphen}'

        for field_name, field in fields.iteritems():
            if not getattr(field, 'async', False):
                continue

            url = r'^{prefix}/{lookup}/%s{trailing_slash}$' % field_name
            methodname = (
                field_name if hasattr(viewset, field_name) else 'async_field'
            )
            routes.append(Route(
                url=url,
                mapping={'get': methodname},
                name=replace_methodname(route_name, field_name),
                initkwargs={'field_name': field_name}
            ))
        return routes

    def get_routes(self, viewset):
        """
        DREST routes injection.
        """
        routes = super(DynamicRouter, self).get_routes(viewset)
        routes += self.get_relation_routes(viewset)
        return routes
