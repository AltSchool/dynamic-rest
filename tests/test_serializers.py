from collections import OrderedDict
from django.test import TestCase

from dynamic_rest.fields import DynamicRelationField
from dynamic_rest.serializers import EphemeralObject, DynamicListSerializer
from tests.serializers import (
    UserSerializer, GroupSerializer, LocationGroupSerializer,
    CountsSerializer, NestedEphemeralSerializer,
    UserLocationSerializer, LocationSerializer
)
from tests.setup import create_fixture
from tests.models import User

# TODO(ant): move UserSerializer-specific tests
# into an integration test case and test serializer
# methods in a more generic way


class TestDynamicSerializer(TestCase):

    def setUp(self):
        self.fixture = create_fixture()
        self.maxDiff = None

    def testDefault(self):
        serializer = UserSerializer(
            self.fixture.users,
            many=True,
            sideload=True)
        self.assertEqual(serializer.data, {
            'users': [
                OrderedDict(
                    [('id', 1), ('name', u'0'), ('location', 1)]),
                OrderedDict(
                    [('id', 2), ('name', u'1'), ('location', 1)]),
                OrderedDict(
                    [('id', 3), ('name', u'2'), ('location', 2)]),
                OrderedDict(
                    [('id', 4), ('name', u'3'), ('location', 3)])
            ]
        })

    def testExtraField(self):
        request_fields = {
            'last_name': True
        }
        serializer = UserSerializer(
            self.fixture.users,
            many=True,
            request_fields=request_fields,
            sideload=True)
        self.assertEqual(serializer.data, {
            'users': [
                OrderedDict(
                    [('id', 1), ('name', u'0'),
                     ('location', 1), ('last_name', u'0')]),
                OrderedDict(
                    [('id', 2), ('name', u'1'),
                     ('location', 1), ('last_name', u'1')]),
                OrderedDict(
                    [('id', 3), ('name', u'2'),
                     ('location', 2), ('last_name', u'2')]),
                OrderedDict(
                    [('id', 4), ('name', u'3'),
                     ('location', 3), ('last_name', u'3')])
            ]
        })

    def testDeferredField(self):
        request_fields = {
            'location': False
        }
        serializer = UserSerializer(
            self.fixture.users,
            many=True,
            request_fields=request_fields,
            sideload=True)
        self.assertEqual(serializer.data, {
            'users': [
                OrderedDict(
                    [('id', 1), ('name', u'0')]),
                OrderedDict(
                    [('id', 2), ('name', u'1')]),
                OrderedDict(
                    [('id', 3), ('name', u'2')]),
                OrderedDict(
                    [('id', 4), ('name', u'3')])
            ]
        })

    def testNestedHasOne(self):
        request_fields = {
            'location': {}
        }
        serializer = UserSerializer(
            self.fixture.users,
            many=True,
            request_fields=request_fields,
            sideload=True)
        self.assertEqual(serializer.data, {
            'locations': [{
                'id': 1,
                'name': u'0'
            }, {
                'id': 2,
                'name': u'1'
            }, {
                'id': 3,
                'name': u'2'
            }],
            'users': [{
                'location': 1,
                'id': 1,
                'name': u'0'
            }, {
                'location': 1,
                'id': 2,
                'name': u'1'
            }, {
                'location': 2,
                'id': 3,
                'name': u'2'
            }, {
                'location': 3,
                'id': 4,
                'name': u'3'
            }]
        })

        serializer = UserSerializer(
            self.fixture.users[0],
            request_fields=request_fields,
            sideload=True)
        self.assertEqual(serializer.data, {
            'locations': [{
                'id': 1,
                'name': u'0'
            }],
            'user': {
                'location': 1,
                'id': 1,
                'name': u'0'
            }
        })

    def testNestedHasMany(self):
        request_fields = {
            'groups': {}
        }
        expected = {
            "users": [
                {
                    "id": 1,
                    "name": "0",
                    "groups": [
                        1,
                        2
                    ],
                    "location": 1
                },
                {
                    "id": 2,
                    "name": "1",
                    "groups": [
                        1,
                        2
                    ],
                    "location": 1
                },
                {
                    "id": 3,
                    "name": "2",
                    "groups": [
                        1,
                        2
                    ],
                    "location": 2
                },
                {
                    "id": 4,
                    "name": "3",
                    "groups": [
                        1,
                        2
                    ],
                    "location": 3
                }
            ],
            "groups": [
                {
                    "id": 1,
                    "name": "0"
                },
                {
                    "id": 2,
                    "name": "1"
                }
            ]
        }
        serializer = UserSerializer(
            self.fixture.users,
            many=True,
            request_fields=request_fields,
            sideload=True)
        self.assertEqual(serializer.data, expected)

        request_fields = {
            'members': {}
        }

        expected = {
            "users": [
                {
                    "id": 1,
                    "name": "0",
                    "location": 1
                },
                {
                    "id": 2,
                    "name": "1",
                    "location": 1
                },
                {
                    "id": 3,
                    "name": "2",
                    "location": 2
                },
                {
                    "id": 4,
                    "name": "3",
                    "location": 3
                }
            ],
            "groups": [
                {
                    "id": 1,
                    "name": "0",
                    "members": [
                        1,
                        2,
                        3,
                        4
                    ]
                },
                {
                    "id": 2,
                    "name": "1",
                    "members": [
                        1,
                        2,
                        3,
                        4
                    ]
                }
            ]
        }
        serializer = GroupSerializer(
            self.fixture.groups,
            many=True,
            request_fields=request_fields,
            sideload=True)
        self.assertEqual(serializer.data, expected)

    def testNestedExtraField(self):
        request_fields = {
            'groups': {
                'permissions': True
            }
        }

        serializer = UserSerializer(
            self.fixture.users,
            many=True,
            request_fields=request_fields,
            sideload=True)
        expected = {
            "users": [
                {
                    "id": 1,
                    "name": "0",
                    "groups": [
                        1,
                        2
                    ],
                    "location": 1
                },
                {
                    "id": 2,
                    "name": "1",
                    "groups": [
                        1,
                        2
                    ],
                    "location": 1
                },
                {
                    "id": 3,
                    "name": "2",
                    "groups": [
                        1,
                        2
                    ],
                    "location": 2
                },
                {
                    "id": 4,
                    "name": "3",
                    "groups": [
                        1,
                        2
                    ],
                    "location": 3
                }
            ],
            "groups": [
                {
                    "id": 1,
                    "name": "0",
                    "permissions": [
                        1
                    ]
                },
                {
                    "id": 2,
                    "name": "1",
                    "permissions": [
                        2
                    ]
                }
            ]
        }
        self.assertEqual(serializer.data, expected)

    def testNestedDeferredField(self):
        request_fields = {
            'groups': {
                'name': False
            }
        }
        serializer = UserSerializer(
            self.fixture.users,
            many=True,
            request_fields=request_fields,
            sideload=True)
        self.assertEqual(serializer.data, {
            'groups': [{
                'id': 1
            }, {
                'id': 2
            }],
            'users': [{
                'location': 1,
                'id': 1,
                'groups': [1, 2],
                'name': u'0'
            }, {
                'location': 1,
                'id': 2,
                'groups': [1, 2],
                'name': u'1'
            }, {
                'location': 2,
                'id': 3,
                'groups': [1, 2],
                'name': u'2'
            }, {
                'location': 3,
                'id': 4,
                'groups': [1, 2],
                'name': u'3'
            }]
        })

    def testGetAllFields(self):
        s = GroupSerializer()
        all_keys1 = s.get_all_fields().keys()
        f2 = s.fields
        all_keys2 = s.get_all_fields().keys()
        expected = ['id', 'name']
        self.assertEqual(f2.keys(), expected)
        self.assertEqual(all_keys1, all_keys2)

    def testOnlyFieldsForcesFields(self):
        expected = ['id', 'last_name']
        serializer = UserSerializer(only_fields=expected)
        self.assertEqual(serializer.fields.keys(), expected)

    def testOnlyFieldsRespectsSideloads(self):
        expected = ['id', 'permissions']
        serializer = UserSerializer(
            only_fields=expected,
            request_fields={
                'permissions': {}
            }
        )
        self.assertEqual(serializer.fields.keys(), expected)
        self.assertEqual(serializer.request_fields['permissions'], {})

    def testOnlyFieldsOverridesIncludeFields(self):
        expected = ['id', 'name']
        serializer = UserSerializer(
            only_fields=expected,
            include_fields=['permissions']
        )
        self.assertEqual(serializer.fields.keys(), expected)

    def testIncludeAllAddsAllFields(self):
        expected = UserSerializer().get_all_fields().keys()
        serializer = UserSerializer(
            include_fields='*'
        )
        self.assertEqual(serializer.fields.keys(), expected)

    def testIncludeAllOverridesExcludeFields(self):
        expected = UserSerializer().get_all_fields().keys()
        serializer = UserSerializer(
            include_fields='*',
            exclude_fields=['id']
        )
        self.assertEqual(serializer.fields.keys(), expected)

    def testIncludeFieldsAddsFields(self):
        include = ['permissions']
        expected = set(UserSerializer().get_fields().keys()) | set(include)
        serializer = UserSerializer(
            include_fields=include
        )
        self.assertEqual(set(serializer.fields.keys()), expected)

    def testIncludeFieldsRespectsSideloads(self):
        include = ['permissions']
        expected = set(UserSerializer().get_fields().keys()) | set(include)
        serializer = UserSerializer(
            include_fields=include,
            request_fields={
                'permissions': {}
            }
        )
        self.assertEqual(set(serializer.fields.keys()), expected)
        self.assertEqual(serializer.request_fields['permissions'], {})

    def testExcludeFieldsRemovesFields(self):
        exclude = ['id']
        expected = set(UserSerializer().get_fields().keys()) - set(exclude)
        serializer = UserSerializer(
            exclude_fields=exclude,
        )
        self.assertEqual(set(serializer.fields.keys()), expected)


