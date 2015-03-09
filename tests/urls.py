from django.conf.urls import patterns, include, url
from rest_framework import routers
from tests import viewsets

router = routers.DefaultRouter()
router.register(r'users', viewsets.UserViewSet)

urlpatterns = patterns('',
    url(r'^', include(router.urls))
)
