from django.test import TestCase
from django.test.client import RequestFactory

from rest_framework import exceptions
from rest_framework.request import (
    MergeDict,
    Request
)
from dynamic_rest.filters import DynamicFilterBackend, FilterNode
from tests.viewsets import UserViewSet
from tests.serializers import GroupSerializer


class TestUserViewSet(TestCase):

    def setUp(self):
        self.view = UserViewSet()
        self.rf = RequestFactory()

    def testGetRequestFields(self):
        request = Request(self.rf.get('/users/', {
            'include[]': ['name', 'groups.permissions'],
            'exclude[]': ['groups.name']
        }))
        self.view.request = request
        fields = self.view.get_request_fields()

        self.assertEqual({
            'groups': {
                'name': False,
                'permissions': True
            },
            'name': True
        }, fields)

    def testGetRequestFieldsDisabled(self):
        self.view.features = (self.view.INCLUDE)
        request = Request(self.rf.get('/users/', {
            'include[]': ['name', 'groups'],
            'exclude[]': ['groups.name']
        }))
        self.view.request = request
        fields = self.view.get_request_fields()

        self.assertEqual({
            'groups': True,
            'name': True
        }, fields)

    def testInvalidRequestFields(self):
        for invalid_field in ('groups..name', 'groups..'):
            request = Request(
                self.rf.get('/users/', {'include[]': [invalid_field]}))
            self.view.request = request
            self.assertRaises(
                exceptions.ParseError,
                self.view.get_request_fields)

    def testFilterExtraction(self):
        filters_map = {
            'attr': ['bar'],
            'attr2.eq': ['bar'],
            '-attr3': ['bar'],
            'rel|attr1': ['val'],
            '-rel|attr2': ['val'],
            'rel.attr': ['baz'],
            'rel.bar|attr': ['val'],
            'attr4.lt': ['val'],
            'attr5.in': ['val1', 'val2', 'val3'],
        }

        backend = DynamicFilterBackend()
        out = backend._extract_filters(filters_map=filters_map)
        self.assertEqual(out['_include']['attr'].value, 'bar')
        self.assertEqual(out['_include']['attr2'].value, 'bar')
        self.assertEqual(out['_exclude']['attr3'].value, 'bar')
        self.assertEqual(out['rel']['_include']['attr1'].value, 'val')
        self.assertEqual(out['rel']['_exclude']['attr2'].value, 'val')
        self.assertEqual(out['_include']['rel__attr'].value, 'baz')
        self.assertEqual(out['rel']['bar']['_include']['attr'].value, 'val')
        self.assertEqual(out['_include']['attr4__lt'].value, 'val')
        self.assertEqual(len(out['_include']['attr5__in'].value), 3)

    def testIsNullCasting(self):
        filters_map = {
            'f1.isnull': [True],
            'f2.isnull': [['a']],
            'f3.isnull': ['true'],
            'f4.isnull': ['1'],
            'f5.isnull': [1],
            'f6.isnull': [False],
            'f7.isnull': [[]],
            'f8.isnull': ['false'],
            'f9.isnull': ['0'],
            'f10.isnull': [0],
            'f11.isnull': [''],
            'f12.isnull': [None],
        }

        backend = DynamicFilterBackend()
        out = backend._extract_filters(filters_map=filters_map)

        self.assertEqual(out['_include']['f1__isnull'].value, True)
        self.assertEqual(out['_include']['f2__isnull'].value, ['a'])
        self.assertEqual(out['_include']['f3__isnull'].value, True)
        self.assertEqual(out['_include']['f4__isnull'].value, True)
        self.assertEqual(out['_include']['f5__isnull'].value, 1)

        self.assertEqual(out['_include']['f6__isnull'].value, False)
        self.assertEqual(out['_include']['f7__isnull'].value, [])
        self.assertEqual(out['_include']['f8__isnull'].value, False)
        self.assertEqual(out['_include']['f9__isnull'].value, False)
        self.assertEqual(out['_include']['f10__isnull'].value, False)
        self.assertEqual(out['_include']['f11__isnull'].value, False)
        self.assertEqual(out['_include']['f12__isnull'].value, None)

    def testNestedFilterRewrite(self):
        node = FilterNode(['members', 'id'], 'in', [1])
        gs = GroupSerializer(include_fields='*')
        filter_key = node.generate_query_key(gs)
        self.assertEqual(filter_key, 'users__id__in')


class TestMergeDictConvertsToDict(TestCase):

    def setUp(self):
        self.view = UserViewSet()
        self.rf = RequestFactory()

    def testMergeDictRequest(self):
        data = {
            'name': 'test'
        }
        request = Request(self.rf.post('/users/', data))
        # force data to be a MergeDict
        request._data = MergeDict(request.data)
        view_request = self.view.dispatch(request)
        self.assertIsInstance(view_request.data, dict)
        self.assertNotIsInstance(view_request.data, MergeDict)
