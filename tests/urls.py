from django.conf.urls import patterns, include, url
from dynamic_rest.routers import DynamicRouter
from tests import viewsets

router = DynamicRouter()
router.register(r'users', viewsets.UserViewSet)
router.register(r'groups', viewsets.GroupViewSet)
router.register(r'profiles', viewsets.ProfileViewSet)
router.register(r'locations', viewsets.LocationViewSet)
router.register(r'cats', viewsets.CatViewSet)
router.register(r'user_locations', viewsets.UserLocationViewSet, base_name='user_locations')

urlpatterns = patterns(
    '',
    url(r'^', include(router.urls))
)
