import datetime
import json

from django.db import connection
from django.test import override_settings
from django.utils import six
from rest_framework.test import APITestCase

from tests.models import Cat, Group, Location, Profile, User
from tests.serializers import NestedEphemeralSerializer
from tests.setup import create_fixture

UNICODE_STRING = six.unichr(9629)  # unicode heart
# UNICODE_URL_STRING = urllib.quote(UNICODE_STRING.encode('utf-8'))
UNICODE_URL_STRING = '%E2%96%9D'


@override_settings(
    DYNAMIC_REST={
        'ENABLE_LINKS': False
    }
)
class TestUsersAPI(APITestCase):

    def setUp(self):
        self.fixture = create_fixture()
        self.maxDiff = None

    def test_get(self):
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
        }, json.loads(response.content.decode('utf-8')))

    def test_get_with_trailing_slash_does_not_redirect(self):
        response = self.client.get('/users/1')
        self.assertEquals(200, response.status_code)

    def test_get_with_include(self):
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
        }, json.loads(response.content.decode('utf-8')))

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
        }, json.loads(response.content.decode('utf-8')))

    def test_get_with_exclude(self):
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
        }, json.loads(response.content.decode('utf-8')))

    def test_get_with_nested_has_one(self):
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
        }, json.loads(response.content.decode('utf-8')))

    def test_get_with_nested_has_many(self):
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
            json.loads(response.content.decode('utf-8')))

    def test_get_with_nested_include(self):
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
            json.loads(response.content.decode('utf-8')))

    def test_get_with_nested_exclude(self):
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
            json.loads(response.content.decode('utf-8')))

    def test_get_with_nested_exclude_all(self):
        with self.assertNumQueries(2):
            # 2 queries: 1 for User, 1 for Group
            url = '/users/?exclude[]=groups.*&include[]=groups.name'
            response = self.client.get(url)
        self.assertEquals(
            200,
            response.status_code,
            response.content.decode('utf-8'))
        self.assertEquals(
            {
                'groups': [{'name': '0'}, {'name': '1'}],
                'users': [{
                    'groups': [1, 2], 'id': 1, 'location': 1, 'name': '0'
                }, {
                    'groups': [1, 2], 'id': 2, 'location': 1, 'name': '1'
                }, {
                    'groups': [1, 2], 'id': 3, 'location': 2, 'name': '2'
                }, {
                    'groups': [1, 2], 'id': 4, 'location': 3, 'name': '3'
                }]
            },
            json.loads(response.content.decode('utf-8')))

    def test_get_with_exclude_all_and_include_field(self):
        with self.assertNumQueries(1):
            url = '/users/?exclude[]=*&include[]=id'
            response = self.client.get(url)
        self.assertEquals(
            200,
            response.status_code,
            response.content.decode('utf-8'))
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(
            set(['id']),
            set(data['users'][0].keys())
        )

    def test_get_with_exclude_all_and_include_relationship(self):
        with self.assertNumQueries(2):
            url = '/users/?exclude[]=*&include[]=groups.'
            response = self.client.get(url)
        self.assertEquals(
            200,
            response.status_code,
            response.content.decode('utf-8'))
        data = json.loads(response.content.decode('utf-8'))
        self.assertEquals(
            set(['groups']),
            set(data['users'][0].keys())
        )
        self.assertTrue('groups' in data)

    def test_get_one_with_include(self):
        with self.assertNumQueries(2):
            # 2 queries: 1 for User, 1 for Group
            response = self.client.get('/users/1/?include[]=groups.')
        self.assertEquals(200, response.status_code)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEquals(len(data['groups']), 2)

    def test_get_with_filter(self):
        with self.assertNumQueries(1):
            # verify that extra [] are stripped out of the key
            response = self.client.get('/users/?filter{name}[]=1')
        self.assertEquals(200, response.status_code)
        self.assertEquals(
            {
                'users': [
                    {'id': 2, 'location': 1, 'name': '1'},
                ]
            },
            json.loads(response.content.decode('utf-8')))

    def test_get_with_filter_no_match(self):
        with self.assertNumQueries(1):
            response = self.client.get('/users/?filter{name}[]=foo')
        self.assertEquals(200, response.status_code)
        self.assertEquals(
            {'users': []},
            json.loads(response.content.decode('utf-8')))

    def test_get_with_filter_unicode_no_match(self):
        with self.assertNumQueries(1):
            response = self.client.get(
                '/users/?filter{name}[]=%s' % UNICODE_URL_STRING
            )
        self.assertEquals(200, response.status_code)
        self.assertEquals(
            {'users': []},
            json.loads(response.content.decode('utf-8')))
        with self.assertNumQueries(1):
            response = self.client.get(
                six.u('/users/?filter{name}[]=%s') % UNICODE_STRING
            )
        self.assertEquals(200, response.status_code)
        self.assertEquals(
            {'users': []},
            json.loads(response.content.decode('utf-8')))

    def test_get_with_filter_unicode(self):
        User.objects.create(
            name=UNICODE_STRING,
            last_name='Unicode'
        )
        with self.assertNumQueries(1):
            response = self.client.get(
                '/users/?filter{name}[]=%s' % UNICODE_URL_STRING
            )
        self.assertEquals(200, response.status_code)
        self.assertEquals(
            1,
            len(
                json.loads(
                    response.content.decode('utf-8')
                )['users']
            )
        )
        with self.assertNumQueries(1):
            response = self.client.get(
                six.u('/users/?filter{name}[]=%s') % UNICODE_STRING
            )
        self.assertEquals(200, response.status_code)
        self.assertEquals(
            1,
            len(
                json.loads(
                    response.content.decode('utf-8')
                )['users']
            )
        )

    def test_get_with_filter_in(self):
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
            json.loads(response.content.decode('utf-8')))

    def test_get_with_filter_exclude(self):
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
            json.loads(response.content.decode('utf-8')))

    def test_get_with_filter_relation_field(self):
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
            json.loads(response.content.decode('utf-8')))

    def test_get_with_filter_and_include_relationship(self):
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
            json.loads(response.content.decode('utf-8')))

    def test_get_with_filter_and_source_rewrite(self):
        """ Test filtering on fields where source is different """
        url = '/locations/?filter{address}=here&include[]=address'
        with self.assertNumQueries(1):
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEquals(len(data['locations']), 1)

    def test_get_with_filter_and_query_injection(self):
        """ Test viewset with query injection """
        url = '/users/?name=1'
        with self.assertNumQueries(1):
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEquals(len(data['users']), 1)
        self.assertEquals(data['users'][0]['name'], '1')

    def test_get_with_include_one_to_many(self):
        """ Test o2m without related_name set. """
        url = '/locations/?filter{id}=1&include[]=users'
        with self.assertNumQueries(2):
            # 2 queries: 1 for locations, 1 for location-users
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEquals(len(data['locations']), 1)
        self.assertEquals(len(data['locations'][0]['users']), 2)

    def test_get_with_count_field(self):
        url = '/locations/?filter{id}=1&include[]=users&include[]=user_count'
        with self.assertNumQueries(2):
            # 2 queries: 1 for locations, 1 for location-users
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEquals(len(data['locations']), 1)
        self.assertEquals(len(data['locations'][0]['users']), 2)
        self.assertEquals(data['locations'][0]['user_count'], 2)

    def test_get_with_queryset_injection(self):
        url = '/users/?location=1'
        with self.assertNumQueries(1):
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEquals(len(data['users']), 2)

    def test_get_with_include_invalid(self):
        for bad_data in ('name..', 'groups..name', 'foo', 'groups.foo'):
            response = self.client.get('/users/?include[]=%s' % bad_data)
            self.assertEquals(400, response.status_code)

    def test_post(self):
        data = {
            'name': 'test',
            'last_name': 'last',
            'location': 1,
            'display_name': 'test last'  # Read only, should be ignored.
        }
        response = self.client.post(
            '/users/', json.dumps(data), content_type='application/json')
        self.assertEquals(201, response.status_code)
        self.assertEquals(
            json.loads(response.content.decode('utf-8')),
            {
                "user": {
                    "id": 5,
                    "name": "test",
                    "permissions": [],
                    "groups": [],
                    "location": 1,
                    "last_name": "last",
                    "display_name": None,
                    "thumbnail_url": None,
                    "number_of_cats": 1,
                    "profile": None,
                    "date_of_birth": None
                }
            })

    def test_put(self):
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

    def test_get_with_default_queryset(self):
        url = '/groups/?filter{id}=1&include[]=loc1users'
        response = self.client.get(url)
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(200, response.status_code)
        self.assertEqual(sorted([1, 2]), content['groups'][0]['loc1users'])

    def test_get_with_default_lambda_queryset(self):
        url = '/groups/?filter{id}=1&include[]=loc1usersLambda'
        response = self.client.get(url)
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            sorted([1, 2]),
            content['groups'][0]['loc1usersLambda']
        )

    def test_get_with_default_queryset_filtered(self):
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
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(200, response.status_code)
        self.assertEqual([1], content['groups'][0]['loc1users'])

    def test_get_with_filter_nested_rewrites(self):
        """
        Test filter for members.id which needs to be rewritten as users.id
        """
        user = User.objects.create(name='test user')
        group = Group.objects.create(name='test group')
        user.groups.add(group)

        url = '/groups/?filter{members.id}=%s&include[]=members' % user.pk
        response = self.client.get(url)
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(content['groups']))
        self.assertEqual(group.pk, content['groups'][0]['id'])

        url = (
            '/users/?filter{groups.members.id}=%s'
            '&include[]=groups.members' % user.pk
        )
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(1, len(content['users']))

    def test_get_with_filter_nonexistent_field(self):
        # Filtering on non-existent field should return 400
        url = '/users/?filter{foobar}=1'
        response = self.client.get(url)
        self.assertEqual(400, response.status_code)

    def test_get_with_filter_invalid_data(self):
        User.objects.create(
            name='test',
            date_of_birth=datetime.datetime.utcnow()
        )
        url = '/users/?filter{date_of_birth.gt}=0&filter{date_of_birth.lt}=0'
        response = self.client.get(url)
        self.assertEqual(400, response.status_code)
        self.assertEqual(
            ["'0' value has an invalid date format. "
             "It must be in YYYY-MM-DD format."],
            response.data
        )

    def test_get_with_filter_deferred(self):
        # Filtering deferred field should work
        grp = Group.objects.create(name='test group')
        user = self.fixture.users[0]
        user.groups.add(grp)

        url = '/users/?filter{groups.id}=%s' % grp.pk
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(1, len(content['users']))
        self.assertEqual(user.pk, content['users'][0]['id'])

    def test_get_with_filter_outer_joins(self):
        """
        Test that the API does not return duplicate results
        when the underlying SQL query would return dupes.
        """
        user = User.objects.create(name='test')
        group_a = Group.objects.create(name='A')
        group_b = Group.objects.create(name='B')
        user.groups = [group_a, group_b]
        response = self.client.get(
            '/users/?filter{groups.name.in}=A&filter{groups.name.in}=B'
        )
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(1, len(content['users']), content)

    def test_get_with_filter_isnull(self):
        """
        Test for .isnull filters
        """

        # User with location=None
        User.objects.create(name='name', last_name='lname', location=None)

        # Count Users where location is not null
        expected = User.objects.filter(location__isnull=False).count()

        url = '/users/?filter{location.isnull}=0'
        response = self.client.get(url)
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(200, response.status_code)
        self.assertEqual(expected, len(content['users']))

        url = '/users/?filter{location.isnull}=False'
        response = self.client.get(url)
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(200, response.status_code)
        self.assertEqual(expected, len(content['users']))

        url = '/users/?filter{location.isnull}=1'
        response = self.client.get(url)
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(content['users']))

        url = '/users/?filter{-location.isnull}=True'
        response = self.client.get(url)
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(200, response.status_code)
        self.assertEqual(expected, len(content['users']))

    def test_get_with_nested_source_fields(self):
        u1 = User.objects.create(name='test1', last_name='user')
        Profile.objects.create(
            user=u1,
            display_name='foo',
            thumbnail_url='http://thumbnail.url')

        url = (
            '/users/?filter{id}=%s&include[]=display_name'
            '&include[]=thumbnail_url' % u1.pk
        )
        response = self.client.get(url)
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(200, response.status_code)
        self.assertIsNotNone(content['users'][0]['display_name'])
        self.assertIsNotNone(content['users'][0]['thumbnail_url'])

    def test_get_with_nested_source_fields_count(self):
        loc = Location.objects.create(name='test location')
        u1 = User.objects.create(name='test1', last_name='user', location=loc)
        Profile.objects.create(user=u1, display_name='foo')
        u2 = User.objects.create(name='test2', last_name='user', location=loc)
        Profile.objects.create(user=u2, display_name='moo')

        # Test prefetching to pull profile.display_name into UserSerializer
        url = (
            '/users/?include[]=display_name'
            '&include[]=thumbnail_url'
        )

        with self.assertNumQueries(2):
            response = self.client.get(url)
            self.assertEqual(200, response.status_code)

        # Test prefetching of user.location.name into ProfileSerializer
        url = '/profiles/?include[]=user_location_name'
        with self.assertNumQueries(3):
            response = self.client.get(url)
            self.assertEqual(200, response.status_code)
            content = json.loads(response.content.decode('utf-8'))
            self.assertIsNotNone(content['profiles'][0]['user_location_name'])

    def test_get_with_dynamic_method_field(self):
        url = '/users/?include[]=number_of_cats'
        with self.assertNumQueries(3):
            response = self.client.get(url)
            self.assertEqual(200, response.status_code)
            self.assertEquals({
                'users': [{
                    'id': 1,
                    'location': 1,
                    'name': '0',
                    'number_of_cats': 1,
                }, {
                    'id': 2,
                    'location': 1,
                    'name': '1',
                    'number_of_cats': 1,
                }, {
                    'id': 3,
                    'location': 2,
                    'name': '2',
                    'number_of_cats': 1,
                }, {
                    'id': 4,
                    'location': 3,
                    'name': '3',
                    'number_of_cats': 0,
                }]
            }, json.loads(response.content.decode('utf-8')))

    def test_get_with_request_filters_and_requires(self):
        """
        This tests conflicting external and internal prefetch requirements.

        `location.cats` is an external requirement that points
        to the `Location.cat_set` model relationship.

        `user.number_of_cats` is an internal requirement that points
        to the same relationship.

        The prefetch tree produced by this call merges the two together
        into a single prefetch:
        {
           'location': {
              'cat_set': {}
            }
        }
        """

        url = (
            '/users/?'
            'include[]=number_of_cats&'
            'include[]=location.cats.&'
            'filter{location.cats|name.icontains}=1'
        )
        with self.assertNumQueries(3):
            response = self.client.get(url)
            self.assertEqual(200, response.status_code)
            self.assertEquals({
                'cats': [{
                    'id': 2,
                    'name': '1'
                }],
                'locations': [{
                    'name': '0',
                    'id': 1,
                    'cats': []
                }, {
                    'name': '1',
                    'id': 2,
                    'cats': [2]
                }, {
                    'name': '2',
                    'id': 3,
                    'cats': []
                }],
                'users': [{
                    'id': 1,
                    'location': 1,
                    'name': '0',
                    'number_of_cats': 0,
                }, {
                    'id': 2,
                    'location': 1,
                    'name': '1',
                    'number_of_cats': 0,
                }, {
                    'id': 3,
                    'location': 2,
                    'name': '2',
                    'number_of_cats': 1,
                }, {
                    'id': 4,
                    'location': 3,
                    'name': '3',
                    'number_of_cats': 0,
                }]
            }, json.loads(response.content.decode('utf-8')))


