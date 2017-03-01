import unittest
from collections import OrderedDict

from django.test import TestCase, override_settings
from django.utils import six

from dynamic_rest.fields import DynamicRelationField
from dynamic_rest.serializers import DynamicListSerializer, EphemeralObject
from tests.models import User
from tests.serializers import (
    CatSerializer,
    CountsSerializer,
    DogSerializer,
    GroupSerializer,
    LocationGroupSerializer,
    LocationSerializer,
    NestedEphemeralSerializer,
    UserLocationSerializer,
    UserSerializer
)
from tests.setup import create_fixture


# TODO(ant): move UserSerializer-specific tests
# into an integration test case and test serializer
# methods in a more generic way

@override_settings(
    DYNAMIC_REST={
        'ENABLE_LINKS': False
    }
)
class TestDynamicSerializer(TestCase):

    def setUp(self):
        self.fixture = create_fixture()
        self.maxDiff = None

    def test_data_without_envelope(self):
        serializer = UserSerializer(
            self.fixture.users,
            many=True,
        )
        self.assertEqual(serializer.data, [
            OrderedDict(
                [('id', 1), ('name', '0'), ('location', 1)]),
            OrderedDict(
                [('id', 2), ('name', '1'), ('location', 1)]),
            OrderedDict(
                [('id', 3), ('name', '2'), ('location', 2)]),
            OrderedDict(
                [('id', 4), ('name', '3'), ('location', 3)])
        ])

    def test_data_with_envelope(self):
        serializer = UserSerializer(
            self.fixture.users,
            many=True,
            envelope=True
        )
        self.assertEqual(serializer.data, {
            'users': [
                OrderedDict(
                    [('id', 1), ('name', '0'), ('location', 1)]),
                OrderedDict(
                    [('id', 2), ('name', '1'), ('location', 1)]),
                OrderedDict(
                    [('id', 3), ('name', '2'), ('location', 2)]),
                OrderedDict(
                    [('id', 4), ('name', '3'), ('location', 3)])
            ]
        })

    def test_data_with_included_field(self):
        request_fields = {
            'last_name': True
        }
        serializer = UserSerializer(
            self.fixture.users,
            many=True,
            sideload=True,   # pending deprecation 1.6
            request_fields=request_fields,
        )
        self.assertEqual(serializer.data, {
            'users': [
                OrderedDict(
                    [('id', 1), ('name', '0'),
                     ('location', 1), ('last_name', '0')]),
                OrderedDict(
                    [('id', 2), ('name', '1'),
                     ('location', 1), ('last_name', '1')]),
                OrderedDict(
                    [('id', 3), ('name', '2'),
                     ('location', 2), ('last_name', '2')]),
                OrderedDict(
                    [('id', 4), ('name', '3'),
                     ('location', 3), ('last_name', '3')])
            ]
        })

    def test_data_with_excluded_field(self):
        request_fields = {
            'location': False
        }
        serializer = UserSerializer(
            self.fixture.users,
            many=True,
            envelope=True,
            request_fields=request_fields,
        )
        self.assertEqual(serializer.data, {
            'users': [
                OrderedDict(
                    [('id', 1), ('name', '0')]),
                OrderedDict(
                    [('id', 2), ('name', '1')]),
                OrderedDict(
                    [('id', 3), ('name', '2')]),
                OrderedDict(
                    [('id', 4), ('name', '3')])
            ]
        })

    def test_data_with_included_has_one(self):
        request_fields = {
            'location': {}
        }
        serializer = UserSerializer(
            self.fixture.users,
            many=True,
            envelope=True,
            request_fields=request_fields,
        )
        self.assertEqual(serializer.data, {
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
                'location': 1,
                'id': 1,
                'name': '0'
            }, {
                'location': 1,
                'id': 2,
                'name': '1'
            }, {
                'location': 2,
                'id': 3,
                'name': '2'
            }, {
                'location': 3,
                'id': 4,
                'name': '3'
            }]
        })

        serializer = UserSerializer(
            self.fixture.users[0],
            envelope=True,
            request_fields=request_fields,
        )
        self.assertEqual(serializer.data, {
            'locations': [{
                'id': 1,
                'name': '0'
            }],
            'user': {
                'location': 1,
                'id': 1,
                'name': '0'
            }
        })

    def test_data_with_included_has_many(self):
        request_fields = {
            'groups': {}
        }
        expected = {
            'users': [
                {
                    'id': 1,
                    'name': '0',
                    'groups': [
                        1,
                        2
                    ],
                    'location': 1
                },
                {
                    'id': 2,
                    'name': '1',
                    'groups': [
                        1,
                        2
                    ],
                    'location': 1
                },
                {
                    'id': 3,
                    'name': '2',
                    'groups': [
                        1,
                        2
                    ],
                    'location': 2
                },
                {
                    'id': 4,
                    'name': '3',
                    'groups': [
                        1,
                        2
                    ],
                    'location': 3
                }
            ],
            'groups': [
                {
                    'id': 1,
                    'name': '0'
                },
                {
                    'id': 2,
                    'name': '1'
                }
            ]
        }
        serializer = UserSerializer(
            self.fixture.users,
            many=True,
            envelope=True,
            request_fields=request_fields,
        )
        self.assertEqual(serializer.data, expected)

        request_fields = {
            'members': {}
        }

        expected = {
            'users': [
                {
                    'id': 1,
                    'name': '0',
                    'location': 1
                },
                {
                    'id': 2,
                    'name': '1',
                    'location': 1
                },
                {
                    'id': 3,
                    'name': '2',
                    'location': 2
                },
                {
                    'id': 4,
                    'name': '3',
                    'location': 3
                }
            ],
            'groups': [
                {
                    'id': 1,
                    'name': '0',
                    'members': [
                        1,
                        2,
                        3,
                        4
                    ]
                },
                {
                    'id': 2,
                    'name': '1',
                    'members': [
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
            envelope=True,
            request_fields=request_fields,
        )
        self.assertEqual(serializer.data, expected)

    def test_data_with_nested_include(self):
        request_fields = {
            'groups': {
                'permissions': True
            }
        }

        serializer = UserSerializer(
            self.fixture.users,
            many=True,
            envelope=True,
            request_fields=request_fields,
        )
        expected = {
            'users': [
                {
                    'id': 1,
                    'name': '0',
                    'groups': [
                        1,
                        2
                    ],
                    'location': 1
                },
                {
                    'id': 2,
                    'name': '1',
                    'groups': [
                        1,
                        2
                    ],
                    'location': 1
                },
                {
                    'id': 3,
                    'name': '2',
                    'groups': [
                        1,
                        2
                    ],
                    'location': 2
                },
                {
                    'id': 4,
                    'name': '3',
                    'groups': [
                        1,
                        2
                    ],
                    'location': 3
                }
            ],
            'groups': [
                {
                    'id': 1,
                    'name': '0',
                    'permissions': [
                        1
                    ]
                },
                {
                    'id': 2,
                    'name': '1',
                    'permissions': [
                        2
                    ]
                }
            ]
        }
        self.assertEqual(serializer.data, expected)

    def test_data_with_nested_exclude(self):
        request_fields = {
            'groups': {
                'name': False
            }
        }
        serializer = UserSerializer(
            self.fixture.users,
            many=True,
            envelope=True,
            request_fields=request_fields,
        )
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
                'name': '0'
            }, {
                'location': 1,
                'id': 2,
                'groups': [1, 2],
                'name': '1'
            }, {
                'location': 2,
                'id': 3,
                'groups': [1, 2],
                'name': '2'
            }, {
                'location': 3,
                'id': 4,
                'groups': [1, 2],
                'name': '3'
            }]
        })

    def test_get_all_fields(self):
        s = GroupSerializer()
        all_keys1 = six.iterkeys(s.get_all_fields())
        f2 = s.fields
        all_keys2 = six.iterkeys(s.get_all_fields())
        expected = ['id', 'name']
        self.assertEqual(list(six.iterkeys(f2)), expected)
        self.assertEqual(list(all_keys1), list(all_keys2))

    def test_get_fields_with_only_fields(self):
        expected = ['id', 'last_name']
        serializer = UserSerializer(only_fields=expected)
        self.assertEqual(list(six.iterkeys(serializer.fields)), expected)

    def test_get_fields_with_only_fields_and_request_fields(self):
        expected = ['id', 'permissions']
        serializer = UserSerializer(
            only_fields=expected,
            request_fields={
                'permissions': {}
            }
        )
        self.assertEqual(list(six.iterkeys(serializer.fields)), expected)
        self.assertEqual(serializer.request_fields['permissions'], {})

    def test_get_fields_with_only_fields_and_include_fields(self):
        expected = ['id', 'name']
        serializer = UserSerializer(
            only_fields=expected,
            include_fields=['permissions']
        )
        self.assertEqual(list(six.iterkeys(serializer.fields)), expected)

    def test_get_fields_with_include_all(self):
        expected = six.iterkeys(UserSerializer().get_all_fields())
        serializer = UserSerializer(
            include_fields='*'
        )
        self.assertEqual(list(six.iterkeys(serializer.fields)), list(expected))

    def test_get_fields_with_include_all_and_exclude(self):
        expected = six.iterkeys(UserSerializer().get_all_fields())
        serializer = UserSerializer(
            include_fields='*',
            exclude_fields=['id']
        )
        self.assertEqual(list(six.iterkeys(serializer.fields)), list(expected))

    def test_get_fields_with_include_fields(self):
        include = ['permissions']
        expected = set(
            six.iterkeys(UserSerializer().get_fields())
        ) | set(include)
        serializer = UserSerializer(
            include_fields=include
        )
        self.assertEqual(set(six.iterkeys(serializer.fields)), expected)

    def test_get_fields_with_include_fields_and_request_fields(self):
        include = ['permissions']
        expected = set(
            six.iterkeys(UserSerializer().get_fields())
        ) | set(include)
        serializer = UserSerializer(
            include_fields=include,
            request_fields={
                'permissions': {}
            }
        )
        self.assertEqual(set(six.iterkeys(serializer.fields)), expected)
        self.assertEqual(serializer.request_fields['permissions'], {})

    def test_get_fields_with_exclude_fields(self):
        exclude = ['id']
        expected = set(
            six.iterkeys(UserSerializer().get_fields())
        ) - set(exclude)
        serializer = UserSerializer(
            exclude_fields=exclude,
        )
        self.assertEqual(set(six.iterkeys(serializer.fields)), expected)

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

    def test_get_name_proxies_to_child(self):
        serializer = UserSerializer(many=True)
        self.assertTrue(isinstance(serializer, DynamicListSerializer))
        self.assertEqual(serializer.get_name(), 'user')
        self.assertEqual(serializer.get_plural_name(), 'users')


