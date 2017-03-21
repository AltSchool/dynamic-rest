"""This module contains custom renderer classes."""
from rest_framework.renderers import (
    BrowsableAPIRenderer,
)
try:
    from rest_framework.renderers import AdminRenderer
except:
    # DRF < 3.3
    class AdminRenderer(BrowsableAPIRenderer):
        pass

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
    """Admin renderer."""

    template = 'dynamic_rest/admin.html'
    COLUMN_BLACKLIST = ('id', 'links')

    def get_context(self, data, media_type, context):
        def process(result):
            if result.get('links', {}).get('self'):
                result['url'] = result['links']['self']
        path = context.get('request').path
        if path != '/':
            data = unpack(data)

        context = super(DynamicAdminRenderer, self).get_context(
            data,
            media_type,
            context
        )

        # to account for the DREST envelope
        # (data is stored one level deeper than expected in the response)
        results = context['results']
        if isinstance(results, list):
            for result in results:
                process(result)
        else:
            process(results)

        context['columns'] = [
            c for c in context['columns'] if c not in self.COLUMN_BLACKLIST
        ]
        context['details'] = context['columns']
        return context

    def render_form_for_serializer(self, serializer):
        serializer.disable_envelope()
        return super(
            DynamicAdminRenderer, self
        ).render_form_for_serializer(serializer)
