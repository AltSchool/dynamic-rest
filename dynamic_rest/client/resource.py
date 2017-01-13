from .manager import APIResourceManager

class APIResource(object):
    def __init__(self, client, name):
        self.name = name
        self.client = client
        self.objects = APIResourceManager(self)
