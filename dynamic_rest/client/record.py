from .utils import unpack
from .exceptions import DoesNotExist


class DRESTRecord(object):
    def __init__(self, resource, **data):
        self._resource = resource
        self._load(data)

    def __eq__(self, other):
        if hasattr(other, '_data'):
            other = other._data
        return self._data == other

    @property
    def _data(self):
        return {
            k: v for k, v in self.__dict__.items()
            if not k.startswith('_')
        }

    @property
    def _diff(self):
        diff = {}
        for key, value in self._data.items():
            if key not in self._clean or value != self._clean[key]:
                diff[key] = value
        return diff

    def _load(self, data):
        for key, value in data.items():
            setattr(self, key, value)

        self._clean = self._data
        self.id = data.get('_meta', {}).get('id', data.get('id', None))

    def __repr__(self):
        return '%s.%s' % (self._resource.name, self.id if self.id else '')

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

    def save(self):
        id = self.id
        new = not id
        data = self._data if new else self._serialize(self._diff)
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
