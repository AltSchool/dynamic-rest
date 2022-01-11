from django.test import TestCase, override_settings

from rest_framework import serializers

from dynamic_rest.fields import DynamicHashIdField
from dynamic_rest.utils import (
    external_id_from_model_and_internal_id,
)
from tests.models import Dog


@override_settings(
    ENABLE_HASHID_FIELDS=True,
    HASHIDS_SALT="I guess you guys aren’t ready for that yet, "
                 "but your kids are gonna love it.",
)
class FieldsTestCase(TestCase):
    def test_dynamic_hash_id_field_with_model_parameter(self):
        class DogModelTestSerializer(serializers.ModelSerializer):
            """
            A custom model serializer simply for testing purposes.
            """

            id = DynamicHashIdField(model=Dog)

            class Meta:
                model = Dog
                fields = ["id", "name", "fur_color", "origin"]

        dog = Dog.objects.create(
            name="Kazan",
            fur_color="brown",
            origin="Abuelos")
        serializer = DogModelTestSerializer(dog)

        self.assertEqual(
            serializer.data["id"],
            external_id_from_model_and_internal_id(
                Dog,
                dog.id))

    def test_dynamic_hash_id_field_without_model_parameter(self):
        class DogModelTestSerializer(serializers.ModelSerializer):
            """
            A custom model serializer simply for testing purposes.
            """

            id = DynamicHashIdField()

            class Meta:
                model = Dog
                fields = ["id", "name", "fur_color", "origin"]

        dog = Dog.objects.create(
            name="Kazan",
            fur_color="brown",
            origin="Abuelos")
        serializer = DogModelTestSerializer(dog)

        self.assertEqual(
            serializer.data["id"],
            external_id_from_model_and_internal_id(
                Dog,
                dog.id))
