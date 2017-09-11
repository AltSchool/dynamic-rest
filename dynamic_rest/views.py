from __future__ import absolute_import
from django.contrib.auth import views
from dynamic_rest.conf import settings


def login(request):
    template_name = settings.LOGIN_TEMPLATE
    print template_name
    return views.login(request, template_name=template_name)


def logout(request):
    return views.logout(request)
