from django.test import TestCase
from django.test.client import RequestFactory

from rest_framework import exceptions
from rest_framework.request import Request
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
    fields = self.view._get_request_fields()

    self.assertEqual({
      'groups': {
        'name': False,
        'permissions': True
      },
      'name': True
    }, fields)

  def testGetRequestFieldsDisabled(self):
    self.view._features = (self.view.INCLUDE)
    request = Request(self.rf.get('/users/', {
      'include[]': ['name', 'groups'],
      'exclude[]': ['groups.name']
    }))
    self.view.request = request
    fields = self.view._get_request_fields()

    self.assertEqual({
      'groups': True,
      'name': True
    }, fields)

  def testInvalidRequestFields(self):
    for invalid_field in ('groups..name', 'groups..'):
      request = Request(self.rf.get('/users/', {'include[]': [invalid_field]}))
      self.view.request = request
      self.assertRaises(exceptions.ParseError, self.view._get_request_fields)
