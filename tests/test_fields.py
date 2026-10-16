"""Tests for the dynamic_rest.fields module."""
import os

from django.test import override_settings
from rest_framework import serializers

from dynamic_rest.fields import DynamicHashIdField
from dynamic_rest.utils import external_id_from_model_and_internal_id
from tests.models import Dog

if os.getenv("DATABASE_URL"):
    from tests.test_cases import ResetTestCase as TestCase
else:
    from tests.test_cases import TestCase


@override_settings(
    ENABLE_HASHID_FIELDS=True,
    HASHIDS_SALT="I guess you guys aren’t ready for that yet, "
    "but your kids are gonna love it.",
)
class FieldsTestCase(TestCase):
    """Test case for dynamic_rest.fields."""

    def test_dynamic_hash_id_field_with_model_parameter(self):
        """Test dynamic hash id field with model parameter."""

        class DogModelTestSerializer(serializers.ModelSerializer):
            """A custom model serializer simply for testing purposes."""

            id = DynamicHashIdField(model=Dog)

            class Meta:
                model = Dog
                fields = ["id", "name", "fur_color", "origin"]

        dog = Dog.objects.create(name="Kazan", fur_color="brown", origin="Abuelos")
        serializer = DogModelTestSerializer(dog)

        self.assertEqual(
            serializer.data["id"], external_id_from_model_and_internal_id(Dog, dog.id)
        )

    def test_dynamic_hash_id_field_without_model_parameter(self):
        """Test dynamic hash id field without model parameter."""

        class DogModelTestSerializer(serializers.ModelSerializer):
            """A custom model serializer simply for testing purposes."""

            id = DynamicHashIdField()

            class Meta:
                """Meta class."""

                model = Dog
                fields = ["id", "name", "fur_color", "origin"]

        dog = Dog.objects.create(name="Kazan", fur_color="brown", origin="Abuelos")
        serializer = DogModelTestSerializer(dog)

        self.assertEqual(
            serializer.data["id"], external_id_from_model_and_internal_id(Dog, dog.id)
        )
