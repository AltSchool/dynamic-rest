from django.urls import include, path

from .drest import router as drest_router
from .drf import router as drf_router

urlpatterns = [
    path('', include(drf_router.urls)),
    path('', include(drest_router.urls)),
]