class TestListSerializer(TestCase):

    def testGetNameProxiesToChild(self):
        serializer = UserSerializer(many=True)
        self.assertTrue(isinstance(serializer, DynamicListSerializer))
        self.assertEqual(serializer.get_name(), 'user')
        self.assertEqual(serializer.get_plural_name(), 'users')


class TestEphemeralSerializer(TestCase):

    def setUp(self):
        self.fixture = create_fixture()

    def testBasic(self):
        location = self.fixture.locations[0]
        data = {}
        data['pk'] = data['id'] = location.pk
        data['location'] = location
        data['groups'] = self.fixture.groups
        instance = EphemeralObject(data)
        data = LocationGroupSerializer(instance).data
        self.assertEqual(
            data, {'id': 1, 'groups': [1, 2], 'location': 1})

    def testCountFields(self):
        eo = EphemeralObject({'pk': 1, 'values': [1, 1, 2]})
        data = CountsSerializer(eo).data

        self.assertEqual(data['count'], 3)
        self.assertEqual(data['unique_count'], 2)

    def testCountNone(self):
        eo = EphemeralObject({'pk': 1, 'values': None})
        data = CountsSerializer(eo).data

        self.assertEqual(data['count'], None)
        self.assertEqual(data['unique_count'], None)

    def testCountException(self):
        eo = EphemeralObject({'pk': 1, 'values': {}})
        with self.assertRaises(TypeError):
            CountsSerializer(eo).data

    def testIdOnly(self):
        """ Test EphemeralSerializer.to_representation() in id_only mode """
        eo = EphemeralObject({'pk': 1, 'values': None})
        data = CountsSerializer(request_fields=True).to_representation(eo)

        self.assertEqual(data, eo.pk)

    def testNested(self):
        value_count = EphemeralObject({'pk': 1, 'values': []})
        nested = EphemeralObject({'pk': 1, 'value_count': value_count})
        data = NestedEphemeralSerializer(
            request_fields={'value_count': {}}).to_representation(nested)
        self.assertEqual(data['value_count']['count'], 0)

    def testNestedContext(self):
        s1 = LocationGroupSerializer(context={'foo': 'bar'})
        s2 = s1.fields['location'].serializer
        self.assertEqual(s2.context['foo'], 'bar')


class TestUserLocationSerializer(TestCase):

    def setUp(self):
        self.fixture = create_fixture()

    def testSerializerWithEmbed(self):
        data = UserLocationSerializer(
            self.fixture.users[0], sideload=True).data
        self.assertEqual(data['user_location']['location']['name'], '0')
        self.assertEqual(
            ["0", "1"],
            sorted([g['name'] for g in data['user_location']['groups']])
        )

    def testSerializerWithDeferredEmbed(self):
        # Make sure 'embed' fields can be deferred
        class UserDeferredLocationSerializer(UserLocationSerializer):
            class Meta:
                model = User
                name = 'user_deferred_location'
            location = DynamicRelationField(
                LocationSerializer, embed=True, deferred=True)

        data = UserDeferredLocationSerializer(
            self.fixture.users[0]).data
        self.assertFalse('location' in data)

        # Now include deferred embedded field
        data = UserDeferredLocationSerializer(
            self.fixture.users[0],
            request_fields={
                'id': True,
                'name': True,
                'location': True
            }).data
        self.assertTrue('location' in data)
        self.assertEqual(data['location']['name'], '0')
