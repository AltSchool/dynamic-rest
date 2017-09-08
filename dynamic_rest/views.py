from __future__ import absolute_import
from django.contrib.auth import views


def login(request):
    return views.login(request, template_name='dynamic_rest/login.html')


def logout(request):
    return views.logout(request)
