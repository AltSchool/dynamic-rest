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
from dynamic_rest import fields


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
DynamicHTMLFormRenderer.default_style[fields.DynamicRelationField] = {
    'base_template': 'relation.html'
}
DynamicHTMLFormRenderer.default_style[fields.DynamicListField] = {
    'base_template': 'list.html'
}


class DynamicAdminRenderer(AdminRenderer):
    """Admin renderer."""
    form_renderer_class = DynamicHTMLFormRenderer
    template = settings.ADMIN_TEMPLATE

    def get_breadcrumbs(self, request, view=None):
        return get_breadcrumbs(request.path, view=view)

    def get_context(self, data, media_type, context):
        def process(result):
            if result.get('links', {}).get('self'):
                result['url'] = result['links']['self']
            result.pop('links', None)

        view = context.get('view')
        response = context.get('response')
        is_error = response.status_code > 399
        is_auth_error = response.status_code in (401, 403)
        request = context.get('request')
        user = request.user if request else None
        referer = request.META.get('HTTP_REFERER') if request else None

        if view and view.__class__.__name__ == 'API':
            # root view
            is_root = True
        else:
            # data view
            is_root = False
            # remove envelope for successful responses
            if getattr(data, 'serializer', None):
                data = unpack(data)

        context = super(DynamicAdminRenderer, self).get_context(
            data,
            media_type,
            context
        )

        context['is_auth_error'] = is_auth_error

        # add context

        header = ''
        header_url = '#'
        description = ''
        if is_root:
            context['style'] = 'root'
            header = settings.ROOT_VIEW_NAME or ''
            description = settings.ROOT_DESCRIPTION
            header_url = '/'

        style = context['style']

        # to account for the DREST envelope
        # (data is stored one level deeper than expected in the response)
        results = context.get('results')
        serializer = getattr(results, 'serializer', None)
        natural_key = serializer.get_natural_key() if serializer else None
        instance = serializer.instance if serializer else None

        if serializer:
            singular_name = serializer.get_name().title()
            plural_name = serializer.get_plural_name().title()
            description = serializer.get_description()
        else:
            singular_name = plural_name = ''

        context['singular_name'] = singular_name
        context['plural_name'] = plural_name
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
        is_update = getattr(view, 'is_update', lambda: False)()

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
            elif not is_error:
                header = getattr(
                    instance,
                    natural_key,
                    header
                )
                header_url = serializer.get_url(
                    pk=instance.pk
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

        context['description'] = description
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
            'put' in allowed_methods and
            style == 'detail' and
            bool(instance)
        )
        context['allow_create'] = (
            'post' in allowed_methods and style == 'list'
        )
        alert = request.query_params.get('alert', None)
        alert_class = request.query_params.get('alert-class', None)
        if is_error:
            alert = 'An error has occurred'
            alert_class = 'danger'
        elif is_update:
            alert = 'Saved successfully'
            alert_class = 'success'
        elif (
            login_url and user and
            referer and login_url in referer
        ):
            alert = 'Welcome back'
            name = getattr(user, 'name', None)
            if name:
                alert += ', %s!' % name
            else:
                alert += '!'
            alert_class = 'success'
        if alert and not alert_class:
            alert_class = 'info'

        context['alert'] = alert
        context['alert_class'] = alert_class
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

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get('response')
        serializer = getattr(data, 'serializer', None)
        # Creation and deletion should use redirects in the admin style.
        location = None
        if (
            response and response.status_code == 201
            and serializer and serializer.instance
        ):
            location = serializer.get_url(
                pk=serializer.instance.pk
            )
            location = '%s?alert=Created+successfully&alert-class=success' % (
                location,
            )
        result = super(DynamicAdminRenderer, self).render(
            data,
            accepted_media_type,
            renderer_context
        )
        if response and location:
            response['Location'] = location
        return result
