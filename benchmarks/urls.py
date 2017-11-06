from django.conf.urls import include, url

from .drest import router as drest_router
from .drf import router as drf_router

urlpatterns = [
    url(r'^', include(drf_router.urls)),
    url(r'^', include(drest_router.urls)),
]
