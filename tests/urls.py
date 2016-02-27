from django.conf.urls import include, patterns, url

from dynamic_rest.routers import DynamicRouter
from tests import viewsets

router = DynamicRouter()
router.register_resource(viewsets.UserViewSet)
router.register_resource(viewsets.GroupViewSet)
router.register_resource(viewsets.ProfileViewSet)
router.register_resource(viewsets.LocationViewSet)

router.register_resource(viewsets.CatViewSet)
router.register_resource(viewsets.DogViewSet)
router.register_resource(viewsets.HorseViewSet)
router.register_resource(viewsets.ZebraViewSet)
router.register_resource(viewsets.UserLocationViewSet)

# the above routes are duplicated to test versioned prefixes
router.register(r'v2/cats', viewsets.CatViewSet)
router.register(r'v1/user_locations', viewsets.UserLocationViewSet)

urlpatterns = patterns(
    '',
    url(r'^', include(router.urls))
)
