"""This module contains custom renderer classes."""
from django.utils import six
import copy
from rest_framework.renderers import (
    HTMLFormRenderer,
    ClassLookupDict
)
from django.utils.safestring import mark_safe
from dynamic_rest.compat import reverse, NoReverseMatch, AdminRenderer
from dynamic_rest.conf import settings
from dynamic_rest import fields


DynamicRelationField = fields.DynamicRelationField

mapping = copy.deepcopy(HTMLFormRenderer.default_style.mapping)
mapping[DynamicRelationField] = {
    'base_template': 'relation.html'
}
mapping[fields.DynamicListField] = {
    'base_template': 'list.html'
}


class DynamicHTMLFormRenderer(HTMLFormRenderer):
    template_pack = 'dynamic_rest/horizontal'
    default_style = ClassLookupDict(mapping)

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Render serializer data and return an HTML form, as a string.
        """
        if renderer_context:
            style = renderer_context.get('style', {})
            style['template_pack'] = self.template_pack
        return super(DynamicHTMLFormRenderer, self).render(
            data,
            accepted_media_type,
            renderer_context
        )


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
        meta = None
        is_update = getattr(view, 'is_update', lambda: False)()
        is_directory = view and view.__class__.__name__ == 'API'
        header = ''
        title = settings.API_NAME or ''
        description = ''

        results = context.get('results')

        style = context.get('style')
        paginator = context.get('paginator')
        columns = context.get('columns')
        serializer = getattr(results, 'serializer', None)
        instance = serializer.instance if serializer else None
        if isinstance(instance, list):
            instance = None

        if is_directory:
            style = context['style'] = 'directory'
            title = header = settings.API_NAME or ''
            description = settings.API_DESCRIPTION

        back_url = None
        back = None
        filters = {}
        create_related_forms = {}

        instance_name = None

        if serializer:
            if instance:
                try:
                    name_field_name = serializer.get_name_field()
                    name_field = serializer.get_field(name_field_name)
                    name_source = name_field.source or name_field_name
                    instance_name = getattr(
                        instance, name_source, str(instance.pk)
                    )
                except:
                    instance_name = None
                for related_name, field in serializer.get_link_fields(
                ).items():
                    inverse_field_name = field.get_inverse_field_name()
                    related_serializer = field.get_serializer(
                        request_fields=None,
                        exclude_fields=[inverse_field_name]
                    )
                    related_serializer.set_request_method('POST')
                    has_permission = (
                        not getattr(related_serializer, 'permissions', None) or
                        related_serializer.permissions.create
                    )
                    can_add_more = field.many or not results.get(related_name)
                    has_source = field.source != '*'
                    if (
                        has_source and
                        can_add_more and
                        bool(inverse_field_name) and
                        has_permission
                    ):
                        create_related_forms[related_name] = (
                            related_serializer,
                            self.render_form_for_serializer(
                                related_serializer
                            )
                        )

            filters = serializer.get_filters()
            meta = serializer.get_meta()
            singular_name = serializer.get_name().title()
            plural_name = serializer.get_plural_name().title()
            description = serializer.get_description()
            icon = serializer.get_icon()
            header = serializer.get_plural_name().title().replace('_', ' ')

            if style == 'list':
                if paginator:
                    paging = paginator.get_page_metadata()
                    count = paging['total_results']
                else:
                    count = len(results)
                header = '%d %s' % (count, header)
            elif not is_error:
                back_url = serializer.get_url()
                back = 'List'
                header = serializer.get_name().title().replace('_', ' ')

            title = header
            if icon:
                header = mark_safe('<span class="fa fa-%s"></span>&nbsp;%s' % (
                    icon,
                    header
                ))

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
            singular_name = plural_name = ''

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
            error = response.data
            if isinstance(error, dict):
                if len(error.keys()) == 1:
                    error = error[error.keys()[0]]
                else:
                    error = ' '.join((
                        "%s=%s" % (str(k), str(v)) for k, v in error.items()
                    ))
            alert = 'An error has occurred: %s' % error
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

        #
        permissions = getattr(view, 'permissions', None)
        allowed_methods = set(
            (x.lower() for x in (view.http_method_names or ()))
        )
        if permissions:
            if not permissions.delete:
                allowed_methods.discard('delete')
            if not permissions.update:
                allowed_methods.discard('patch')
                allowed_methods.discard('put')
            if not permissions.create:
                allowed_methods.discard('post')
            if not permissions.list:
                back = None

        from dynamic_rest.routers import get_directory
        context['instance_name'] = instance_name
        context['directory'] = get_directory(request, icons=True)
        context['filters'] = filters
        context['num_filters'] = sum([
            1 if (
                any([ff is not None for ff in f.value])
                if isinstance(f.value, list)
                else f.value is not None
            ) else 0
            for f in filters.values()
        ])
        context['back_url'] = back_url
        context['back'] = back
        context['columns'] = columns
        context['fields'] = fields
        context['serializer'] = serializer
        context['sortable_fields'] = set([
            c for c in columns if (
                getattr(fields.get(c), 'model_field', None)
                and not isinstance(fields.get(c), DynamicRelationField)
            )
        ])
        sorted_ascending = None
        if hasattr(view, 'get_request_feature'):
            sorted_field = view.get_request_feature(view.SORT)
            sorted_field = sorted_field[0] if sorted_field else None
            if sorted_field:
                if sorted_field.startswith('-'):
                    sorted_field = sorted_field[1:]
                    sorted_ascending = False
                else:
                    sorted_ascending = True
        else:
            sorted_field = None

        context['create_related_forms'] = create_related_forms
        context['sorted_field'] = sorted_field
        context['sorted_ascending'] = sorted_ascending
        context['details'] = context['columns']
        context['is_error'] = is_error
        context['description'] = description
        context['singular_name'] = singular_name
        context['plural_name'] = plural_name
        context['is_auth_error'] = is_auth_error
        context['login_url'] = login_url
        context['logout_url'] = logout_url
        context['header'] = header
        context['title'] = title
        context['api_name'] = settings.API_NAME
        context['url'] = request.get_full_path()
        context['allow_filter'] = (
            'get' in allowed_methods and style == 'list'
        ) and bool(filters)
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
                response.get('Location', '/') +
                '?alert=Deleted+successfully&alert-class=success'
            )

        if response and location:
            response['Location'] = location
        return result
