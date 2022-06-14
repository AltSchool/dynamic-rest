# adapter from Django's django.core.paginator
# adds support for the "exclude_count" parameter

from math import ceil

from django.utils.functional import cached_property
from django.core.paginator import Paginator

try:
    from django.utils.translation import gettext_lazy as _
except ImportError:
    def _(x):
        return x



class InvalidPage(Exception):
    pass


class PageNotAnInteger(InvalidPage):
    pass


class EmptyPage(InvalidPage):
    pass


class DynamicPaginator(Paginator):

    def __init__(self, object_list, per_page, orphans=0,
                 allow_empty_first_page=True, exclude_count=False):
        self.object_list = object_list
        self._check_object_list_is_ordered()
        self.per_page = int(per_page)
        self.orphans = int(orphans)
        self.allow_empty_first_page = allow_empty_first_page
        self.exclude_count = exclude_count

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
            # always fetch one extra item to determine if more pages are available
            top = top + 1
        else:
            # skip validating against count
            if top + self.orphans >= self.count:
                top = self.count
        return self._get_page(self.object_list[bottom:top], number, self)

    @cached_property
    def count(self):
        """Return the total number of objects, across all pages."""
        if self.exclude_count:
            # always return 0, count should not be called
            return 0

        try:
            return self.object_list.count()
        except (AttributeError, TypeError):
            # AttributeError if object_list has no count() method.
            # TypeError if object_list.count() requires arguments
            # (i.e. is of type list).
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
