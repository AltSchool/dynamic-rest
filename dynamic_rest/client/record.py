from .utils import unpack
from .exceptions import DoesNotExist


class DRESTRecord(object):
    FIELD_BLACKLIST = {'links'}

    def __init__(self, resource, **data):
        self._resource = resource
        self._load(data)

    def _get_data(self):
        return {
            k: v for k, v in self.__dict__.items()
            if not k.startswith('_') and k not in self.FIELD_BLACKLIST
        }

    def _load(self, data):
        for key, value in data.items():
            if key.startswith('_'):
                data.pop(key)
            setattr(self, key, value)

        self.id = data.get('id', data.get('_id', None))

    def __repr__(self):
        return '%s.%s' % (self._resource.name, self.id if self.id else '')

    def save(self):
        id = self.id
        response = self._resource.request(
            'patch' if id else 'post',
            id=self.id,
            data=self._get_data()
        )
        self._load(unpack(response))
        return response

    def reload(self):
        id = self.id
        if id:
            response = self._resource.request('get', id=id)
            self._load(unpack(response))
        else:
            raise DoesNotExist()
