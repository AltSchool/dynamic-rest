from django.conf.urls import include, patterns, url

from dynamic_rest.routers import DynamicRouter
from tests import viewsets

router = DynamicRouter()
router.register(r'users', viewsets.UserViewSet)
router.register(r'groups', viewsets.GroupViewSet)
router.register(r'profiles', viewsets.ProfileViewSet)
router.register(r'locations', viewsets.LocationViewSet)

router.register(r'cats', viewsets.CatViewSet)
router.register(r'dogs', viewsets.DogViewSet)
router.register(r'horses', viewsets.HorseViewSet)
router.register(r'zebras', viewsets.ZebraViewSet)
router.register(r'user_locations', viewsets.UserLocationViewSet)

# the above routes are duplicated to test versioned prefixes
router.register(r'v2/cats', viewsets.CatViewSet)
router.register(r'v1/user_locations', viewsets.UserLocationViewSet)

urlpatterns = patterns(
    '',
    url(r'^', include(router.urls))
)
