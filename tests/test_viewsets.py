import json

from django.test import TestCase
from django.test.client import RequestFactory
from rest_framework import exceptions, status
from rest_framework.request import Request

from dynamic_rest.filters import DynamicFilterBackend, FilterNode
from tests.models import Dog, Group, User
from tests.serializers import GroupSerializer
from tests.setup import create_fixture
from tests.viewsets import (
    GroupNoMergeDictViewSet,
    UserViewSet
)


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
        out = backend._get_requested_filters(filters_map=filters_map)
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
        out = backend._get_requested_filters(filters_map=filters_map)

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
        filter_key, field = node.generate_query_key(gs)
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


class BulkUpdateTestCase(TestCase):

    def setUp(self):
        self.fixture = create_fixture()

    def test_bulk_update_default_style(self):
        '''
        Test that PATCH request partially updates all submitted resources.
        '''
        data = [{'id': 1, 'fur': 'grey'}, {'id': 2, 'fur': 'grey'}]
        response = self.client.patch(
            '/dogs/',
            json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('dogs' in response.data)
        self.assertTrue(2, len(response.data['dogs']))
        self.assertTrue(
            all([Dog.objects.get(id=pk).fur_color == 'grey' for pk in (1, 2)])
        )

    def test_bulk_update_drest_style(self):
        data = {'dogs': [{'id': 1, 'fur': 'grey'}, {'id': 2, 'fur': 'grey'}]}
        response = self.client.patch(
            '/dogs/',
            json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('dogs' in response.data)

    def test_bulk_update_with_filter(self):
        '''
        Test that you can patch inside of the filtered queryset.
        '''
        data = [{'id': 3, 'fur': 'gold'}]
        response = self.client.patch(
            '/dogs/?filter{fur.contains}=brown',
            json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Dog.objects.get(id=3).fur_color == 'gold')

    def test_bulk_update_fail_without_lookup_attribute(self):
        '''
        Test that PATCH request will fail if lookup attribute wasn't provided.
        '''
        data = [{'fur': 'grey'}]
        response = self.client.patch(
            '/dogs/?filter{fur.contains}=brown',
            json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class BulkCreationTestCase(TestCase):

    def test_post_single(self):
        """
        Test that POST request with single resource only creates a single
        resource.
        """
        data = {'name': 'foo', 'random_input': [1, 2, 3]}
        response = self.client.post(
            '/groups/', json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(1, Group.objects.all().count())

    def test_post_bulk_from_resource_plural_name(self):
        data = {
            'groups': [
                {'name': 'foo', 'random_input': [1, 2, 3]},
                {'name': 'bar', 'random_input': [4, 5, 6]},
            ]
        }
        response = self.client.post(
            '/groups/',
            json.dumps(data),
            content_type='application/json'
        )
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
        response = self.client.post(
            '/groups/',
            json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(2, Group.objects.all().count())
        self.assertEqual(
            ['foo', 'bar'],
            list(Group.objects.all().values_list('name', flat=True))
        )

    def test_post_bulk_with_existing_items_and_disabled_partial_creation(self):
        data = [{'name': 'foo'}, {'name': 'bar'}]
        Group.objects.create(name='foo')
        response = self.client.post(
            '/groups/',
            json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(1, Group.objects.all().count())
        self.assertTrue('errors' in response.data)

    def test_post_bulk_with_sideloaded_results(self):
        u1 = User.objects.create(name='foo', last_name='bar')
        u2 = User.objects.create(name='foo', last_name='baz')
        data = [
            {
                'name': 'foo',
                'members': [u1.pk],
            }, {
                'name': 'bar',
                'members': [u2.pk],
            }
        ]
        response = self.client.post(
            '/groups/?include[]=members.',
            json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        resp_data = response.data

        # Check top-level keys
        self.assertEqual(
            set(['users', 'groups']),
            set(resp_data.keys())
        )

        # Should be 2 of each
        self.assertEqual(2, len(resp_data['users']))
        self.assertEqual(2, len(resp_data['groups']))


class BulkDeletionTestCase(TestCase):

    def setUp(self):
        self.fixture = create_fixture()
        self.ids = [i.pk for i in self.fixture.dogs]
        self.ids_to_delete = self.ids[:2]

    def test_bulk_delete_default_style(self):
        data = [{'id': i} for i in self.ids_to_delete]
        response = self.client.delete(
            '/dogs/',
            json.dumps(data),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            Dog.objects.filter(id__in=self.ids_to_delete).count(),
            0
        )

    def test_bulk_delete_drest_style(self):
        data = {'dogs': [{'id': i} for i in self.ids_to_delete]}
        response = self.client.delete(
            '/dogs/',
            json.dumps(data),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            Dog.objects.filter(id__in=self.ids_to_delete).count(),
            0
        )

    def test_bulk_delete_single(self):
        response = self.client.delete(
            '/dogs/%s' % self.ids_to_delete[0],
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_bulk_delete_invalid_single(self):
        data = {"dog": {"id": self.ids_to_delete[0]}}
        response = self.client.delete(
            '/dogs/',
            json.dumps(data),
            content_type='application/json',
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_bulk_delete_invalid(self):
        data = {"id": self.ids_to_delete[0]}
        response = self.client.delete(
            '/dogs/',
            json.dumps(data),
            content_type='application/json',
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_delete_on_nonexistent_raises_404(self):
        response = self.client.delete(
            '/dogs/31415'
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )
