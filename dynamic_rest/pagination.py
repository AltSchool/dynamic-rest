from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.conf import settings

dynamic_settings = getattr(settings, 'DYNAMIC_REST', {})
drf_settings = getattr(settings, 'REST_FRAMEWORK', {})


class DynamicPageNumberPagination(PageNumberPagination):
    page_size_query_param = dynamic_settings.get(
        'PAGE_SIZE_QUERY_PARAM',
        'per_page')
    page_query_param = dynamic_settings.get('PAGE_QUERY_PARAM', 'page')
    max_page_size = dynamic_settings.get('MAX_PAGE_SIZE', None)
    page_size = dynamic_settings.get(
        'PAGE_SIZE', drf_settings.get('PAGE_SIZE'))

    def get_page_metadata(self):
        # returns total_results, total_pages, page, per_page
        return {
            'total_results': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'page': self.page.number,
            'per_page': self.get_page_size(self.request)
        }

    def get_paginated_response(self, data):
        meta = self.get_page_metadata()
        if 'meta' in data:
            data['meta'].update(meta)
        else:
            data['meta'] = meta
        return Response(data)
