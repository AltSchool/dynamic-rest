# adapted from Django's django.core.paginator (2.2 - 3.2+ compatible)
# adds support for the "exclude_count" parameter

from math import ceil

import inspect
from django.utils.functional import cached_property
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.utils.inspect import method_has_no_args

try:
    from django.utils.translation import gettext_lazy as _
except ImportError:
    def _(x):
        return x


class DynamicPaginator(Paginator):

    def __init__(self, *args, **kwargs):
        self.exclude_count = kwargs.pop('exclude_count', False)
        super().__init__(*args, **kwargs)

    def validate_number(self, number):
        """Validate the given 1-based page number."""
        try:
            number = int(number)
        except (TypeError, ValueError):
            raise PageNotAnInteger(_('That page number is not an integer'))
        if number < 1:
            raise EmptyPage(_('That page number is less than 1'))
        if self.exclude_count:
            # skip validating against num_pages
            return number
        if number > self.num_pages:
            if number == 1 and self.allow_empty_first_page:
                pass
            else:
                raise EmptyPage(_('That page contains no results'))
        return number

    def page(self, number):
        """Return a Page object for the given 1-based page number."""
        number = self.validate_number(number)
        bottom = (number - 1) * self.per_page
        top = bottom + self.per_page
        if self.exclude_count:
            # always fetch one extra item
            # to determine if more pages are available
            # and skip validation against count
            top = top + 1
        else:
            if top + self.orphans >= self.count:
                top = self.count
        return self._get_page(self.object_list[bottom:top], number, self)

    @cached_property
    def count(self):
        """Return the total number of objects, across all pages."""
        if self.exclude_count:
            # always return 0, count should not be called
            return 0

        c = getattr(self.object_list, 'count', None)
        if callable(c) and not inspect.isbuiltin(c) and method_has_no_args(c):
            return c()
        return len(self.object_list)

    @cached_property
    def num_pages(self):
        """Return the total number of pages."""
        if self.exclude_count:
            # always return 1, count should not be called
            return 1

        if self.count == 0 and not self.allow_empty_first_page:
            return 0
        hits = max(1, self.count - self.orphans)
        return int(ceil(hits / float(self.per_page)))
