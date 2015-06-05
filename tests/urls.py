from django.conf.urls import patterns, include, url
from rest_framework import routers
from tests import viewsets

router = routers.DefaultRouter()
router.register(r'users', viewsets.UserViewSet)
router.register(r'groups', viewsets.GroupViewSet)
router.register(r'locations', viewsets.LocationViewSet)
router.register(r'user_locations', viewsets.UserLocationViewSet)

urlpatterns = patterns('',
                       url(r'^', include(router.urls))
                       )
