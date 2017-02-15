from unittest import TestCase
from dj.test import TemporaryApplication
import requests
import json


class DJBlueprintsTestCase(TestCase):

    def test_blueprints(self):
        application = TemporaryApplication()

        application.execute('generate model foo')
        application.execute('add dynamic-rest')
        application.execute('generate api v0 foo')
        application.execute('migrate')
        server = application.execute('serve 9123', async=True)

        response = requests.post('localhost:9123/v0/foos/')
        self.assertTrue(response.status_code, 201)
        content = json.loads(response.content)
        self.assertEquals(content, {'foo': {'id': 1}})

        server.terminate()
