from rest_framework.pagination import PageNumberPagination
from django.conf import settings

dynamic_settings = getattr(settings, 'DYNAMIC_REST', {})
class DynamicPageNumberPagination(PageNumberPagination):
  page_size_query_param = dynamic_settings.get('PAGE_SIZE_QUERY_PARAM')
  page_query_param = dynamic_settings.get('PAGE_QUERY_PARAM', 'page')
  max_page_size = dynamic_settings.get('MAX_PAGE_SIZE', None)
  def paginate_queryset(self, queryset, request, view=None):

