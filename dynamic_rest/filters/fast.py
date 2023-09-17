"""Fast Filter Backend."""
from django.db.models import Model, QuerySet

from dynamic_rest.filters.base import DynamicFilterBackend
from dynamic_rest.prefetch import FastPrefetch, FastQuery
from dynamic_rest.serializers import DynamicModelSerializer


class FastDynamicFilterBackend(DynamicFilterBackend):
    """A DRF filter backend that constructs DREST querysets."""

    def _create_prefetch(self, source: str, queryset: QuerySet) -> FastPrefetch:
        """Create a Prefetch object."""
        return FastPrefetch(source, queryset=queryset)

    def _get_queryset(
        self, queryset: QuerySet = None, serializer: DynamicModelSerializer = None
    ) -> FastQuery:
        """Get the base queryset for this request."""
        queryset = super()._get_queryset(queryset=queryset, serializer=serializer)

        if not isinstance(queryset, FastQuery):
            queryset = FastQuery(queryset)

        return queryset

    def _make_model_queryset(self, model: Model) -> FastQuery:
        """Make a queryset for a model."""
        queryset = super()._make_model_queryset(model)
        return FastQuery(queryset)

    def _serializer_filter(
        self, serializer: DynamicModelSerializer, queryset: QuerySet
    ) -> QuerySet:
        """Filter a queryset using a serializer's filter_queryset method."""
        queryset.queryset = serializer.filter_queryset(queryset.queryset)
        return queryset
