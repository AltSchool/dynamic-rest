from collections import OrderedDict
from django.test import TestCase
from dynamic_rest.serializers import EphemeralObject
from tests.serializers import (
    UserSerializer, GroupSerializer, LocationGroupSerializer,
    CountsSerializer
)
from tests.setup import create_fixture


class TestUserSerializer(TestCase):

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
