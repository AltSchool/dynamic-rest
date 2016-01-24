from django.conf.urls import patterns, url, include
from .drest import router as drest_router
from .drf import router as drf_router

urlpatterns = patterns(
    '',
    url(r'^', include(drf_router.urls)),
    url(r'^', include(drest_router.urls)),
)
