"""This module contains custom renderer classes."""
from django.utils import six
import copy
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

from dynamic_rest.compat import reverse, NoReverseMatch
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
    template_pack = 'dynamic_rest/horizontal'


DynamicHTMLFormRenderer.default_style = ClassLookupDict(
    copy.deepcopy(DynamicHTMLFormRenderer.default_style.mapping)
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

    def get_context(self, data, media_type, context):
        view = context.get('view')
        response = context.get('response')
        request = context.get('request')
        is_error = response.status_code > 399
        is_auth_error = response.status_code in (401, 403)
        user = request.user if request else None
        referer = request.META.get('HTTP_REFERER') if request else None

        # remove envelope for successful responses
        if getattr(data, 'serializer', None):
            serializer = data.serializer
            if hasattr(serializer, 'disable_envelope'):
                serializer.disable_envelope()
            data = serializer.data

        context = super(DynamicAdminRenderer, self).get_context(
            data,
            media_type,
            context
        )

        # add context
        name_field = None
        meta = None
        is_update = getattr(view, 'is_update', lambda: False)()
        is_root = view and view.__class__.__name__ == 'API'
        header = ''
        header_url = '#'
        description = ''

        style = context['style']
        # to account for the DREST envelope
        # (data is stored one level deeper than expected in the response)
        results = context.get('results')
        paginator = context.get('paginator')
        columns = context['columns']
        serializer = getattr(results, 'serializer', None)
        instance = serializer.instance if serializer else None
        if isinstance(instance, list):
            instance = None

        def process(result):
            if result.get('links', {}).get('self'):
                url = result['url'] = result['links']['self']
                parts = url.split('/')
                pk = parts[-1] if parts[-1] else parts[-2]
                result['pk'] = pk

        if results:
            if isinstance(results, list):
                for result in results:
                    process(result)
            else:
                process(results)

        if is_root:
            style = context['style'] = 'root'
            header = settings.API_NAME or ''
            description = settings.API_DESCRIPTION
            header_url = '/'

        back_url = None
        back = None
        root_url = settings.API_ROOT_URL

        if serializer:
            meta = serializer.get_meta()
            search_key = serializer.get_search_key()
            search_help = getattr(meta, 'search_help', None)
            singular_name = serializer.get_name().title()
            plural_name = serializer.get_plural_name().title()
            description = serializer.get_description()
            header = serializer.get_plural_name().title()
            name_field = serializer.get_name_field()

            if style == 'list':
                if paginator:
                    paging = paginator.get_page_metadata()
                    count = paging['total_results']
                else:
                    count = len(results)
                header = '%d %s' % (count, header)
            elif not is_error:
                back_url = serializer.get_url()
                back = plural_name
                header = results.get(name_field)
                header_url = serializer.get_url(
                    pk=instance.pk
                )

            if style == 'list':
                list_fields = getattr(meta, 'list_fields', None) or meta.fields
            else:
                list_fields = meta.fields
            blacklist = ('id', )
            if not isinstance(list_fields, six.string_types):
                # respect serializer field ordering
                columns = [
                    f for f in list_fields
                    if f in columns and f not in blacklist
                ]

            fields = serializer.get_all_fields()
        else:
            fields = {}
            search_key = search_help = None
            singular_name = plural_name = ''

        # search value
        search_value = (
            request.query_params.get(search_key, '')
            if search_key else ''
        )

        # link field
        link_field = name_field
        if (
            columns and not link_field or
            (columns and link_field not in columns)
        ):
            link_field = columns[0]

        # login and logout
        login_url = ''
        try:
            login_url = settings.ADMIN_LOGIN_URL or reverse(
                'dynamic_rest:login'
            )
        except NoReverseMatch:
            try:
                login_url = (
                    settings.ADMIN_LOGIN_URL or reverse('rest_framework:login')
                )
            except NoReverseMatch:
                pass

        logout_url = ''
        try:
            logout_url = (
                settings.ADMIN_LOGOUT_URL or reverse('dynamic_rest:logout')
            )
        except NoReverseMatch:
            try:
                logout_url = (
                    settings.ADMIN_LOGOUT_URL or reverse('dynamic_rest:logout')
                )
            except NoReverseMatch:
                pass

        # alerts
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

        # methods
        allowed_methods = set(
            (x.lower() for x in (view.http_method_names or ()))
        )

        context['root_url'] = root_url
        context['back_url'] = back_url
        context['back'] = back
        context['link_field'] = link_field
        context['columns'] = columns
        context['fields'] = fields
        context['details'] = context['columns']
        context['description'] = description
        context['singular_name'] = singular_name
        context['plural_name'] = plural_name
        context['is_auth_error'] = is_auth_error
        context['login_url'] = login_url
        context['logout_url'] = logout_url
        context['header'] = header
        context['header_url'] = header_url
        context['search_value'] = search_value
        context['search_key'] = search_key
        context['search_help'] = search_help
        context['allow_filter'] = (
            'get' in allowed_methods and style == 'list'
        ) and search_key
        context['allow_delete'] = (
            'delete' in allowed_methods and style == 'detail'
            and bool(instance)
        )
        context['allow_edit'] = (
            'put' in allowed_methods and
            style == 'detail' and
            bool(instance)
        )
        context['allow_create'] = (
            'post' in allowed_methods and style == 'list'
        )
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
        # add redirects for successful creates and deletes
        renderer_context = renderer_context or {}
        response = renderer_context.get('response')
        serializer = getattr(data, 'serializer', None)
        # Creation and deletion should use redirects in the admin style.
        location = None

        did_create = response and response.status_code == 201
        did_delete = response and response.status_code == 204

        if (
            did_create
            and serializer
        ):
            location = '%s?alert=Created+successfully&alert-class=success' % (
                serializer.get_url(pk=serializer.instance.pk)
            )

        result = super(DynamicAdminRenderer, self).render(
            data,
            accepted_media_type,
            renderer_context
        )

        if did_delete:
            location = (
                response['Location'] +
                '?alert=Deleted+successfully&alert-class=success'
            )

        if response and location:
            response['Location'] = location
        return result
