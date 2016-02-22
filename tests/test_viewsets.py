import json

from django.test import TestCase
from django.test.client import RequestFactory
from rest_framework import exceptions, status
from rest_framework.request import Request

from dynamic_rest.filters import DynamicFilterBackend, FilterNode
from tests.models import Group
from tests.serializers import GroupSerializer
from tests.setup import create_fixture
from tests.viewsets import GroupNoMergeDictViewSet, GroupViewSet, UserViewSet


class TestUserViewSet(TestCase):

    def setUp(self):
        self.view = UserViewSet()
        self.rf = RequestFactory()

    def test_get_request_fields(self):
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

    def test_get_request_fields_disabled(self):
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

    def test_get_request_fields_invalid(self):
        for invalid_field in ('groups..name', 'groups..'):
            request = Request(
                self.rf.get('/users/', {'include[]': [invalid_field]}))
            self.view.request = request
            self.assertRaises(
                exceptions.ParseError,
                self.view.get_request_fields)

    def test_filter_extraction(self):
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

    def test_is_null_casting(self):
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

    def test_nested_filter_rewrite(self):
        node = FilterNode(['members', 'id'], 'in', [1])
        gs = GroupSerializer(include_fields='*')
        filter_key = node.generate_query_key(gs)
        self.assertEqual(filter_key, 'users__id__in')


class TestMergeDictConvertsToDict(TestCase):

    def setUp(self):
        self.fixture = create_fixture()
        self.view = GroupNoMergeDictViewSet.as_view({'post': 'create'})
        self.rf = RequestFactory()

    def test_merge_dict_request(self):
        data = {
            'name': 'miao',
            'random_input': [1, 2, 3]
        }
        # Django test submits data as multipart-form by default,
        # which results in request.data being a MergeDict.
        # Wrote UserNoMergeDictViewSet to raise an exception (return 400)
        # if request.data ends up as MergeDict, is not a dict, or
        # is a dict of lists.
        request = Request(self.rf.post('/groups/', data))
        try:
            response = self.view(request)
            self.assertEqual(response.status_code, 201)
        except NotImplementedError as e:
            message = '{0}'.format(e)
            if 'request.FILES' not in message:
                self.fail('Unexpected error: %s' % message)
            # otherwise, this is a known DRF 3.2 bug


class TestBulkAPI(TestCase):

    def setUp(self):
        self.rf = RequestFactory()
        self.view = GroupViewSet.as_view({'post': 'create'})

    def test_post_single(self):
        """
        Test that POST request with single resource only creates a single
        resource.
        """
        data = {'name': 'foo', 'random_input': [1, 2, 3]}
        request = self.rf.post(
            '/group/', json.dumps(data), content_type='application/json')
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(1, Group.objects.all().count())

    def test_post_bulk_from_resource_plural_name(self):
        data = {
            'groups': [
                {'name': 'foo', 'random_input': [1, 2, 3]},
                {'name': 'bar', 'random_input': [4, 5, 6]},
            ]
        }
        request = self.rf.post(
            '/groups/',
            json.dumps(data),
            content_type='application/json'
        )
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(2, Group.objects.all().count())

    def test_post_bulk_from_list(self):
        """
        Test that POST request with multiple resources created all posted
        resources.
        """
        data = [
            {
                'name': 'foo',
                'random_input': [1, 2, 3],
            },
            {
                'name': 'bar',
                'random_input': [4, 5, 6],
            }
        ]
        request = self.rf.post(
            '/groups/',
            json.dumps(data),
            content_type='application/json'
        )
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(2, Group.objects.all().count())
        self.assertEqual(
            ['foo', 'bar'],
            list(Group.objects.all().values_list('name', flat=True))
        )

    def test_post_bulk_with_existing_items_and_disabled_partial_creation(self):
        data = [{'name': 'foo'}, {'name': 'bar'}]
        Group.objects.create(name='foo')
        request = self.rf.post(
            '/groups/',
            json.dumps(data),
            content_type='application/json'
        )
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(1, Group.objects.all().count())
        self.assertTrue('errors' in response.data)
