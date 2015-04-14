from django.test import TestCase
from django.test.client import RequestFactory

from rest_framework import exceptions
from rest_framework.request import Request
from dynamic_rest.filters import DynamicFilterBackend
from tests.viewsets import UserViewSet


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

        self.assertEqual(out['_include']['attr'], 'bar')
        self.assertEqual(out['_include']['attr2'], 'bar')
        self.assertEqual(out['_exclude']['attr3'], 'bar')
        self.assertEqual(out['rel']['_include']['attr1'], 'val')
        self.assertEqual(out['rel']['_exclude']['attr2'], 'val')
        self.assertEqual(out['_include']['rel__attr'], 'baz')
        self.assertEqual(out['rel']['bar']['_include']['attr'], 'val')
        self.assertEqual(out['_include']['attr4__lt'], 'val')
        self.assertEqual(len(out['_include']['attr5__in']), 3)
