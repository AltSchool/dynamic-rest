from dynamic_rest.utils import unpack
from .exceptions import DoesNotExist


class DRESTRecord(object):

    def __init__(self, resource, **data):
        self._resource = resource
        self._load(data)

    def save(self):
        id = self.id
        new = not id
        data = (
            self._get_data() if new
            else self._serialize(self._get_diff())
        )
        if data:
            response = self._resource.request(
                'post' if new else 'patch',
                id=id,
                data=data
            )
            self._load(unpack(response))

    def reload(self):
        id = self.id
        if id:
            response = self._resource.request('get', id=id)
            self._load(unpack(response))
        else:
            raise DoesNotExist()

    def __eq__(self, other):
        if hasattr(other, '_get_data'):
            other = other._get_data()
        return self._get_data() == other

    def __repr__(self):
        return '%s.%s' % (self._resource.name, self.id if self.id else '')

    def _get_data(self, fn=None):
        if fn is None:
            flt = lambda k, v: not k.startswith('_')
        else:
            flt = lambda k, v: fn(k, v)

        return {
            k: v for k, v in self.__dict__.items()
            if flt(k, v)
        }

    def _get_diff(self):
        return self._get_data(
            lambda k, v: (
                not k.startswith('_') and
                (k not in self._clean or v != self._clean[k])
            )
        )

    def _load(self, data):
        for key, value in data.items():
            setattr(self, key, value)

        self._clean = self._get_data()
        self.id = data.get('_meta', {}).get('id', data.get('id', None))

    def _serialize(self, data):
        for key, values in data.items():
            if isinstance(values, list):
                if len(values) > 0:
                    for i, value in enumerate(values):
                        if isinstance(value, DRESTRecord):
                            values[i] = value.id
            elif isinstance(values, DRESTRecord):
                data[key] = values.id
        return data
