import json

import datetime
from uuid import UUID
from django.test import TestCase
from model_mommy import mommy
from rest_framework.fields import empty
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from .compat import resolve
from dynamic_rest.meta import Meta


class ViewSetTestCase(TestCase):
    """Base class that makes it easy to test dynamic viewsets.

    You must set the "view" property to an API-bound view.

    This test runs through the various exposed endpoints,
    making internal API calls as a superuser.

    Default test cases:
        test_get_detail:
            - Only runs if the view allows GET
        test_get_list
            - Only runs if the view allows GET
        test_create
            - Only runs if the view allows POST
        test_update
            - Only run if the view allows PUT
        test_delete
            - Only run if the view allows DELETE

    Overriding methods:
        get_client:
            - should return a suitable API client
        get_post_params:
            - returns an object that can be POSTed to the view
        get_put_params:
            - return an object that can be PUT to the view given an instance
        create_instance:
            - return a committed instance of the model
        prepare_instance:
            - return an uncomitted instance of the model


    Example usage:

        class MyAdminViewSetTestCase(AdminViewSetTestCase):
            viewset = UserViewSet

            # use custom post params
            def get_post_params(self):
                return {
                    'foo': 1
                }

    """
    viewset = None

    def setUp(self):
        if self.viewset:
            try:
                # trigger URL loading
                resolve('/')
            except:
                pass

    def get_model(self):
        serializer = self.serializer_class
        return serializer.get_model()

    def get_url(self, pk=None):
        return self.serializer_class.get_url(pk)

    @property
    def serializer_class(self):
        if not hasattr(self, '_serializer_class'):
            self._serializer_class = self.view.get_serializer_class()
        return self._serializer_class

    @property
    def view(self):
        if not hasattr(self, '_view'):
            self._view = self.viewset() if self.viewset else None
        return self._view

    @property
    def api_client(self):
        if not getattr(self, '_api_client', None):
            self._api_client = self.get_client()
        return self._api_client

    def get_superuser(self):
        User = get_user_model()
        return mommy.make(
            User,
            is_superuser=True
        )

    def get_client(self):
        user = self.get_superuser()
        client = APIClient()
        client.force_authenticate(user)
        return client

    def get_create_params(self):
        return {}

    def get_put_params(self, instance):
        return self.get_post_params(instance)

    def get_post_params(self, instance=None):
        def format_value(v):
            if isinstance(
                v,
                (UUID, datetime.datetime, datetime.date)
            ):
                v = str(v)
            return v

        delete = False
        if not instance:
            delete = True
            instance = self.create_instance()

        serializer_class = self.serializer_class
        serializer = serializer_class(include_fields='*')
        fields = serializer.get_all_fields()
        data = serializer.to_representation(instance)
        data = {
            k: format_value(v) for k, v in data.items()
            if k in fields and (
                (not fields[k].read_only) or
                (fields[k].default is not empty)
            )
        }

        if delete:
            instance.delete()

        return data

    def prepare_instance(self):
        # prepare an uncomitted instance
        return mommy.prepare(
            self.get_model(),
            **self.get_create_params()
        )

    def create_instance(self):
        # create a sample instance
        instance = self.prepare_instance()
        instance.save()
        return instance

    def test_get_list(self):
        view = self.view
        if view is None:
            return

        if 'get' not in view.http_method_names:
            return

        url = self.get_url()

        EMPTY = 0
        NON_EMPTY = 1
        for case in (EMPTY, NON_EMPTY):
            if case == NON_EMPTY:
                self.create_instance()

            for renderer in view.get_renderers():
                url = '%s?format=%s' % (url, renderer.format)
                response = self.api_client.get(url)
                self.assertEquals(
                    response.status_code,
                    200,
                    'GET %s failed with %d: %s' % (
                        url,
                        response.status_code,
                        response.content.decode('utf-8')
                    )
                )

    def test_get_detail(self):
        view = self.view
        if view is None:
            return

        if 'get' not in view.http_method_names:
            return

        instance = self.create_instance()
        # generate an invalid PK by modifying a valid PK
        # this ensures the ID looks valid to the framework,
        # e.g. a UUID looks like a UUID
        try:
            invalid_pk = int(str(instance.pk)) + 1
        except:
            invalid_pk = list(str(instance.pk))
            invalid_pk[0] = 'a' if invalid_pk[0] == 'b' else 'b'
            invalid_pk = "".join(invalid_pk)

        for (pk, status) in (
            (instance.pk, 200),
            (invalid_pk, 404)
        ):
            url = self.get_url(pk)
            for renderer in view.get_renderers():
                url = '%s?format=%s' % (url, renderer.format)
                response = self.api_client.get(url)
                self.assertEquals(
                    response.status_code,
                    status,
                    'GET %s failed with %d:\n%s' % (
                        url,
                        response.status_code,
                        response.content.decode('utf-8')
                    )
                )

    def test_create(self):
        view = self.view
        if view is None:
            return

        if 'post' not in view.http_method_names:
            return

        model = self.get_model()
        for renderer in view.get_renderers():

            format = renderer.format
            url = '%s?format=%s' % (
                self.get_url(),
                format
            )
            data = self.get_post_params()
            response = self.api_client.post(
                url,
                content_type='application/json',
                data=json.dumps(data)
            )
            self.assertTrue(
                response.status_code < 400,
                'POST %s failed with %d:\n%s' % (
                    url,
                    response.status_code,
                    response.content.decode('utf-8')
                )
            )
            content = response.content.decode('utf-8')
            if format == 'json':
                content = json.loads(content)
                model = self.get_model()
                model_name = Meta(model).get_name()
                serializer = self.serializer_class()
                name = serializer.get_name()
                pk_field = serializer.get_field('pk')
                if pk_field:
                    pk_field = pk_field.field_name
                    pk = content[name][pk_field]
                    self.assertTrue(
                        model.objects.filter(pk=pk).exists(),
                        'POST %s succeeded but instance '
                        '"%s.%s" does not exist' % (
                            url,
                            model_name,
                            pk
                        )
                    )

    def test_update(self):
        view = self.view
        if view is None:
            return

        if 'put' not in view.http_method_names:
            return

        instance = self.create_instance()
        for renderer in view.get_renderers():
            data = self.get_put_params(instance)
            url = '%s?format=%s' % (
                self.get_url(instance.pk),
                renderer.format
            )
            response = self.api_client.put(
                url,
                content_type='application/json',
                data=json.dumps(data)
            )
            self.assertTrue(
                response.status_code < 400,
                'PUT %s failed with %d:\n%s' % (
                    url,
                    response.status_code,
                    response.content.decode('utf-8')
                )
            )

    def test_delete(self):
        view = self.view

        if view is None:
            return

        if 'delete' not in view.http_method_names:
            return

        for renderer in view.get_renderers():
            instance = self.create_instance()
            url = '%s?format=%s' % (
                self.get_url(instance.pk),
                renderer.format
            )
            response = self.api_client.delete(url)
            self.assertTrue(
                response.status_code < 400,
                'DELETE %s failed with %d: %s' % (
                    url,
                    response.status_code,
                    response.content.decode('utf-8')
                )
            )
            model = self.get_model()
            model_name = Meta(model).get_name()
            pk = instance.pk
            self.assertFalse(
                model.objects.filter(pk=pk).exists(),
                'DELETE %s succeeded but instance "%s.%s" still exists' % (
                    url,
                    model_name,
                    pk
                )
            )
