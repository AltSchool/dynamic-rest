# Backwards compatability for django < 1.10.x
try:
    from django.urls import set_script_prefix, clear_script_prefix
except ImportError:
    from django.core.urlresolvers import set_script_prefix, clear_script_prefix


from rest_framework.test import APITestCase

from dynamic_rest.meta import get_model_table
from dynamic_rest.routers import DynamicRouter
from tests.models import Dog
from tests.serializers import CatSerializer, DogSerializer
from tests.urls import urlpatterns  # noqa  force route registration


class TestDynamicRouter(APITestCase):

    def test_get_canonical_path(self):
        rsrc_key = DogSerializer().get_resource_key()
        self.assertEqual(
            '/dogs',
            DynamicRouter.get_canonical_path(rsrc_key)
        )

    def test_get_canonical_path_with_prefix(self):
        set_script_prefix('/v2/')
        rsrc_key = DogSerializer().get_resource_key()
        self.assertEqual(
            '/v2/dogs',
            DynamicRouter.get_canonical_path(rsrc_key)
        )
        clear_script_prefix()

    def test_get_canonical_path_with_pk(self):
        rsrc_key = DogSerializer().get_resource_key()
        self.assertEqual(
            '/dogs/1/',
            DynamicRouter.get_canonical_path(rsrc_key, pk='1')
        )

    def test_get_canonical_path_with_keyspace(self):
        rsrc_key = CatSerializer().get_resource_key()
        self.assertEqual(
            '/v2/cats',
            DynamicRouter.get_canonical_path(rsrc_key)
        )

    def test_get_canonical_serializer(self):
        rsrc_key = get_model_table(Dog)
        self.assertEqual(
            DogSerializer,
            DynamicRouter.get_canonical_serializer(rsrc_key)
        )

    def test_get_canonical_serializer_by_model(self):
        self.assertEqual(
            DogSerializer,
            DynamicRouter.get_canonical_serializer(None, model=Dog)
        )

    def test_get_canonical_serializer_by_instance(self):
        dog = Dog.objects.create(
            name='Snoopy',
            fur_color='black and white',
            origin=''
        )
        self.assertEqual(
            DogSerializer,
            DynamicRouter.get_canonical_serializer(None, instance=dog)
        )
