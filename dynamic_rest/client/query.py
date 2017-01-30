from copy import copy
from dynamic_rest.utils import unpack
from six import string_types


class DRESTQuery(object):

    def __init__(
        self,
        resource=None,
        filters=None,
        orders=None,
        includes=None,
        excludes=None,
        extras=None
    ):
        self.resource = resource
        self.filters = filters or {}
        self.includes = includes or []
        self.excludes = excludes or []
        self.orders = orders or []
        self.extras = extras or {}
        # disable sideloading for easy loading
        self.extras['sideloading'] = 'false'
        # enable debug for inline types
        self.extras['debug'] = 'true'
        self._reset()

    def __repr__(self):
        return 'Query: %s' % self.resource.name

    def all(self):
        return self._copy()

    def list(self):
        return list(self)

    def first(self):
        l = self.list()
        return l[0] if l else None

    def last(self):
        l = self.list()
        return l[-1] if l else None

    def map(self, field='id'):
        return dict((
            (getattr(k, field), k) for k in self.list()
        ))

    def get(self, id):
        """Returns a single record by ID.

        Arguments:
            id: a resource ID
        """
        resource = self.resource
        response = resource.request('get', id=id, params=self._get_params())
        return self._load(response)

    def filter(self, **kwargs):
        return self._copy(filters=kwargs)

    def exclude(self, **kwargs):
        filters = dict(('-' + k, v) for k, v in kwargs.items())
        return self._copy(filters=filters)

    def including(self, *args):
        return self._copy(includes=args)

    def excluding(self, *args):
        return self._copy(excludes=args)

    def extra(self, **kwargs):
        return self._copy(extras=kwargs)

    def sort(self, *args):
        return self._copy(orders=args)

    def order_by(self, *args):
        return self.sort(*args)

    def _get_params(self):
        filters = self.filters
        includes = self.includes
        excludes = self.excludes
        orders = self.orders
        extras = self.extras

        params = {}
        for key, value in filters.items():
            filter_key = 'filter{%s}' % key.replace('__', '.')
            params[filter_key] = value

        if includes:
            params['include[]'] = includes

        if excludes:
            params['exclude[]'] = excludes

        if orders:
            params['sort[]'] = orders

        for key, value in extras.items():
            params[key] = value
        return params

    def _reset(self):
        # current page of data
        self._data = None
        # iteration index on current page
        self._index = None
        # page number
        self._page = None
        # total number of pages
        self._pages = None

    def _copy(self, **kwargs):
        data = self.__dict__
        new_data = {
            k: copy(v)
            for k, v in data.items()
            if not k.startswith('_')
        }
        for key, value in kwargs.items():
            new_value = data.get(key)
            if isinstance(new_value, dict):
                if value != new_value:
                    new_value = copy(new_value)
                    new_value.update(value)
            elif (
                isinstance(new_value, (list, tuple)) and
                not isinstance(new_value, string_types)
            ):
                if value != new_value:
                    new_value = list(set(new_value + list(value)))
            new_data[key] = new_value
        return DRESTQuery(**new_data)

    def _get_page(self, params):
        if self._page is None:
            self._page = 1
        else:
            self._page += 1

        resource = self.resource
        params['page'] = self._page
        data = resource.request('get', params=params)
        meta = data.get('meta', {})
        pages = meta.get('total_pages', 1)

        self._data = self._load(data)
        self._pages = pages
        self._index = 0

    def _load(self, data):
        return self.resource.load(unpack(data))

    def __iter__(self):
        # TODO: implement __getitem__ for random access
        params = self._get_params()
        self._get_page(params)
        while True:
            if self._index == len(self._data):
                # end of page
                if self._page == self._pages:
                    # end of results
                    self._reset()
                    raise StopIteration()
                self._get_page(params)

            yield self._data[self._index]
            self._index += 1
