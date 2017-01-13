from copy import copy


def extract(content):
    keys = [k for k in content.keys() if k != 'meta']
    return content[keys[0]]


def build_params(
    filters,
    includes,
    excludes,
    orders,
    extras
):
    params = {}
    for key, value in filters.items():
        filter_key = 'filter{%s}' % key.replace('__', '.')
        params[filter_key] = value

    params['include[]'] = includes
    params['exclude[]'] = excludes
    params['sort[]'] = orders

    for key, value in extras.items():
        params[key] = value
    return params


class APIRecordSet(object):

    def __init__(
        self,
        manager=None,
        pk=None,
        filters=None,
        orders=None,
        includes=None,
        excludes=None,
        extras=None
    ):
        self.manager = manager
        self.filters = filters or {}
        self.includes = includes or []
        self.excludes = excludes or []
        self.orders = orders or []
        self.extras = extras or {}
        # force-disable sideloading for easier loading
        self.extras['sideloading'] = 'false'
        self.pk = pk
        self._reset()

    def get_params(self):
        return build_params(
            self.filters,
            self.includes,
            self.excludes,
            self.orders,
            self.extras
        )

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
            for k, v in data.items() if not k.startswith('_')
        }
        for key, value in kwargs.items():
            new_value = data.get(key)
            if isinstance(new_value, dict):
                if value != new_value:
                    new_value = copy(new_value)
                    new_value.update(value)
            elif (
                isinstance(new_value, (list, tuple)) and
                not isinstance(new_value, basestring)
            ):
                if value != new_value:
                    new_value = list(set(new_value + value))
            new_data[key] = new_value
        return APIRecordSet(**new_data)

    def get(self, pk):
        resource = self.manager.resource
        client = resource.client
        data = client.get(
            '%s/%s' % (resource.name, pk),
            params=self.get_params()
        )
        return extract(data)

    def filter(self, **kwargs):
        return self._copy(filters=kwargs)

    def include(self, *args):
        return self._copy(includes=args)

    def exclude(self, *args):
        return self._copy(excludes=args)

    def extra(self, **kwargs):
        return self._copy(extras=kwargs)

    def order_by(self, *args):
        return self._copy(orders=args)

    def _get_page(self, params):
        if self._page is None:
            self._page = 1
        else:
            self._page += 1

        resource = self.manager.resource
        client = resource.client

        params['page'] = self._page
        data = client.get(resource.name, params=params)
        meta = data.get('meta', {})
        pages = meta.get('total_pages', 1)

        self._data = extract(data)
        self._pages = pages
        self._index = 0

    def __iter__(self):
        params = self.get_params()
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
