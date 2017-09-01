"""This module contains custom renderer classes."""
from django.utils import six
from copy import copy
from rest_framework.renderers import (
    BrowsableAPIRenderer,
    HTMLFormRenderer,
    ClassLookupDict
)
try:
    from rest_framework.renderers import AdminRenderer
except:
    # DRF < 3.3
    class AdminRenderer(BrowsableAPIRenderer):
        format = 'admin'

from dynamic_rest.utils import unpack, get_breadcrumbs
from dynamic_rest.fields import DynamicRelationField


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

    def render_form_for_serializer(self, serializer):
        if hasattr(serializer, 'initial_data'):
            serializer.is_valid()

        form_renderer = self.form_renderer_class()
        return form_renderer.render(
            serializer.data,
            self.accepted_media_type,
            {'style': {'template_pack': 'dynamic_rest/horizontal'}}
        )


class DynamicHTMLFormRenderer(HTMLFormRenderer):
    template_pack = 'rest_framework/vertical'


DynamicHTMLFormRenderer.default_style = ClassLookupDict(
    copy(DynamicHTMLFormRenderer.default_style.mapping)
)
DynamicHTMLFormRenderer.default_style[DynamicRelationField] = {
    'base_template': 'select2.html'
}


class DynamicAdminRenderer(AdminRenderer):
    """Admin renderer."""
    form_renderer_class = DynamicHTMLFormRenderer
    template = 'dynamic_rest/admin.html'
    COLUMN_BLACKLIST = ('id', 'links')

    def get_breadcrumbs(self, request, view=None):
        return get_breadcrumbs(request.path, view=view)

    def get_context(self, data, media_type, context):
        def process(result):
            if result.get('links', {}).get('self'):
                result['url'] = result['links']['self']
        view = context.get('view')
        request = context.get('request')
        response = context.get('response')

        if view and view.__class__.__name__ == 'API':
            # root view
            is_root = True
        else:
            # data view
            is_root = False
            if response.status_code < 400:
                # remove envelope for successful responses
                data = unpack(data)

        context = super(DynamicAdminRenderer, self).get_context(
            data,
            media_type,
            context
        )

        # modify context
        context['breadcrumblist'] = self.get_breadcrumbs(
            request,
            view=view
        )

        if is_root:
            context['style'] = 'root'

        # to account for the DREST envelope
        # (data is stored one level deeper than expected in the response)
        results = context.get('results')
        if results:
            if isinstance(results, list):
                for result in results:
                    process(result)
            else:
                process(results)

        columns = context['columns']
        if hasattr(view, 'serializer_class'):
            fields = view.serializer_class.Meta.fields
            if not isinstance(fields, six.string_types):
                # respect serializer field ordering
                columns = [
                    f for f in fields if f in columns
                ]

        # remove blacklisted columns
        context['columns'] = [
            c for c in columns if c not in self.COLUMN_BLACKLIST
        ]
        context['details'] = context['columns']
        context['error_form'] = context['error_form']
        if context['error_form']:
            context['errors'] = context['response'].data.get('errors')

        # hide/display sidebar options
        allowed_methods = set(
            (x.lower() for x in (view.http_method_names or ()))
        )
        context['show_sidebar'] = True
        context['allow_filter'] = False
        context['allow_delete'] = 'delete' in allowed_methods
        context['allow_edit'] = 'put' in allowed_methods
        context['allow_create'] = 'post' in allowed_methods
        context['allow_import'] = 'post' in allowed_methods
        return context

    def render_form_for_serializer(self, serializer):
        serializer.disable_envelope()
        if hasattr(serializer, 'initial_data'):
            serializer.is_valid()

        form_renderer = self.form_renderer_class()
        return form_renderer.render(
            serializer.data,
            self.accepted_media_type,
            {'style': {'template_pack': 'dynamic_rest/horizontal'}}
        )
