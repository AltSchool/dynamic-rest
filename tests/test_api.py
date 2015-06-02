import json
from django.db import connection
from rest_framework.test import APITestCase
from tests.setup import create_fixture
from tests.models import User, Group


class TestUsersAPI(APITestCase):

    def setUp(self):
        self.fixture = create_fixture()
        self.maxDiff = None

    def testDefault(self):
        with self.assertNumQueries(1):
            # 1 for User, 0 for Location
            response = self.client.get('/users/')
        self.assertEquals(200, response.status_code)
        self.assertEquals({
            'users': [{
                'id': 1,
                'location': 1,
                'name': '0'
            }, {
                'id': 2,
                'location': 1,
                'name': '1'
            }, {
                'id': 3,
                'location': 2,
                'name': '2'
            }, {
                'id': 4,
                'location': 3,
                'name': '3'
            }]
        }, json.loads(response.content))

    def testInclude(self):
        with self.assertNumQueries(2):
            # 2 queries: 1 for User, 1 for Group, 0 for Location
            response = self.client.get('/users/?include[]=groups')
        self.assertEquals(200, response.status_code)
        self.assertEquals({
            'users': [{
                'id': 1,
                'groups': [1, 2],
                'location': 1,
                'name': '0'
            }, {
                'id': 2,
                'groups': [1, 2],
                'location': 1,
                'name': '1'
            }, {
                'id': 3,
                'groups': [1, 2],
                'location': 2,
                'name': '2'
            }, {
                'id': 4,
                'groups': [1, 2],
                'location': 3,
                'name': '3'
            }]
        }, json.loads(response.content))

        with self.assertNumQueries(2):
            # 2 queries: 1 for User, 1 for Group
            response = self.client.get('/groups/?include[]=members')
        self.assertEquals(200, response.status_code)
        self.assertEquals({
            'groups': [{
                'id': 1,
                'members': [1, 2, 3, 4],
                'name': '0'
            }, {
                'id': 2,
                'members': [1, 2, 3, 4],
                'name':
                '1'
            }]
        }, json.loads(response.content))

    def testExclude(self):
        with self.assertNumQueries(1):
            response = self.client.get('/users/?exclude[]=name')
        query = connection.queries[-1]['sql']
        self.assertFalse('name' in query, query)
        self.assertFalse('*' in query, query)

        self.assertEquals(200, response.status_code)
        self.assertEquals({
            'users': [{
                'id': 1,
                'location': 1
            }, {
                'id': 2,
                'location': 1
            }, {
                'id': 3,
                'location': 2
            }, {
                'id': 4,
                'location': 3
            }]
        }, json.loads(response.content))

    def testNestedHasOne(self):
        with self.assertNumQueries(2):
            response = self.client.get('/users/?include[]=location.')
        self.assertEquals(200, response.status_code)
        self.assertEquals({
            'locations': [{
                'id': 1,
                'name': '0'
            }, {
                'id': 2,
                'name': '1'
            }, {
                'id': 3,
                'name': '2'
            }],
            'users': [{
                'id': 1,
                'location': 1,
                'name': '0'
            }, {
                'id': 2,
                'location': 1,
                'name': '1'
            }, {
                'id': 3,
                'location': 2,
                'name': '2'
            }, {
                'id': 4,
                'location': 3,
                'name': '3'
            }]
        }, json.loads(response.content))

    def testNestedHasMany(self):
        with self.assertNumQueries(2):
            # 2 queries: 1 for User, 1 for Group
            response = self.client.get('/users/?include[]=groups.')
        self.assertEquals(200, response.status_code)
        self.assertEquals(
            {'groups': [{'id': 1, 'name': '0'}, {'id': 2, 'name': '1'}],
             'users': [{
                 'groups': [1, 2], 'id': 1, 'location': 1, 'name': '0'
             }, {
                 'groups': [1, 2], 'id': 2, 'location': 1, 'name': '1'
             }, {
                 'groups': [1, 2], 'id': 3, 'location': 2, 'name': '2'
             }, {
                 'groups': [1, 2], 'id': 4, 'location': 3, 'name': '3'
             }]},
            json.loads(response.content))

    def testNestedInclude(self):
        with self.assertNumQueries(3):
            # 3 queries: 1 for User, 1 for Group, 1 for Permissions
            response = self.client.get('/users/?include[]=groups.permissions')
        self.assertEquals(200, response.status_code)
        self.assertEquals(
            {'groups': [{'id': 1, 'name': '0', 'permissions': [1]},
                        {'id': 2, 'name': '1', 'permissions': [2]}],
             'users': [{
                 'groups': [1, 2], 'id': 1, 'location': 1, 'name': '0'
             }, {
                 'groups': [1, 2], 'id': 2, 'location': 1, 'name': '1'
             }, {
                 'groups': [1, 2], 'id': 3, 'location': 2, 'name': '2'
             }, {
                 'groups': [1, 2], 'id': 4, 'location': 3, 'name': '3'
             }
            ]},
            json.loads(response.content))

    def testNestedExclude(self):
        with self.assertNumQueries(2):
            # 2 queries: 1 for User, 1 for Group
            response = self.client.get('/users/?exclude[]=groups.name')
        self.assertEquals(200, response.status_code)
        self.assertEquals(
            {'groups': [{'id': 1}, {'id': 2}],
             'users': [{
                 'groups': [1, 2], 'id': 1, 'location': 1, 'name': '0'
             }, {
                 'groups': [1, 2], 'id': 2, 'location': 1, 'name': '1'
             }, {
                 'groups': [1, 2], 'id': 3, 'location': 2, 'name': '2'
             }, {
                 'groups': [1, 2], 'id': 4, 'location': 3, 'name': '3'
             }]},
            json.loads(response.content))

    def testSingleResourceSideload(self):
        with self.assertNumQueries(2):
            # 2 queries: 1 for User, 1 for Group
            response = self.client.get('/users/1/?include[]=groups.')
        self.assertEquals(200, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(len(data['groups']), 2)

    def testFilterBasic(self):
        with self.assertNumQueries(1):
            response = self.client.get('/users/?filter{name}=1')
        self.assertEquals(200, response.status_code)
        self.assertEquals(
            {
                'users': [
                    {'id': 2, 'location': 1, 'name': '1'},
                ]
            },
            json.loads(response.content))

    def testFilterIn(self):
        url = '/users/?filter{name.in}=1&filter{name.in}=2'
        with self.assertNumQueries(1):
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        self.assertEquals(
            {
                'users': [
                    {'id': 2, 'location': 1, 'name': '1'},
                    {'id': 3, 'location': 2, 'name': '2'},
                ]
            },
            json.loads(response.content))

    def testFilterExclude(self):
        url = '/users/?filter{-name}=1'
        with self.assertNumQueries(1):
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        self.assertEquals(
            {
                'users': [
                    {'id': 1, 'location': 1, 'name': '0'},
                    {'id': 3, 'location': 2, 'name': '2'},
                    {'id': 4, 'location': 3, 'name': '3'},
                ]
            },
            json.loads(response.content))

    def testFilterRelation(self):
        url = '/users/?filter{location.name}=1'
        with self.assertNumQueries(1):
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        self.assertEquals(
            {
                'users': [
                    {'id': 3, 'location': 2, 'name': '2'},
                ]
            },
            json.loads(response.content))

    def testFilterSideload(self):
        url = '/users/?include[]=groups.&filter{groups|name}=1'
        with self.assertNumQueries(2):
            # 2 queries: 1 for User, 1 for Group
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        self.assertEquals(
            {
                'groups': [{'id': 2, 'name': '1'}],
                'users': [
                    {'groups': [2], 'id': 1, 'location': 1, 'name': '0'},
                    {'groups': [2], 'id': 2, 'location': 1, 'name': '1'},
                    {'groups': [2], 'id': 3, 'location': 2, 'name': '2'},
                    {'groups': [2], 'id': 4, 'location': 3, 'name': '3'}
                ]
            },
            json.loads(response.content))

    def testFilterSourceRewrite(self):
        """ Test filtering on fields where source is different """
        url = '/locations/?filter{address}=here&include[]=address'
        with self.assertNumQueries(1):
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(len(data['locations']), 1)

    def testFilterQueryInjection(self):
        """ Test viewset with query injection """
        url = '/users/?name=1'
        with self.assertNumQueries(1):
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(len(data['users']), 1)
        self.assertEquals(data['users'][0]['name'], '1')

    def testIncludeO2M(self):
        """ Test o2m without related_name set. """
        url = '/locations/?filter{id}=1&include[]=users'
        with self.assertNumQueries(2):
            # 2 queries: 1 for locations, 1 for location-users
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(len(data['locations']), 1)
        self.assertEquals(len(data['locations'][0]['users']), 2)

    def testCountField(self):
        url = '/locations/?filter{id}=1&include[]=users&include[]=user_count'
        with self.assertNumQueries(2):
            # 2 queries: 1 for locations, 1 for location-users
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(len(data['locations']), 1)
        self.assertEquals(len(data['locations'][0]['users']), 2)
        self.assertEquals(data['locations'][0]['user_count'], 2)

    def testQuerysetInjection(self):
        url = '/users/?location=1'
        with self.assertNumQueries(1):
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(len(data['users']), 2)

    def testInvalid(self):
        for bad_data in ('name..', 'groups..name', 'foo', 'groups.foo'):
            response = self.client.get('/users/?include[]=%s' % bad_data)
            self.assertEquals(400, response.status_code)

    def testPostResponse(self):
        data = {
            'name': 'test',
            'last_name': 'last',
            'location': 1
            }
        response = self.client.post(
            '/users/', json.dumps(data), content_type='application/json')
        self.assertEquals(201, response.status_code)
        self.assertEquals(
            json.loads(response.content),
            {
                "user": {
                    "id": 5,
                    "name": "test",
                    "permissions": [],
                    "groups": [],
                    "location": 1,
                    "last_name": "last"
                    }
            })

    def testUpdate(self):
        group = Group.objects.create(name='test group')
        data = {
            'name': 'updated'
            }
        response = self.client.put(
            '/groups/%s/' % group.pk,
            json.dumps(data),
            content_type='application/json')
        self.assertEquals(200, response.status_code)
        updated_group = Group.objects.get(pk=group.pk)
        self.assertEquals(updated_group.name, data['name'])

    def testDefaultQueryset(self):
        url = '/groups/?filter{id}=1&include[]=loc1users'
        response = self.client.get(url)
        content = json.loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual(sorted([1, 2]), content['groups'][0]['loc1users'])

    def testDefaultQuerysetWithFilter(self):
        """
        Make sure filter can be added to relational fields with default
        filters.
        """
        url = (
            '/groups/?filter{id}=1&include[]=loc1users'
            '&filter{loc1users|id.in}=3'
            '&filter{loc1users|id.in}=1'
            )
        response = self.client.get(url)
        content = json.loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual([1], content['groups'][0]['loc1users'])

    def testFilterWithNestedRewrite(self):
        """
        Test filter for members.id which needs to be rewritten as users.id
        """
        user = User.objects.create(name='test user')
        group = Group.objects.create(name='test group')
        user.groups.add(group)

        url = '/groups/?filter{members.id}=%s&include[]=members' % user.pk
        response = self.client.get(url)
        content = json.loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(content['groups']))
        self.assertEqual(group.pk, content['groups'][0]['id'])

        url = (
            '/users/?filter{groups.members.id}=%s'
            '&include[]=groups.members' % user.pk
        )
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        content = json.loads(response.content)
        self.assertEqual(1, len(content['users']))

    def testBadFilter(self):
        # Filtering on non-existent field should return 400
        url = '/users/?filter{foobar}=1'
        response = self.client.get(url)
        self.assertEqual(400, response.status_code)

    def testBadDeferredFilter(self):
        # Filtering deferred field without including should return 400
        url = '/users/?filter{groups.id}=1'
        response = self.client.get(url)
        self.assertEqual(400, response.status_code)

    def testIsNull(self):
        """
        Test for .isnull filters
        """

        # User with location=None
        User.objects.create(name='name', last_name='lname', location=None)

        # Count Users where location is not null
        expected = User.objects.filter(location__isnull=False).count()

        url = '/users/?filter{location.isnull}=0'
        response = self.client.get(url)
        content = json.loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual(expected, len(content['users']))

        url = '/users/?filter{location.isnull}=False'
        response = self.client.get(url)
        content = json.loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual(expected, len(content['users']))

        url = '/users/?filter{location.isnull}=1'
        response = self.client.get(url)
        content = json.loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(content['users']))

        url = '/users/?filter{-location.isnull}=True'
        response = self.client.get(url)
        content = json.loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual(expected, len(content['users']))