@override_settings(
    DYNAMIC_REST={
        'ENABLE_LINKS': False
    }
)
class TestLocationsAPI(APITestCase):

    def setUp(self):
        self.fixture = create_fixture()
        self.maxDiff = None

    def test_options(self):
        response = self.client.options('/locations/')
        self.assertEquals(200, response.status_code)
        actual = json.loads(response.content.decode('utf-8'))
        expected = {
            'description': '',
            'features': ['include[]', 'exclude[]', 'filter{}', 'sort[]'],
            'name': 'Location List',
            'parses': [
                'application/json',
                'application/x-www-form-urlencoded',
                'multipart/form-data'
            ],
            'properties': {
                'name': {
                    'default': None,
                    'label': 'Name',
                    'nullable': False,
                    'read_only': False,
                    'required': True,
                    'type': 'string'
                },
                'address': {
                    'default': None,
                    'label': 'Address',
                    'nullable': False,
                    'read_only': False,
                    'required': False,
                    'type': 'field'
                },
                'id': {
                    'default': None,
                    'label': 'ID',
                    'nullable': False,
                    'read_only': True,
                    'required': False,
                    'type': 'integer'
                },
                'user_count': {
                    'default': None,
                    'label': 'User count',
                    'nullable': False,
                    'read_only': False,
                    'required': False,
                    'type': 'field'
                },
                'users': {
                    'default': None,
                    'label': 'Users',
                    'nullable': False,
                    'read_only': False,
                    'related_to': 'users',
                    'required': False,
                    'type': 'many'
                },
                'cats': {
                    'default': None,
                    'label': 'Cats',
                    'nullable': False,
                    'read_only': False,
                    'related_to': 'cats',
                    'required': False,
                    'type': 'many'
                },
                'bad_cats': {
                    'default': None,
                    'label': 'Bad cats',
                    'nullable': False,
                    'read_only': False,
                    'related_to': 'cats',
                    'required': False,
                    'type': 'many'
                },
                'friendly_cats': {
                    'default': None,
                    'label': 'Friendly cats',
                    'nullable': True,
                    'read_only': False,
                    'related_to': 'cats',
                    'required': False,
                    'type': 'many'
                }
            },
            'renders': ['application/json', 'text/html'],
            'resource_name': 'location',
            'resource_name_plural': 'locations'
        }
        # Django 1.7 and 1.9 differ in their interpretation of
        # "nullable" when it comes to inverse relationship fields.
        # Ignore the values for the purposes of this comparison.
        del actual['properties']['friendly_cats']['nullable']
        del expected['properties']['friendly_cats']['nullable']
        self.assertEquals(
            json.loads(json.dumps(expected)),
            json.loads(json.dumps(actual))
        )

    def test_get_with_filter_by_user(self):
        url = '/locations/?filter{users}=1'
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(1, len(content['locations']))

    def test_get_with_filter_rewrites(self):
        """Tests various filter rewrite scenarios"""
        urls = [
            '/locations/?filter{cats}=1',
            '/locations/?filter{friendly_cats}=1',
            '/locations/?filter{bad_cats}=1'
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(200, response.status_code)


class TestRelationsAPI(APITestCase):

    """Test auto-generated relation endpoints."""

    def setUp(self):
        self.fixture = create_fixture()

    def test_generated_relation_fields(self):
        r = self.client.get('/users/1/location/')
        self.assertEqual(200, r.status_code)

        r = self.client.get('/users/1/permissions/')
        self.assertEqual(200, r.status_code)

        r = self.client.get('/users/1/groups/')
        self.assertEqual(200, r.status_code)

        # Not a relation field
        r = self.client.get('/users/1/name/')
        self.assertEqual(404, r.status_code)

    def test_location_users_relations_identical_to_sideload(self):
        r1 = self.client.get('/locations/1/?include[]=users.')
        self.assertEqual(200, r1.status_code)
        r1_data = json.loads(r1.content.decode('utf-8'))

        r2 = self.client.get('/locations/1/users/')
        self.assertEqual(200, r2.status_code)
        r2_data = json.loads(r2.content.decode('utf-8'))

        self.assertEqual(r2_data['users'], r1_data['users'])

    def test_relation_includes(self):
        r = self.client.get('/locations/1/users/?include[]=location.')
        self.assertEqual(200, r.status_code)

        content = json.loads(r.content.decode('utf-8'))
        self.assertTrue('locations' in content)

    def test_relation_excludes(self):
        r = self.client.get('/locations/1/users/?exclude[]=location')
        self.assertEqual(200, r.status_code)
        content = json.loads(r.content.decode('utf-8'))

        self.assertFalse('location' in content['users'][0])

    def test_relation_filter_returns_error(self):
        r = self.client.get('/locations/1/users/?filter{name}=foo')
        self.assertEqual(400, r.status_code)


class TestUserLocationsAPI(APITestCase):

    """
    Test API on serializer with embedded fields.
    """

    def setUp(self):
        self.fixture = create_fixture()

    def test_get_embedded(self):
        with self.assertNumQueries(3):
            url = '/v1/user_locations/1/'
            response = self.client.get(url)

        self.assertEqual(200, response.status_code)
        content = json.loads(response.content.decode('utf-8'))
        groups = content['user_location']['groups']
        location = content['user_location']['location']
        self.assertEqual(content['user_location']['location']['name'], '0')
        self.assertTrue(isinstance(groups[0], dict))
        self.assertTrue(isinstance(location, dict))


class TestLinks(APITestCase):

    def setUp(self):
        self.fixture = create_fixture()

        home = Location.objects.create()
        hunting_ground = Location.objects.create()
        self.cat = Cat.objects.create(
            name='foo',
            home=home,
            backup_home=hunting_ground
        )
        self.cat.hunting_grounds.add(hunting_ground)

    def test_deferred_relations_have_links(self):
        r = self.client.get('/v2/cats/1/')
        self.assertEqual(200, r.status_code)
        content = json.loads(r.content.decode('utf-8'))

        cat = content['cat']
        self.assertTrue('links' in cat)

        # 'home' has link=None set so should not have a link object
        self.assertTrue('home' not in cat['links'])

        # test for default link (auto-generated relation endpoint)
        # Note that the pluralized name is used rather than the full prefix.
        self.assertEqual(cat['links']['foobar'], '/cats/1/foobar/')

        # test for dynamically generated link URL
        cat1 = Cat.objects.get(pk=1)
        self.assertEqual(
            cat['links']['backup_home'],
            '/locations/%s/?include[]=address' % cat1.backup_home.pk
        )

    def test_including_empty_relation_hides_link(self):
        r = self.client.get('/v2/cats/1/?include[]=foobar')
        self.assertEqual(200, r.status_code)
        content = json.loads(r.content.decode('utf-8'))

        # 'foobar' is included but empty, so don't return a link
        cat = content['cat']
        self.assertFalse(cat['foobar'])
        self.assertFalse('foobar' in cat['links'])

    def test_including_non_empty_many_relation_has_link(self):
        r = self.client.get('/v2/cats/%s/?include[]=foobar' % self.cat.pk)
        self.assertEqual(200, r.status_code)
        content = json.loads(r.content.decode('utf-8'))
        cat = content['cat']
        self.assertTrue('foobar' in cat)
        self.assertTrue('foobar' in cat['links'])

    def test_no_links_for_included_single_relations(self):
        url = '/v2/cats/%s/?include[]=home' % self.cat.pk
        r = self.client.get(url)
        self.assertEqual(200, r.status_code)
        content = json.loads(r.content.decode('utf-8'))

        cat = content['cat']
        self.assertTrue('home' in cat)
        self.assertFalse('home' in cat['links'])

    def test_sideloading_relation_hides_link(self):
        url = '/v2/cats/%s/?include[]=foobar.' % self.cat.pk
        r = self.client.get(url)
        self.assertEqual(200, r.status_code)
        content = json.loads(r.content.decode('utf-8'))

        cat = content['cat']
        self.assertTrue('foobar' in cat)
        self.assertTrue('locations' in content)  # check for sideload
        self.assertFalse('foobar' in cat['links'])  # no link

    def test_one_to_one_dne(self):
        user = User.objects.create(name='foo', last_name='bar')

        url = '/users/%s/profile/' % user.pk
        r = self.client.get(url)
        self.assertEqual(200, r.status_code)
        # Check error message to differentiate from a routing error 404
        content = json.loads(r.content.decode('utf-8'))
        self.assertEqual({}, content)

    def test_ephemeral_object_link(self):

        class FakeCountObject(object):
            pk = 1
            values = []

        class FakeNested(object):
            value_count = FakeCountObject()

        szr = NestedEphemeralSerializer()
        data = szr.to_representation(FakeNested())
        self.assertEqual(data, {'value_count': 1}, data)

    def test_meta_read_only_relation_field(self):
        """Test for making a DynamicRelationField read-only by adding
        it to Meta.read_only_fields.
        """
        data = {
            'name': 'test ro',
            'last_name': 'last',
            'location': 1,
            'profile': 'bogus value',  # Read only relation field
        }
        response = self.client.post(
            '/users/', json.dumps(data),
            content_type='application/json'
        )
        # Note: if 'profile' isn't getting ignored, this will return
        # a 404 since a matching Profile object isn't found.
        self.assertEquals(201, response.status_code)


class TestDogsAPI(APITestCase):

    """
    Tests for sorting
    """

    def setUp(self):
        self.fixture = create_fixture()

    def test_sort(self):
        url = '/dogs/?sort[]=name'
        # 2 queries - one for getting dogs, one for the meta (count)
        with self.assertNumQueries(2):
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        expected_response = [{
            'id': 2,
            'name': 'Air-Bud',
            'origin': 'Air Bud 4: Seventh Inning Fetch',
            'fur': 'gold'
        }, {
            'id': 1,
            'name': 'Clifford',
            'origin': 'Clifford the big red dog',
            'fur': 'red'
        }, {
            'id': 4,
            'name': 'Pluto',
            'origin': 'Mickey Mouse',
            'fur': 'brown and white'
        }, {
            'id': 3,
            'name': 'Spike',
            'origin': 'Rugrats',
            'fur': 'brown'
        }, {
            'id': 5,
            'name': 'Spike',
            'origin': 'Tom and Jerry',
            'fur': 'light-brown'
        }]
        actual_response = json.loads(
            response.content.decode('utf-8')).get('dogs')
        self.assertEquals(expected_response, actual_response)

    def test_sort_reverse(self):
        url = '/dogs/?sort[]=-name'
        # 2 queries - one for getting dogs, one for the meta (count)
        with self.assertNumQueries(2):
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        expected_response = [{
            'id': 3,
            'name': 'Spike',
            'origin': 'Rugrats',
            'fur': 'brown'
        }, {
            'id': 5,
            'name': 'Spike',
            'origin': 'Tom and Jerry',
            'fur': 'light-brown'
        }, {
            'id': 4,
            'name': 'Pluto',
            'origin': 'Mickey Mouse',
            'fur': 'brown and white'
        }, {
            'id': 1,
            'name': 'Clifford',
            'origin': 'Clifford the big red dog',
            'fur': 'red'
        }, {
            'id': 2,
            'name': 'Air-Bud',
            'origin': 'Air Bud 4: Seventh Inning Fetch',
            'fur': 'gold'
        }]
        actual_response = json.loads(
            response.content.decode('utf-8')).get('dogs')
        self.assertEquals(expected_response, actual_response)

    def test_sort_multiple(self):
        url = '/dogs/?sort[]=-name&sort[]=-origin'
        # 2 queries - one for getting dogs, one for the meta (count)
        with self.assertNumQueries(2):
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        expected_response = [{
            'id': 5,
            'name': 'Spike',
            'origin': 'Tom and Jerry',
            'fur': 'light-brown'
        }, {
            'id': 3,
            'name': 'Spike',
            'origin': 'Rugrats',
            'fur': 'brown'
        }, {
            'id': 4,
            'name': 'Pluto',
            'origin': 'Mickey Mouse',
            'fur': 'brown and white'
        }, {
            'id': 1,
            'name': 'Clifford',
            'origin': 'Clifford the big red dog',
            'fur': 'red'
        }, {
            'id': 2,
            'name': 'Air-Bud',
            'origin': 'Air Bud 4: Seventh Inning Fetch',
            'fur': 'gold'
        }]
        actual_response = json.loads(
            response.content.decode('utf-8')).get('dogs')
        self.assertEquals(expected_response, actual_response)

    def test_sort_rewrite(self):
        url = '/dogs/?sort[]=fur'
        # 2 queries - one for getting dogs, one for the meta (count)
        with self.assertNumQueries(2):
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)
        expected_response = [{
            'id': 3,
            'name': 'Spike',
            'origin': 'Rugrats',
            'fur': 'brown'
        }, {
            'id': 4,
            'name': 'Pluto',
            'origin': 'Mickey Mouse',
            'fur': 'brown and white'
        }, {
            'id': 2,
            'name': 'Air-Bud',
            'origin': 'Air Bud 4: Seventh Inning Fetch',
            'fur': 'gold'
        }, {
            'id': 5,
            'name': 'Spike',
            'origin': 'Tom and Jerry',
            'fur': 'light-brown'
        }, {
            'id': 1,
            'name': 'Clifford',
            'origin': 'Clifford the big red dog',
            'fur': 'red'
        }]
        actual_response = json.loads(
            response.content.decode('utf-8')).get('dogs')
        self.assertEquals(expected_response, actual_response)

    def test_sort_invalid(self):
        url = '/horses?sort[]=borigin'
        response = self.client.get(url)

        # expected server to throw a 400 if an incorrect
        # sort field is specified
        self.assertEquals(400, response.status_code)