@override_settings(
    DYNAMIC_REST={
        'ENABLE_LINKS': False
    }
)
class TestEphemeralSerializer(TestCase):

    def setUp(self):
        self.fixture = create_fixture()

    def test_data(self):
        location = self.fixture.locations[0]
        data = {}
        data['pk'] = data['id'] = location.pk
        data['location'] = location
        data['groups'] = self.fixture.groups
        instance = EphemeralObject(data)
        data = LocationGroupSerializer(
            instance, envelope=True
        ).data['locationgroup']
        self.assertEqual(
            data, {'id': 1, 'groups': [1, 2], 'location': 1}
        )

    def test_data_count_field(self):
        eo = EphemeralObject({'pk': 1, 'values': [1, 1, 2]})
        data = CountsSerializer(eo, envelope=True).data['counts']

        self.assertEqual(data['count'], 3)
        self.assertEqual(data['unique_count'], 2)

    def test_data_count_field_returns_none_if_null_values(self):
        eo = EphemeralObject({'pk': 1, 'values': None})
        data = CountsSerializer(eo, envelope=True).data['counts']

        self.assertEqual(data['count'], None)
        self.assertEqual(data['unique_count'], None)

    def test_data_count_raises_exception_if_wrong_type(self):
        eo = EphemeralObject({'pk': 1, 'values': {}})
        with self.assertRaises(TypeError):
            CountsSerializer(eo, envelope=True).data

    def test_to_representation_if_id_only(self):
        ''' Test EphemeralSerializer.to_representation() in id_only mode '''
        eo = EphemeralObject({'pk': 1, 'values': None})
        data = CountsSerializer(request_fields=True).to_representation(eo)

        self.assertEqual(data, eo.pk)

    def test_to_representation_request_fields_nested(self):
        value_count = EphemeralObject({'pk': 1, 'values': []})
        nested = EphemeralObject({'pk': 1, 'value_count': value_count})
        data = NestedEphemeralSerializer(
            request_fields={'value_count': {}}).to_representation(nested)
        self.assertEqual(data['value_count']['count'], 0)

    def test_context_nested(self):
        s1 = LocationGroupSerializer(context={'foo': 'bar'})
        s2 = s1.fields['location'].serializer
        self.assertEqual(s2.context['foo'], 'bar')


