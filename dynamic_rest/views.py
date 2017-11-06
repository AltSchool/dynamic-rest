from __future__ import absolute_import
from django.contrib.auth import views
from dynamic_rest.conf import settings


def login(request):
    template_name = settings.ADMIN_LOGIN_TEMPLATE
    return views.login(request, template_name=template_name)


def logout(request):
    return views.logout(request)
