"""URLs for the benchmarks app."""
from django.urls import include, path

from benchmarks_app.drest import router as drest_router
from benchmarks_app.drf import router as drf_router

urlpatterns = [
    path("", include(drf_router.urls)),
    path("", include(drest_router.urls)),
]