class TestUserLocationSerializer(TestCase):

    def setUp(self):
        self.fixture = create_fixture()

    def test_data_with_embed(self):
        data = UserLocationSerializer(
            self.fixture.users[0],
            envelope=True
        ).data
        self.assertEqual(data['user_location']['location']['name'], '0')
        self.assertEqual(
            ['0', '1'],
            sorted([g['name'] for g in data['user_location']['groups']])
        )

    def test_data_with_embed_deferred(self):
        # Make sure 'embed' fields can be deferred
        class UserDeferredLocationSerializer(UserLocationSerializer):

            class Meta:
                model = User
                name = 'user_deferred_location'
                fields = (
                    'id',
                    'name',
                    'location',
                )
            location = DynamicRelationField(
                LocationSerializer, embed=True, deferred=True
            )

        data = UserDeferredLocationSerializer(
            self.fixture.users[0],
            envelope=True
        ).data
        self.assertFalse('location' in data)

        # Now include deferred embedded field
        data = UserDeferredLocationSerializer(
            self.fixture.users[0],
            request_fields={
                'id': True,
                'name': True,
                'location': True
            },
            envelope=True
        ).data['user_deferred_location']
        self.assertTrue('location' in data)
        self.assertEqual(data['location']['name'], '0')

    @override_settings(
        DYNAMIC_REST={
            'DEFER_MANY_RELATIONS': False,
        }
    )
    def test_data_with_many_deferred(self):
        class UserDeferredLocationSerializer(UserLocationSerializer):

            class Meta:
                defer_many_relations = True
                model = User
                name = 'user_deferred_location'
                fields = (
                    'id',
                    'name',
                    'groups',
                )
            groups = DynamicRelationField('GroupSerializer', many=True)

        data = UserDeferredLocationSerializer(
            self.fixture.users[0]).data
        self.assertFalse('groups' in data)

        # Now include deferred embedded field
        data = UserDeferredLocationSerializer(
            self.fixture.users[0],
            request_fields={
                'id': True,
                'name': True,
                'groups': True
            },
            envelope=True
        ).data['user_deferred_location']
        self.assertTrue('groups' in data)

    @override_settings(
        DYNAMIC_REST={
            'DEFER_MANY_RELATIONS': True,
        }
    )
    def test_data_with_many_not_deferred(self):
        class UserDeferredLocationSerializer(UserLocationSerializer):

            class Meta:
                defer_many_relations = False
                model = User
                name = 'user_deferred_location'
                fields = (
                    'groups',
                )
            groups = DynamicRelationField('GroupSerializer', many=True)

        data = UserDeferredLocationSerializer(
            self.fixture.users[0],
            envelope=True
        ).data['user_deferred_location']
        self.assertTrue('groups' in data)


