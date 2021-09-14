from django.conf.urls import include, path

from .drest import router as drest_router
from .drf import router as drf_router

urlpatterns = [
    path(r'^', include(drf_router.urls)),
    path(r'^', include(drest_router.urls)),
]
