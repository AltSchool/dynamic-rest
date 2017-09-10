"""This module contains custom renderer classes."""
from django.utils import six
from copy import copy
from rest_framework.renderers import (
    BrowsableAPIRenderer,
    HTMLFormRenderer,
    ClassLookupDict
)
from rest_framework.compat import reverse, NoReverseMatch
try:
    from rest_framework.renderers import AdminRenderer
except:
    # DRF < 3.3
    class AdminRenderer(BrowsableAPIRenderer):
        format = 'admin'

from dynamic_rest.utils import unpack, get_breadcrumbs
from dynamic_rest.conf import settings
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
    'base_template': 'relation.html'
}


class DynamicAdminRenderer(AdminRenderer):
    """Admin renderer."""
    form_renderer_class = DynamicHTMLFormRenderer
    template = 'dynamic_rest/admin.html'

    def get_breadcrumbs(self, request, view=None):
        return get_breadcrumbs(request.path, view=view)

    def get_context(self, data, media_type, context):
        def process(result):
            if result.get('links', {}).get('self'):
                result['url'] = result['links']['self']
            result.pop('links', None)

        view = context.get('view')
        response = context.get('response')
        request = context.get('request')

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

        # add context

        header = ''
        header_url = '#'
        if is_root:
            context['style'] = 'root'
            header = settings.ROOT_VIEW_NAME or ''
            header_url = '/'

        style = context['style']

        # to account for the DREST envelope
        # (data is stored one level deeper than expected in the response)
        results = context.get('results')
        serializer = getattr(results, 'serializer', None)
        if results:
            if isinstance(results, list):
                for result in results:
                    process(result)
            else:
                process(results)

        columns = context['columns']
        link_field = None
        paginator = context.get('paginator')
        serializer_class = None
        meta = None
        if hasattr(view, 'serializer_class'):
            serializer_class = view.serializer_class
            header = serializer_class.get_plural_name().title()
            if style == 'list':
                if paginator:
                    paging = paginator.get_page_metadata()
                    count = paging['total_results']
                else:
                    count = len(results)
                header = '%d %s' % (count, header)
            else:
                header = getattr(
                    serializer.instance,
                    serializer.get_natural_key()
                )
                header_url = serializer.get_url(
                    pk=serializer.instance.pk
                )
            meta = serializer_class.Meta
            if style == 'list':
                fields = getattr(meta, 'list_fields', None) or meta.fields
            else:
                fields = meta.fields
            blacklist = ('id', )
            if not isinstance(fields, six.string_types):
                # respect serializer field ordering
                columns = [
                    f for f in fields
                    if f in columns and f not in blacklist
                ]

        search_key = getattr(
            meta,
            'search_key',
            None
        ) or None
        search_value = (
            request.query_params.get(search_key, '')
            if search_key else ''
        )
        # columns
        context['columns'] = columns

        # link_field - the field to add the row hyperlink onto
        # defaults to first visible column
        if not link_field and columns:
            link_field = columns[0]
        context['link_field'] = link_field

        login_url = ''
        try:
            login_url = settings.LOGIN_URL or reverse('dynamic_rest:login')
        except NoReverseMatch:
            try:
                login_url = (
                    settings.LOGIN_URL or reverse('rest_framework:login')
                )
            except NoReverseMatch:
                pass
        context['login_url'] = login_url

        logout_url = ''
        try:
            logout_url = (
                settings.LOGOUT_URL or reverse('dynamic_rest:logout')
            )
        except NoReverseMatch:
            try:
                logout_url = (
                    settings.LOGOUT_URL or reverse('dynamic_rest:logout')
                )
            except NoReverseMatch:
                pass
        context['logout_url'] = logout_url

        context['header'] = header
        context['header_url'] = header_url
        context['details'] = context['columns']
        allowed_methods = set(
            (x.lower() for x in (view.http_method_names or ()))
        )
        context['search_value'] = search_value
        context['search_key'] = search_key
        context['allow_filter'] = (
            'get' in allowed_methods and style == 'list'
        ) and search_key
        context['allow_delete'] = (
            'delete' in allowed_methods and style == 'detail'
        )
        context['allow_edit'] = (
            'put' in allowed_methods and style == 'detail'
        )
        context['allow_create'] = (
            'post' in allowed_methods and style == 'list'
        )
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