@override_settings(
    DYNAMIC_REST={
        'ENABLE_SERIALIZER_CACHE': True
    }
)
class TestSerializerCaching(TestCase):

    def setUp(self):
        self.serializer = CatSerializer(
            request_fields={'home': {}, 'backup_home': True}
        )

    def test_get_all_fields(self):
        all_fields = self.serializer.get_all_fields()

        # These are two different instances of the field object
        # because get_all_fields() does a copy().
        home_field_1 = self.serializer.fields['home']
        home_field_2 = all_fields['home']

        self.assertNotEqual(
            home_field_1,
            home_field_2,
            'Expected different field instances, got same.'
        )

        self.assertEqual(
            home_field_1.serializer,
            home_field_2.serializer,
            'Expected same serializer instance, got different.'
        )

    def test_serializer_args_busts_cache(self):
        home_field = self.serializer.fields['home']

        self.assertIsNot(
            home_field.get_serializer(),
            home_field.get_serializer('foo'),
            (
                'Passing arg to get_serializer should construct new'
                ' serializer. Instead got same one.'
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
                'Different fields that use same serializer should get',
                ' separate serializer instances.'
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
            'Different root serializers should yield different instances.'
        )

    @unittest.skip(
        "skipping because DRF's Field.root doesn't have cycle-detection."
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


class TestMeta(TestCase):

    def test_default_name(self):
        serializer = DogSerializer()
        if hasattr(serializer.Meta, 'name'):
            # bust cached value
            del(serializer.Meta.name)
        self.assertFalse(hasattr(serializer.Meta, 'name'))
        self.assertEqual('dog', serializer.get_name())

    def test_default_plural_name(self):
        serializer = DogSerializer()
        if hasattr(serializer.Meta, 'plural_name'):
            # bust cached value
            del(serializer.Meta.plural_name)
        self.assertFalse(hasattr(serializer.Meta, 'plural_name'))
        self.assertEqual('dogs', serializer.get_plural_name())
