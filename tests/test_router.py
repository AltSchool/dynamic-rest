"""Tests for the dynamic_rest.routers module."""
import os

from django.urls import clear_script_prefix, set_script_prefix
from rest_framework.routers import DefaultRouter

from dynamic_rest.meta import get_model_table
from dynamic_rest.routers import DynamicRouter, Route
from tests.models import Dog
from tests.serializers import CatSerializer, DogSerializer
from tests.urls import urlpatterns  # noqa pylint: disable=unused-import

if os.getenv("DATABASE_URL"):
    from tests.test_cases import ResetAPITestCase as TestCase
else:
    from tests.test_cases import APITestCase as TestCase


class TestDynamicRouter(TestCase):
    """Test case for dynamic_rest.routers."""

    def test_get_canonical_path(self):
        """Test get canonical path."""
        rsrc_key = DogSerializer().get_resource_key()
        self.assertEqual("/dogs", DynamicRouter.get_canonical_path(rsrc_key))

    def test_get_canonical_path_with_prefix(self):
        """Test get canonical path with prefix."""
        set_script_prefix("/v2/")
        rsrc_key = DogSerializer().get_resource_key()
        self.assertEqual("/v2/dogs", DynamicRouter.get_canonical_path(rsrc_key))
        clear_script_prefix()

    def test_get_canonical_path_with_pk(self):
        """Test get canonical path with pk."""
        rsrc_key = DogSerializer().get_resource_key()
        self.assertEqual("/dogs/1/", DynamicRouter.get_canonical_path(rsrc_key, pk="1"))

    def test_get_canonical_path_with_keyspace(self):
        """Test get canonical path with keyspace."""
        rsrc_key = CatSerializer().get_resource_key()
        self.assertEqual("/v2/cats", DynamicRouter.get_canonical_path(rsrc_key))

    def test_get_canonical_serializer(self):
        """Test get canonical serializer."""
        rsrc_key = get_model_table(Dog)
        self.assertEqual(
            DogSerializer, DynamicRouter.get_canonical_serializer(rsrc_key)
        )

    def test_get_canonical_serializer_by_model(self):
        """Test get canonical serializer by model."""
        self.assertEqual(
            DogSerializer, DynamicRouter.get_canonical_serializer(None, model=Dog)
        )

    def test_get_canonical_serializer_by_instance(self):
        """Test get canonical serializer by instance."""
        dog = Dog.objects.create(name="Snoopy", fur_color="black and white", origin="")
        self.assertEqual(
            DogSerializer, DynamicRouter.get_canonical_serializer(None, instance=dog)
        )

    def test_rest_framework_router_unmodified(self):
        """Test rest framework router unmodified."""
        if hasattr(self, "assertCountEqual"):
            method = self.assertCountEqual
        else:
            method = self.assertItemsEqual

        method(
            [
                {"post": "create", "get": "list"},
                {
                    "put": "update",
                    "patch": "partial_update",
                    "delete": "destroy",
                    "get": "retrieve",
                },
            ],
            [
                route.mapping
                for route in DefaultRouter.routes
                if isinstance(route, Route)
            ],
        )
