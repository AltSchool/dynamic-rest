from rest_framework.test import APITestCase, APIClient
from dynamic_rest.client import DRESTClient
from six import string_types
from dynamic_rest.client.exceptions import (
    BadRequest, DoesNotExist
)
from tests.setup import create_fixture
import urllib
try:
    urlencode = urllib.urlencode
except:
    # Py3
    urlencode = urllib.parse.urlencode


class MockSession(object):

    """requests.session compatiability adapter for DRESTClient."""

    def __init__(self, client):
        self._client = client or APIClient()
        self.headers = {}

    def request(self, method, url, params=None, data=None):
        def make_params(params):
            list_params = []
            for key, value in params.items():
                if isinstance(
                    value, string_types
                ) or not isinstance(value, list):
                    value = [value]
                for v in value:
                    list_params.append((key, v))
            return urlencode(list_params)

        url = '%s%s' % (
            url,
            ('?%s' % make_params(params)) if params else ''
        )
        response = getattr(self._client, method)(url, data=data)
        content = response.content.decode('utf-8')
        response.content = content
        return response


class ClientTestCase(APITestCase):

    def setUp(self):
        self.fixture = create_fixture()
        self.drest = DRESTClient('test', client=MockSession(self.client))

    def test_get_all(self):
        users = self.drest.Users.all().list()
        self.assertEquals(len(users), len(self.fixture.users))
        self.assertEquals(
            {user.name for user in users},
            {user.name for user in self.fixture.users}
        )

    def test_get_filter(self):
        users = self.drest.Users.filter(id=self.fixture.users[0].id).list()
        self.assertEquals(1, len(users))
        self.assertEquals(users[0].name, self.fixture.users[0].name)

    def test_get_one(self):
        fixed_user = self.fixture.users[0]
        pk = fixed_user.pk
        user = self.drest.Users.get(pk)
        self.assertEquals(user.name, fixed_user.name)

    def test_get_include(self):
        users = self.drest.Users.including('location.*').list()
        self.assertEquals(users[0].location.name, '0')

    def test_get_map(self):
        users = self.drest.Users.map()
        id = self.fixture.users[0].pk
        self.assertEquals(users[id].id, id)

    def test_get_exclude(self):
        user = self.fixture.users[0]
        users = self.drest.Users.exclude(name=user.name).map()
        self.assertTrue(user.pk not in users)

    def test_get_including_related_save(self):
        users = self.drest.Users.including('location.*').list()
        user = users[0]
        location = user.location
        _location = self.drest.Locations.map()[location.id]
        self.assertTrue(
            location.name in {l.name for l in self.fixture.locations}
        )
        _location.name = 'foo'
        _location.save()
        location.reload()
        self.assertTrue(_location.name, location.name)
        self.assertTrue(location.name, 'foo')

    def test_get_excluding(self):
        users = self.drest.Users.excluding('*').map()
        pk = self.fixture.users[0].pk
        self.assertEquals(users[pk].id, pk)

    def test_update(self):
        user = self.drest.Users.first()
        user.name = 'foo'
        user.save()
        user = self.drest.Users.first()
        self.assertTrue(user.name, 'foo')

    def test_create(self):
        user = self.drest.Users.create(
            name='foo',
            last_name='bar'
        )
        self.assertIsNotNone(user.id)

    def test_invalid_resource(self):
        with self.assertRaises(DoesNotExist):
            self.drest.Foo.create(name='foo')
        with self.assertRaises(DoesNotExist):
            self.drest.Foo.filter(name='foo').list()

    def test_save_invalid_data(self):
        user = self.drest.Users.first()
        user.date_of_birth = 'foo'
        with self.assertRaises(BadRequest):
            user.save()

    def test_get_invalid_data(self):
        with self.assertRaises(DoesNotExist):
            self.drest.Users.get('does-not-exist')

    def test_extra_pagination(self):
        users = list(self.drest.Users.all().extra(per_page=1))
        users2 = list(self.drest.Users.all())
        self.assertEquals(users, users2)

        name = users[0].name
        users_named = list(self.drest.Users.extra(name=name))
        self.assertTrue(len(users_named), 1)
        self.assertTrue(users_named[0].name, name)

    def test_save_deferred(self):
        user = self.drest.Users.excluding('*').first()
        user.name = 'foo'
        user.save()

        user2 = self.drest.Users.filter(name='foo').first()
        self.assertIsNotNone(user2)
        self.assertEquals(user2.id, user.id)

    def test_sort(self):
        users = self.drest.Users.sort('name').list()
        self.assertEquals(
            users,
            list(sorted(users, key=lambda x: x.name))
        )
