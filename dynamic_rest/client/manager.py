from .recordset import APIRecordSet

class APIResourceManager(object):
    def __init__(self, resource):
        self.resource = resource

    def get(self, pk):
        return APIRecordSet(self).get(pk)

    def filter(self, **kwargs):
        return APIRecordSet(self, filters=kwargs)

    def all(self):
        return APIRecordSet(self)
