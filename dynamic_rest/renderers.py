"""This module contains custom renderer classes."""
from rest_framework.renderers import (
    BrowsableAPIRenderer,
    AdminRenderer
)
from dynamic_rest.utils import unpack


class DynamicBrowsableAPIRenderer(BrowsableAPIRenderer):
    """Renderer class that adds directory support to the Browsable API."""

    template = 'dynamic_rest/api.html'

    def get_context(self, data, media_type, context):
        from dynamic_rest.routers import get_directory

        context = super(DynamicBrowsableAPIRenderer, self).get_context(
            data,
            media_type,
            context
        )
        request = context['request']
        context['directory'] = get_directory(request)
        return context


class DynamicAdminRenderer(AdminRenderer):
    """Admin renderer override."""

    COLUMN_BLACKLIST = ('id', 'links', 'url')
    template = 'dynamic_rest/admin.html'

    def get_context(self, data, media_type, context):
        def add_url(result):
            if result.get('links', {}).get('self'):
                result['url'] = result['links']['self']

        context = super(DynamicAdminRenderer, self).get_context(
            data,
            media_type,
            context
        )

        # to account for the DREST envelope
        # (data is stored one level deeper than expected in the response)
        results = unpack(context['results'])
        if results is None:
            style = 'detail'
            header = {}
        elif isinstance(results, list):
            for result in results:
                add_url(result)
            header = results[0] if results else {}
            style = 'list'
        else:
            add_url(results)
            header = results
            style = 'detail'

        columns = [
            key for key in header.keys() if key not in self.COLUMN_BLACKLIST
        ]
        context['results'] = results
        context['columns'] = columns
        context['details'] = columns
        context['style'] = style
        return context

    def get_raw_data_form(self, data, view, method, request):
        print unpack(data)
        return super(
            DynamicAdminRenderer, self
        ).get_raw_data_form(unpack(data), view, method, request)
