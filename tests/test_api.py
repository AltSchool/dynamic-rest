import json
from django.test import TestCase
from rest_framework.test import APITestCase
from tests.setup import create_fixture


class TestUsersAPI(APITestCase):

  def setUp(self):
    self.fixture = create_fixture()
    self.maxDiff = None

  def testDefault(self):
    with self.assertNumQueries(2):
      # 2 queries: 1 for User, 1 for Location
      # TODO: optimize down to 1 query
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
    with self.assertNumQueries(3):
      # 3 queries: 1 for User, 1 for Group, one for Location
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

  def testExclude(self):
    response = self.client.get('/users/?exclude[]=name')
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
    pass

  def testNestedInclude(self):
    pass

  def testNestedExclude(self):
    pass

  def testInvalid(self):
    for bad_data in ('name..', 'groups..name', 'foo', 'groups.foo'):
      response = self.client.get('/users/?include[]=%s' % bad_data)
      self.assertEquals(400, response.status_code)
