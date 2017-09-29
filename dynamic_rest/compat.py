# flake8: noqa
from __future__ import absolute_import

from django.utils import six
from django import VERSION

DJANGO110 = VERSION >= (1, 10)
try:
    from django.urls import (
        NoReverseMatch,
        RegexURLPattern,
        RegexURLResolver,
        ResolverMatch,
        Resolver404,
        get_script_prefix,
        reverse,
        reverse_lazy,
        resolve
    )
except ImportError:
    from django.core.urlresolvers import (  # Will be removed in Django 2.0
        NoReverseMatch,
        RegexURLPattern,
        RegexURLResolver,
        ResolverMatch,
        Resolver404,
        get_script_prefix,
        reverse,
        reverse_lazy,
        resolve
    )


def set_many(instance, field, value):
    if DJANGO110:
        field = getattr(instance, field)
        field.set(value)
    else:
        setattr(instance, field, value)


try:
    from rest_framework.relations import Hyperlink
except ImportError:
    class Hyperlink(six.text_type):
        """
        A string like object that additionally has an associated name.
        We use this for hyperlinked URLs that may render as a named link
        in some contexts, or render as a plain URL in others.

        Taken from DRF 3.2, used for compatability with DRF 3.1.
        TODO(compat): remove when we drop compat for DRF 3.1.
        """
        def __new__(self, url, obj):
            ret = six.text_type.__new__(self, url)
            ret.obj = obj
            return ret

        def __getnewargs__(self):
            return(str(self), self.name,)

        @property
        def name(self):
            # This ensures that we only called `__str__` lazily,
            # as in some cases calling __str__ on a model instances *might*
            # involve a database lookup.
            return six.text_type(self.obj)

        is_hyperlink = True

try:
    from rest_framework.renderers import AdminRenderer
except ImportError:
    from django.template import RequestContext, loader
    from rest_framework.request import override_method
    from rest_framework.renderers import BrowsableAPIRenderer

    class AdminRenderer(BrowsableAPIRenderer):
        template = 'rest_framework/admin.html'
        format = 'admin'

        def render(self, data, accepted_media_type=None, renderer_context=None):
            self.accepted_media_type = accepted_media_type or ''
            self.renderer_context = renderer_context or {}

            response = renderer_context['response']
            request = renderer_context['request']
            view = self.renderer_context['view']

            if response.status_code == 400:
                # Errors still need to display the list or detail information.
                # The only way we can get at that is to simulate a GET request.
                self.error_form = self.get_rendered_html_form(data, view, request.method, request)
                self.error_title = {'POST': 'Create', 'PUT': 'Edit'}.get(request.method, 'Errors')

                with override_method(view, request, 'GET') as request:
                    response = view.get(request, *view.args, **view.kwargs)
                data = response.data

            template = loader.get_template(self.template)
            context = self.get_context(data, accepted_media_type, renderer_context)
            context = RequestContext(renderer_context['request'], context)
            ret = template.render(context)

            # Creation and deletion should use redirects in the admin style.
            if (response.status_code == 201) and ('Location' in response):
                response.status_code = 302
                response['Location'] = request.build_absolute_uri()
                ret = ''

            if response.status_code == 204:
                response.status_code = 302
                try:
                    # Attempt to get the parent breadcrumb URL.
                    response['Location'] = self.get_breadcrumbs(request)[-2][1]
                except KeyError:
                    # Otherwise reload current URL to get a 'Not Found' page.
                    response['Location'] = request.full_path
                ret = ''

            return ret

        def get_context(self, data, accepted_media_type, renderer_context):
            """
            Render the HTML for the browsable API representation.
            """
            context = super(AdminRenderer, self).get_context(
                data, accepted_media_type, renderer_context
            )

            paginator = getattr(context['view'], 'paginator', None)
            if (paginator is not None and data is not None):
                try:
                    results = paginator.get_results(data)
                except KeyError:
                    results = data
            else:
                results = data

            if results is None:
                header = {}
                style = 'detail'
            elif isinstance(results, list):
                header = results[0] if results else {}
                style = 'list'
            else:
                header = results
                style = 'detail'

            columns = [key for key in header.keys() if key != 'url']
            details = [key for key in header.keys() if key != 'url']

            context['style'] = style
            context['columns'] = columns
            context['details'] = details
            context['results'] = results
            context['error_form'] = getattr(self, 'error_form', None)
            context['error_title'] = getattr(self, 'error_title', None)
            return context
