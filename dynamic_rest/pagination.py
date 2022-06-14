"""This module contains custom pagination classes."""
from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.exceptions import NotFound

from django.utils.functional import cached_property
from django.core.paginator import InvalidPage
from dynamic_rest.conf import settings
from dynamic_rest.paginator import DynamicPaginator


class DynamicPageNumberPagination(PageNumberPagination):
    """A subclass of PageNumberPagination.

    Adds support for pagination metadata and overrides for
    pagination query parameters.
    """

    page_size_query_param = settings.PAGE_SIZE_QUERY_PARAM
    exclude_count_query_param = settings.EXCLUDE_COUNT_QUERY_PARAM
    page_query_param = settings.PAGE_QUERY_PARAM
    max_page_size = settings.MAX_PAGE_SIZE
    page_size = settings.PAGE_SIZE or api_settings.PAGE_SIZE
    django_paginator_class = DynamicPaginator

    def get_page_metadata(self):
        # always returns page, per_page
        # also returns total_results and total_pages
        # (unless EXCLUDE_COUNT_QUERY_PARAM is set)
        meta = {
            'page': self.page.number,
            'per_page': self.get_page_size(self.request)
        }
        if not self.exclude_count:
            meta['total_results'] = self.page.paginator.count
            meta['total_pages'] = self.page.paginator.num_pages
        else:
            meta['more_pages'] = self.more_pages
        return meta

    def get_paginated_response(self, data):
        meta = self.get_page_metadata()
        result = None
        if isinstance(data, list):
            result = OrderedDict()
            if not self.exclude_count:
                result['count'] = self.page.paginator.count
                result['next'] = self.get_next_link()
                result['previous'] = self.get_previous_link()
            result['results'] = data
            result['meta'] = meta
        else:
            result = data
            if 'meta' in result:
                result['meta'].update(meta)
            else:
                result['meta'] = meta
        return Response(result)

    @cached_property
    def exclude_count(self):
        return self.request.query_params.get(self.exclude_count_query_param)

    def get_page_number(self, request, paginator):
        page_number = request.query_params.get(self.page_query_param, 1)
        if page_number in self.last_page_strings:
            page_number = paginator.num_pages
        return page_number

    def paginate_queryset(self, queryset, request, **other):
        """
        Paginate a queryset if required, either returning a
        page object, or `None` if pagination is not configured for this view.
        """
        if 'exclude_count' in self.__dict__:
            self.__dict__.pop('exclude_count')

        page_size = self.get_page_size(request)
        if not page_size:
            return None

        self.request = request
        paginator = self.django_paginator_class(
            queryset, page_size, exclude_count=self.exclude_count
        )
        page_number = self.get_page_number(request, paginator)

        try:
            self.page = paginator.page(page_number)
        except InvalidPage as exc:
            msg = self.invalid_page_message.format(
                page_number=page_number, message=str(exc)
            )
            raise NotFound(msg)

        if paginator.num_pages > 1 and self.template is not None:
            # The browsable API should display pagination controls.
            self.display_page_controls = True

        result = list(self.page)
        if self.exclude_count:
            if len(result) > page_size:
                # if exclude_count is set, we fetch one extra item
                result = result[:page_size]
                self.more_pages = True
            else:
                self.more_pages = False
        return result
