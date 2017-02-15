from unittest import TestCase
from dj.test import TemporaryApplication
from django.conf import settings
import requests
import json
import os

if settings.ENABLE_INTEGRATION_TESTS:
    class DJBlueprintsTestCase(TestCase):

        def test_blueprints(self):
            application = TemporaryApplication()
            # this file is ROOT/tests/integration/test_blueprints.py
            root = os.path.abspath(os.path.join(__file__, '../../..'))
            print root

            application.execute('generate model foo')
            application.execute('add ' + root + ' --dev')
            application.execute('generate api v0 foo')
            application.execute('migrate')
            server = application.execute('serve 9123', async=True)

            response = requests.post('localhost:9123/v0/foos/')
            self.assertTrue(response.status_code, 201)
            content = json.loads(response.content)
            self.assertEquals(content, {'foo': {'id': 1}})

            server.terminate()
