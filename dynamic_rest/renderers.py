from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.reverse import reverse


class DynamicBrowsableAPIRenderer(BrowsableAPIRenderer):

    def get_context(self, *args, **kwargs):
        context = super(DynamicBrowsableAPIRenderer, self).get_context(
            *args,
            **kwargs
        )
        context['directory'] = self.get_directory()
        return context

    def get_directory(self):
        """Get API directory as a nested list of lists."""
        from dynamic_rest.routers import directory

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
                endpoint_url = endpoint.get('_url', None)
                if endpoint_url:
                    endpoint_url = reverse(endpoint_url)
                endpoints_list.append((endpoint_name, endpoint_url, []))

            url = endpoints.get('_url', None)
            if url:
                url = reverse(url)
            directory_list.append((group_name, url, endpoints_list))
        return directory_list
