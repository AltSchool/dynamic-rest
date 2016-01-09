from collections import OrderedDict
from django.conf import settings
from django.test import TestCase

from dynamic_rest.fields import DynamicRelationField
from dynamic_rest.serializers import EphemeralObject, DynamicListSerializer
from tests.serializers import (
    UserSerializer, GroupSerializer, LocationGroupSerializer,
    CountsSerializer, NestedEphemeralSerializer,
    UserLocationSerializer, LocationSerializer,
    CatSerializer
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
        settings.DYNAMIC_REST['ENABLE_LINKS'] = False

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

    def test_serializer_propagation_consistency(self):
        s = CatSerializer(
            request_fields={'home': True}
        )

        # In version <= 1.3.7 these will have returned different values.
        r1 = s.get_all_fields()['home'].serializer.id_only()
        r2 = s.fields['home'].serializer.id_only()
        r3 = s.get_all_fields()['home'].serializer.id_only()
        self.assertEqual(r1, r2)
        self.assertEqual(r2, r3)


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


class TestSerializerCaching(TestCase):

    def setUp(self):
        self.serializer = CatSerializer(
            request_fields={'home': {}, 'backup_home': True}
        )
        settings.DYNAMIC_REST['ENABLE_SERIALIZER_CACHE'] = True

    def test_basic(self):
        all_fields = self.serializer.get_all_fields()

        # These are two different instances of the field object
        # because get_all_fields() does a copy().
        home_field_1 = self.serializer.fields['home']
        home_field_2 = all_fields['home']

        self.assertNotEqual(
            home_field_1,
            home_field_2,
            "Expected different field instances, got same."
        )

        self.assertEqual(
            home_field_1.serializer,
            home_field_2.serializer,
            "Expected same serializer instance, got different."
        )

    def test_serializer_args_busts_cache(self):
        home_field = self.serializer.fields['home']

        self.assertIsNot(
            home_field.get_serializer(),
            home_field.get_serializer('foo'),
            (
                "Passing arg to get_serializer should construct new"
                " serializer. Instead got same one."
            )
        )

    def test_same_serializer_class_different_fields(self):
        # These two use the same serializer class, but are different
        # fields, so they should use different serializer instances.
        home_field = self.serializer.fields['home']
        backup_home_field = self.serializer.fields['backup_home']

        self.assertIsNot(
            home_field.serializer,
            backup_home_field.serializer,
            (
                "Different fields that use same serializer should get",
                " separate serializer instances."
            )
        )

    def test_different_roots(self):
        serializer2 = CatSerializer(
            request_fields={'home': {}, 'backup_home': {}}
        )

        home1 = self.serializer.fields['home']
        home2 = serializer2.fields['home']

        self.assertIsNot(
            home1.serializer,
            home2.serializer,
            "Different root serializers should yield different instances."
        )

    def test_root_serializer_cycle_busting(self):
        s = CatSerializer(
            request_fields={'home': {}, 'backup_home': {}}
        )

        s.parent = s  # Create cycle.

        self.assertIsNone(s.fields['home'].root_serializer)

    def test_root_serializer_trickledown_request_fields(self):
        s = CatSerializer(
            request_fields=True
        )

        self.assertIsNotNone(s.get_all_fields()['home'].serializer)

    def test_recursive_serializer(self):
        s = LocationSerializer(
            request_fields={
                'cats': {
                    'parent': {
                        'parent': True
                    }
                }
            }
        )

        cats_field = s.get_all_fields()['cats']

        l1 = cats_field.serializer.child  # .child because list
        l2 = l1.get_all_fields()['parent'].serializer
        l3 = l2.get_all_fields()['parent'].serializer
        l4 = l3.get_all_fields()['parent'].serializer
        self.assertIsNot(l2, l3)

        # l3 and l4 should be same cached instance because both have
        # request_fields=True (l3 by inheritence, l4 by default)
        self.assertIs(l3, l4)