class TestHorsesAPI(APITestCase):

    """
    Tests for sorting on default fields and limit sorting fields
    """

    def setUp(self):
        self.fixture = create_fixture()

    def test_sort(self):
        url = '/horses'
        # 1 query - one for getting horses
        # (the viewset as features specified, so no meta is returned)
        with self.assertNumQueries(1):
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)

        # expect the default for horses to be sorted by -name
        expected_response = {
            'horses': [{
                'id': 2,
                'name': 'Secretariat',
                'origin': 'Kentucky'
            }, {
                'id': 1,
                'name': 'Seabiscuit',
                'origin': 'LA'
            }]
        }
        actual_response = json.loads(response.content.decode('utf-8'))
        self.assertEquals(expected_response, actual_response)

    def test_sort_with_field_not_allowed(self):
        url = '/horses?sort[]=origin'
        response = self.client.get(url)

        # if `ordering_fields` are specified in the viewset, only allow sorting
        # based off those fields. If a field is listed in the url that is not
        # specified, return a 400
        self.assertEquals(400, response.status_code)


class TestZebrasAPI(APITestCase):

    """
    Tests for sorting on when ordering_fields is __all__
    """

    def setUp(self):
        self.fixture = create_fixture()

    def test_sort(self):
        url = '/zebras?sort[]=-name'
        # 1 query - one for getting zebras
        # (the viewset as features specified, so no meta is returned)
        with self.assertNumQueries(1):
            response = self.client.get(url)
        self.assertEquals(200, response.status_code)

        # expect sortable on any field on horses because __all__ is specified
        expected_response = {
            'zebras': [{
                'id': 2,
                'name': 'Ted',
                'origin': 'africa'
            }, {
                'id': 1,
                'name': 'Ralph',
                'origin': 'new york'
            }]
        }
        actual_response = json.loads(response.content.decode('utf-8'))
        self.assertEquals(expected_response, actual_response)


class TestBrowsableAPI(APITestCase):

    """
    Tests for Browsable API directory
    """

    def test_get_root(self):
        response = self.client.get('/?format=api')
        content = response.content.decode('utf-8')
        self.assertIn('directory', content)
        self.assertIn('/horses', content)
        self.assertIn('/zebras', content)
        self.assertIn('/users', content)

    def test_get_list(self):
        response = self.client.get('/users/?format=api')
        content = response.content.decode('utf-8')
        self.assertIn('directory', content)
        self.assertIn('/horses', content)
        self.assertIn('/zebras', content)
        self.assertIn('/users', content)
