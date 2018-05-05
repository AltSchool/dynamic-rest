import json

from django.contrib.auth.models import User
from tests.setup import create_fixture
from rest_framework.test import APITestCase


class TestPermissionsUsersAPI(APITestCase):

    def setUp(self):
        self.fixture = create_fixture()
        self.maxDiff = None
        self.default_user = User.objects.filter(
            manager__isnull=True,
            officer__isnull=True
        ).first()
        self.manager_user = User.objects.filter(
            manager__isnull=False
        ).first()
        self.officer_user = User.objects.filter(
            officer__isnull=False
        ).first()
        self.admin_user = User.objects.filter(
            is_superuser=True
        ).first()

    def test_default_user(self):
        self.client.force_authenticate(user=self.default_user)
        response = self.client.get('/p/users/')
        # no list
        self.assertEquals(403, response.status_code)
        # read
        response = self.client.get(
            '/p/users/%s/' % self.default_user.id
        )
        self.assertEquals(200, response.status_code)
        content = json.loads(response.content)
        self.assertTrue(len(content['user']), 1)
        # no update
        data = content['user']
        data['last_name'] = 'joe'
        response = self.client.put(
            '/p/users/%s/' % self.default_user.id,
            data,
            format='json'
        )
        self.assertEquals(404, response.status_code)
        # no create
        data['username'] = 'foobar'
        data.pop('id', None)
        response = self.client.post(
            '/p/users/',
            data,
            format='json'
        )
        self.assertEquals(403, response.status_code, response.content)
        # no delete
        response = self.client.delete(
            '/p/users/%s/' % self.default_user.id
        )
        self.assertEquals(404, response.status_code)

    def test_officer_user(self):
        self.client.force_authenticate(user=self.officer_user)
        response = self.client.get('/p/users/')
        # list
        self.assertEquals(200, response.status_code)
        content = json.loads(response.content)
        self.assertTrue(len(content['users']), 3)
        # read
        response = self.client.get(
            '/p/users/%s/' % self.default_user.id
        )
        content = json.loads(response.content)
        self.assertTrue(len(content['user']), 1)
        # partial update
        data = content['user']
        data['username'] = 'foobar'
        response = self.client.put(
            '/p/users/%s/' % self.default_user.id,
            data=data,
            format='json'
        )
        self.assertEquals(404, response.status_code)

        response = self.client.put(
            '/p/users/%s/' % self.officer_user.id,
            data=data,
            format='json'
        )
        self.assertEquals(200, response.status_code, response.content)
        # no create
        data.pop('id', None)
        data['username'] = 'newbar'
        response = self.client.post(
            '/p/users/',
            data,
            format='json'
        )
        self.assertEquals(403, response.status_code, response.content)
        # no delete
        response = self.client.delete(
            '/p/users/%s/' % self.default_user.id
        )

    def test_manager_user(self):
        self.client.force_authenticate(user=self.manager_user)
        response = self.client.get('/p/users/')
        # list
        self.assertEquals(200, response.status_code)
        content = json.loads(response.content)
        self.assertTrue(len(content['users']), 3)
        # read
        response = self.client.get(
            '/p/users/%s/' % self.default_user.id
        )
        content = json.loads(response.content)
        self.assertTrue(len(content['user']), 1)
        # update
        data = content['user']
        data['username'] = 'foobar'
        response = self.client.put(
            '/p/users/%s/' % self.default_user.id,
            data=data,
            format='json'
        )
        self.assertEquals(200, response.status_code, response.content)
        data['username'] = 'twobar'
        response = self.client.put(
            '/p/users/%s/' % self.officer_user.id,
            data=data,
            format='json'
        )
        self.assertEquals(200, response.status_code)
        # create
        data.pop('id', None)
        data['username'] = 'newbar'
        response = self.client.post(
            '/p/users/',
            data=data,
            format='json'
        )
        self.assertEquals(201, response.status_code, response.content)
        # partial delete
        response = self.client.delete(
            '/p/users/%s/' % self.default_user.id
        )
        self.assertEquals(204, response.status_code)
        response = self.client.delete(
            '/p/users/%s/' % self.admin_user.id
        )
        self.assertEquals(404, response.status_code)

    def test_admin_user(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/p/users/')
        # list
        self.assertEquals(200, response.status_code)
        content = json.loads(response.content)
        self.assertTrue(len(content['users']), 4)
        # read
        response = self.client.get(
            '/p/users/%s/' % self.default_user.id
        )
        content = json.loads(response.content)
        self.assertTrue(len(content['user']), 1)
        # update
        data = content['user']
        data['username'] = 'foobar'
        # can also update the read-only is_superuser field!
        data['is_superuser'] = True
        response = self.client.put(
            '/p/users/%s/' % self.default_user.id,
            data=data,
            format='json'
        )
        self.assertEquals(200, response.status_code, response.content)
        content = json.loads(response.content)
        self.assertEquals(content['user']['is_superuser'], True)
        # create
        data.pop('id', None)
        data['username'] = 'newbar'
        response = self.client.post(
            '/p/users/',
            data=data,
            format='json'
        )
        self.assertEquals(201, response.status_code, response.content)
        # delete
        response = self.client.delete(
            '/p/users/%s/' % self.admin_user.id
        )
        self.assertEquals(204, response.status_code)
