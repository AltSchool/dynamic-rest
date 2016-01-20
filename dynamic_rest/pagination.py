"""This module contains custom pagination classes."""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.settings import api_settings

from dynamic_rest.conf import settings


class DynamicPageNumberPagination(PageNumberPagination):
    """A subclass of PageNumberPagination.

    Adds support for pagination metadata and overrides for
    pagination query parameters.
    """
    page_size_query_param = settings.PAGE_SIZE_QUERY_PARAM
    page_query_param = settings.PAGE_QUERY_PARAM
    max_page_size = settings.MAX_PAGE_SIZE
    page_size = settings.PAGE_SIZE or api_settings.PAGE_SIZE

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
