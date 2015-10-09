from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.reverse import reverse


class DynamicBrowsableAPIRenderer(BrowsableAPIRenderer):

    def get_context(self, data, media_type, context):
        context = super(DynamicBrowsableAPIRenderer, self).get_context(
            data,
            media_type,
            context
        )
        request = context['request']
        context['directory'] = self.get_directory(request)
        return context

    def get_directory(self, request):
        """Get API directory as a nested list of lists."""
        from dynamic_rest.routers import directory

        def get_url(url):
            return reverse(url) if url else url

        def is_active_url(path, url):
            return path.startswith(url) if url else False

        path = request.path
        directory_list = []
        sort_key = lambda r: r[0]
        # TODO(ant): support arbitrarily nested
        # structure, for now it is capped at a single level
        # for UX reasons
        for group_name, endpoints in sorted(
            directory.iteritems(),
            key=sort_key
        ):
            endpoints_list = []
            for endpoint_name, endpoint in sorted(
                endpoints.iteritems(),
                key=sort_key
            ):
                if endpoint_name == '_url':
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
