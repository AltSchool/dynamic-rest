"""Paginator that supports dynamic page sizes and excludes count queries."""
# adapted from Django's django.core.paginator (3.2+ compatible)
# adds support for the "exclude_count" parameter

import inspect
from math import ceil

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.utils.functional import cached_property
from django.utils.inspect import method_has_no_args
from django.utils.translation import gettext_lazy as _


class DynamicPaginator(Paginator):
    """A subclass of Paginator that supports dynamic page sizes."""

    def __init__(self, *args, **kwargs):
        """Initialise the DynamicPaginator."""
        self.exclude_count = kwargs.pop("exclude_count", False)
        super().__init__(*args, **kwargs)

    def validate_number(self, number):
        """Validate the given 1-based page number."""
        try:
            number = int(number)
        except (TypeError, ValueError) as exc:
            raise PageNotAnInteger(_("That page number is not an integer")) from exc
        if number < 1:
            raise EmptyPage(_("That page number is less than 1"))
        if self.exclude_count:
            # skip validating against num_pages
            return number
        if number > self.num_pages:
            if number != 1 or not self.allow_empty_first_page:
                raise EmptyPage(_("That page contains no results"))
        return number

    def page(self, number):
        """Return a Page object for the given 1-based page number."""
        number = self.validate_number(number)
        per_page = self.per_page
        count = self.count
        bottom = (number - 1) * per_page
        top = bottom + per_page
        if self.exclude_count:
            # always fetch one extra item
            # to determine if more pages are available
            # and skip validation against count
            top += 1
        elif top + self.orphans >= count:
            top = count
        return self._get_page(self.object_list[bottom:top], number, self)

    @cached_property
    def count(self):
        """Return the total number of objects, across all pages."""
        if self.exclude_count:
            # always return 0, count should not be called
            return 0

        c = getattr(self.object_list, "count", None)
        if callable(c) and not inspect.isbuiltin(c) and method_has_no_args(c):
            return c()
        return len(self.object_list)

    @cached_property
    def num_pages(self):
        """Return the total number of pages."""
        if self.exclude_count:
            # always return 1, count should not be called
            return 1
        count = self.count
        if count == 0 and not self.allow_empty_first_page:
            return 0
        hits = max(1, count - self.orphans)
        return int(ceil(hits / float(self.per_page)))
