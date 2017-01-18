from .utils import unpack
from .exceptions import DoesNotExist


class DRESTRecord(object):
    # TODO: use metadata to figure out which fields to ignore
    FIELD_BLACKLIST = {'links'}

    def __init__(self, resource, **data):
        self._resource = resource
        self._load(data)

    @property
    def _data(self):
        return {
            k: v for k, v in self.__dict__.items()
            if not k.startswith('_') and k not in self.FIELD_BLACKLIST
        }

    @property
    def _diff(self):
        data = self._data
        for key, value in data.items():
            if key in self._clean and value == self._clean[key]:
                data.pop(key)

        return data

    def _load(self, data):
        for key, value in data.items():
            if key.startswith('_'):
                data.pop(key)
            setattr(self, key, value)

        self._clean = self._data
        self.id = data.get('_meta', {}).get('id', data.get('id', None))

    def __repr__(self):
        return '%s.%s' % (self._resource.name, self.id if self.id else '')

    def save(self):
        id = self.id
        data = self._diff if id else self._data
        if data:
            response = self._resource.request(
                'patch' if id else 'post',
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
