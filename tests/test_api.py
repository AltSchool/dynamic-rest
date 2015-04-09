import json
from django.db import connection
from django.test import TestCase
from rest_framework.test import APITestCase
from tests.setup import create_fixture


class TestUsersAPI(APITestCase):

  def setUp(self):
    self.fixture = create_fixture()
    self.maxDiff = None

  def testDefault(self):
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
    }, json.loads(response.content))

  def testInclude(self):
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
    }, json.loads(response.content))

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
    }, json.loads(response.content))

  def testExclude(self):
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
    with self.assertNumQueries(2):
      # 2 queries: 1 for User, 1 for Group
      response = self.client.get('/users/?include[]=groups.')
    self.assertEquals(200, response.status_code)
    self.assertEquals(
     {u'groups': [{u'id': 1, u'name': u'0'}, {u'id': 2, u'name': u'1'}],
      u'users': [{u'groups': [1, 2], u'id': 1, u'location': 1, u'name': u'0'},
                 {u'groups': [1, 2], u'id': 2, u'location': 1, u'name': u'1'},
                 {u'groups': [1, 2], u'id': 3, u'location': 2, u'name': u'2'},
                 {u'groups': [1, 2], u'id': 4, u'location': 3, u'name': u'3'}]},
    json.loads(response.content))

  def testNestedInclude(self):
    with self.assertNumQueries(3):
      # 3 queries: 1 for User, 1 for Group, 1 for Permissions
      response = self.client.get('/users/?include[]=groups.permissions')
    self.assertEquals(200, response.status_code)
    self.assertEquals(
       {u'groups': [{u'id': 1, u'name': u'0', u'permissions': [1]},
                    {u'id': 2, u'name': u'1', u'permissions': [2]}],
        u'users': [{u'groups': [1, 2], u'id': 1, u'location': 1, u'name': u'0'},
                   {u'groups': [1, 2], u'id': 2, u'location': 1, u'name': u'1'},
                   {u'groups': [1, 2], u'id': 3, u'location': 2, u'name': u'2'},
                   {u'groups': [1, 2], u'id': 4, u'location': 3, u'name': u'3'}]},
    json.loads(response.content))

  def testNestedExclude(self):
    with self.assertNumQueries(2):
      # 2 queries: 1 for User, 1 for Group
      response = self.client.get('/users/?exclude[]=groups.name')
    self.assertEquals(200, response.status_code)
    self.assertEquals(
        {u'groups': [{u'id': 1}, {u'id': 2}],
         u'users': [{u'groups': [1, 2], u'id': 1, u'location': 1, u'name': u'0'},
                   {u'groups': [1, 2], u'id': 2, u'location': 1, u'name': u'1'},
                   {u'groups': [1, 2], u'id': 3, u'location': 2, u'name': u'2'},
                   {u'groups': [1, 2], u'id': 4, u'location': 3, u'name': u'3'}]},
    json.loads(response.content))

  def testFilterBasic(self):
    with self.assertNumQueries(1):
      response = self.client.get('/users/?filter{name}=1')
    self.assertEquals(200, response.status_code)
    self.assertEquals(
        {
          u'users': [
            {u'id': 2, u'location': 1, u'name': u'1'},
          ]
        },
        json.loads(response.content))

  def testFilterIn(self):
    url = '/users/?filter{name.in}=1&filter{name.in}=2'
    with self.assertNumQueries(1):
      response = self.client.get(url)
    self.assertEquals(200, response.status_code)
    self.assertEquals(
        {
          u'users': [
            {u'id': 2, u'location': 1, u'name': u'1'},
            {u'id': 3, u'location': 2, u'name': u'2'},
          ]
        },
        json.loads(response.content))

  def testFilterExclude(self):
    url = '/users/?filter{-name}=1'
    with self.assertNumQueries(1):
      response = self.client.get(url)
    self.assertEquals(200, response.status_code)
    self.assertEquals(
        {
          u'users': [
            {u'id': 1, u'location': 1, u'name': u'0'},
            {u'id': 3, u'location': 2, u'name': u'2'},
            {u'id': 4, u'location': 3, u'name': u'3'},
          ]
        },
        json.loads(response.content))

  def testFilterRelation(self):
    url = '/users/?filter{location.name}=1'
    with self.assertNumQueries(1):
      response = self.client.get(url)
    self.assertEquals(200, response.status_code)
    self.assertEquals(
        {
          u'users': [
            {u'id': 3, u'location': 2, u'name': u'2'},
          ]
        },
        json.loads(response.content))

  def testFilterSideload(self):
    url = '/users/?include[]=groups.&filter{groups|name}=1'
    with self.assertNumQueries(2):
      # 2 queries: 1 for User, 1 for Group
      response = self.client.get(url)
    self.assertEquals(200, response.status_code)
    self.assertEquals(
      {
        u'groups': [{u'id': 2, u'name': u'1'}],
        u'users': [
          {u'groups': [2], u'id': 1, u'location': 1, u'name': u'0'},
          {u'groups': [2], u'id': 2, u'location': 1, u'name': u'1'},
          {u'groups': [2], u'id': 3, u'location': 2, u'name': u'2'},
          {u'groups': [2], u'id': 4, u'location': 3, u'name': u'3'}
        ]
      },
      json.loads(response.content))

  def testInvalid(self):
    for bad_data in ('name..', 'groups..name', 'foo', 'groups.foo'):
      response = self.client.get('/users/?include[]=%s' % bad_data)
      self.assertEquals(400, response.status_code)
