from collections import OrderedDict
from django.test import TestCase
from tests.models import *
from tests.serializers import *
from tests.setup import create_fixture


class TestUserSerializer(TestCase):

  def setUp(self):
    self.fixture = create_fixture()
    self.maxDiff = None

  def testDefault(self):
    serializer = UserSerializer(self.fixture.users, many=True)
    self.assertEqual({
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
    }, serializer.data)

  def testExtraField(self):
    context = {
      'request_fields': {
        'last_name': True
      }
    }
    serializer = UserSerializer(self.fixture.users, many=True, context=context)
    self.assertEqual({
      'users': [
        OrderedDict(
            [('id', 1), ('name', u'0'), ('location', 1), ('last_name', u'0')]),
        OrderedDict(
            [('id', 2), ('name', u'1'), ('location', 1), ('last_name', u'1')]),
        OrderedDict(
            [('id', 3), ('name', u'2'), ('location', 2), ('last_name', u'2')]),
        OrderedDict(
            [('id', 4), ('name', u'3'), ('location', 3), ('last_name', u'3')])
      ]
    }, serializer.data)

  def testDeferredField(self):
    context = {
      'request_fields': {
        'location': False
      }
    }
    serializer = UserSerializer(self.fixture.users, many=True, context=context)
    self.assertEqual({
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
    }, serializer.data)

  def testNestedHasOne(self):
    context = {
      'request_fields': {
        'location': {}
      }
    }
    serializer = UserSerializer(self.fixture.users, many=True, context=context, sideload=False)
    self.assertEqual({
      'users': [
        OrderedDict([('id', 1), ('name', u'0'), ('location',
          OrderedDict([('id', 1), ('name', u'0')]))]),
        OrderedDict([('id', 2), ('name', u'1'), ('location',
          OrderedDict([('id', 1), ('name', u'0')]))]),
        OrderedDict([('id', 3), ('name', u'2'), ('location',
          OrderedDict([('id', 2), ('name', u'1')]))]),
        OrderedDict([('id', 4), ('name', u'3'), ('location',
          OrderedDict([('id', 3), ('name', u'2')]))])
      ]
    }, serializer.data)

  def testNestedHasMany(self):
    context = {
      'request_fields': {
        'groups': {}
      }
    }
    serializer = UserSerializer(self.fixture.users, many=True, context=context, sideload=False)
    self.assertEqual({
      'users': [
        OrderedDict([('id', 1), ('name', u'0'), ('groups', [
          OrderedDict([('id', 1), ('name', u'0')]),
          OrderedDict([('id', 2), ('name', u'1')])]), ('location', 1)]),
        OrderedDict([('id', 2), ('name', u'1'), ('groups', [
          OrderedDict([('id', 1), ('name', u'0')]),
          OrderedDict([('id', 2), ('name', u'1')])]),('location', 1)]),
        OrderedDict([('id', 3), ('name', u'2'), ('groups', [
          OrderedDict([('id', 1), ('name', u'0')]),
          OrderedDict([('id', 2), ('name', u'1')])]), ('location', 2)]),
        OrderedDict([('id', 4), ('name', u'3'), ('groups', [
          OrderedDict([('id', 1), ('name', u'0')]),
          OrderedDict([('id', 2),('name', u'1')])]), ('location', 3)])
      ]
    }, serializer.data)


    context = {
      'request_fields': {
        'members': {}
      }
    }
    serializer = GroupSerializer(self.fixture.groups, many=True, context=context, sideload=False)
    self.assertEqual({
      'groups': [
        OrderedDict([('id', 1), ('name', u'0'), ('members', [
          OrderedDict([('id', 1), ('name', u'0'), ('location', 1)]),
          OrderedDict([('id', 2), ('name', u'1'), ('location', 1)]),
          OrderedDict([('id', 3), ('name', u'2'), ('location', 2)]),
          OrderedDict([('id', 4), ('name', u'3'), ('location', 3)])
        ])]),
        OrderedDict([('id', 2), ('name', u'1'), ('members', [
          OrderedDict([('id', 1), ('name', u'0'), ('location', 1)]),
          OrderedDict([('id', 2), ('name', u'1'), ('location', 1)]),
          OrderedDict([('id', 3), ('name', u'2'), ('location', 2)]),
          OrderedDict([('id', 4), ('name', u'3'), ('location', 3)])
        ])])
      ]
    }, serializer.data)

  def testNestedExtraField(self):
    context = {
      'request_fields': {
        'groups': {
          'permissions': True
        }
      }
    }
    serializer = UserSerializer(self.fixture.users, many=True, context=context, sideload=False)
    self.assertEqual({
      'users': [
        OrderedDict([('id', 1), ('name', u'0'), ('groups', [
          OrderedDict([('id', 1), ('name', u'0'), ('permissions', [1])]),
          OrderedDict([('id', 2), ('name', u'1'), ('permissions', [2])])]), ('location', 1)]),
        OrderedDict([('id', 2), ('name', u'1'), ('groups', [
          OrderedDict([('id', 1), ('name', u'0'), ('permissions', [1])]),
          OrderedDict([('id', 2), ('name', u'1'), ('permissions', [2])])]), ('location', 1)]),
        OrderedDict([('id', 3), ('name', u'2'), ('groups', [
          OrderedDict([('id', 1), ('name', u'0'), ('permissions', [1])]),
          OrderedDict([('id', 2), ('name', u'1'), ('permissions', [2])])]), ('location', 2)]),
        OrderedDict([('id', 4), ('name', u'3'), ('groups', [
          OrderedDict([('id', 1), ('name', u'0'), ('permissions', [1])]),
          OrderedDict([('id', 2), ('name', u'1'), ('permissions', [2])])]), ('location', 3)])
      ]
    }, serializer.data)

  def testNestedDeferredField(self):
    context = {
      'request_fields': {
        'groups': {
          'name': False
        }
      }
    }
    serializer = UserSerializer(self.fixture.users, many=True, context=context, sideload=False)
    self.assertEqual({
      'users': [
        OrderedDict([('id', 1), ('name', u'0'), ('groups', [
          OrderedDict([('id', 1)]),
          OrderedDict([('id', 2)])]), ('location', 1)]),
        OrderedDict([('id', 2), ('name', u'1'), ('groups', [
          OrderedDict([('id', 1)]),
          OrderedDict([('id', 2)])]), ('location', 1)]),
        OrderedDict([('id', 3), ('name', u'2'), ('groups', [
          OrderedDict([('id', 1)]),
          OrderedDict([('id', 2)])]), ('location', 2)]),
        OrderedDict([('id', 4), ('name', u'3'), ('groups', [
          OrderedDict([('id', 1)]),
          OrderedDict([('id', 2)])]), ('location', 3)])
      ]
    }, serializer.data)
