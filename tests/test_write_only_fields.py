"""Tests for protecting write-only fields from filters and sorting."""
import json
import os
from types import SimpleNamespace
from urllib.parse import quote

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import ValidationError

from dynamic_rest.datastructures import FilterNode
from dynamic_rest.fields import DynamicRelationField
from dynamic_rest.filters import DynamicSortingFilter
from dynamic_rest.serializers import DynamicModelSerializer
from tests.models import Cat, Dog, Location, User

if os.getenv("DATABASE_URL"):
    from tests.test_cases import ResetAPITestCase as TestCase
else:
    from tests.test_cases import APITestCase as TestCase

PROTECT = {"PROTECT_WRITE_ONLY_FIELDS": True}


class WriteOnlyFieldsTestCase(TestCase):
    """Test case for write-only serializer fields."""

    def setUp(self):
        """Set up test case."""
        for name, fur_color in (("a", "red"), ("b", "gold"), ("c", "brown")):
            Dog.objects.create(name=name, fur_color=fur_color, origin="x")

    def _get(self, url, expected_status):
        """GET a URL and return the decoded JSON body."""
        response = self.client.get(url)
        self.assertEqual(expected_status, response.status_code, response.content)
        return json.loads(response.content)

    def test_write_only_fields_can_be_filtered_and_sorted_by_default(self):
        """Test the existing behavior is kept unless protection is enabled."""
        body = self._get("/secret_dogs/?filter{fur}=red", 200)
        self.assertEqual(["a"], [dog["name"] for dog in body["secret_dogs"]])

        body = self._get("/secret_dogs/?sort[]=-fur", 200)
        self.assertEqual(["a", "b", "c"], [dog["name"] for dog in body["secret_dogs"]])

    @override_settings(DYNAMIC_REST=PROTECT)
    def test_filter_on_a_write_only_field_is_rejected(self):
        """Test a write-only field cannot be used to probe values."""
        complex_filter = quote(json.dumps({"fur": "red"}))
        for query in (
            "filter{fur}=red",
            "filter{fur.startswith}=r",
            "filter{fur.icontains}=o",
            "filter{-fur}=red",
            "filter{fur.in}=red&filter{fur.in}=gold",
            f"filter{{}}={complex_filter}",
        ):
            with self.subTest(query=query):
                body = self._get(f"/secret_dogs/?{query}", 400)
                self.assertIn("Invalid filter field: fur", body[0])

    @override_settings(DYNAMIC_REST=PROTECT)
    def test_sort_on_a_write_only_field_is_rejected(self):
        """Test a write-only field cannot be used to order and so leak values."""
        for term in ("fur", "-fur"):
            with self.subTest(term=term):
                body = self._get(f"/secret_dogs/?sort[]={term}", 400)
                self.assertIn("Invalid filter field", body[0])

    @override_settings(DYNAMIC_REST=PROTECT)
    def test_readable_fields_can_still_be_filtered_and_sorted(self):
        """Test fields that are not write-only are unaffected."""
        body = self._get("/secret_dogs/?filter{name}=b", 200)
        self.assertEqual(["b"], [dog["name"] for dog in body["secret_dogs"]])

        body = self._get("/secret_dogs/?sort[]=-name", 200)
        self.assertEqual(["c", "b", "a"], [dog["name"] for dog in body["secret_dogs"]])

    @override_settings(DYNAMIC_REST=PROTECT)
    def test_write_only_fields_are_not_rendered(self):
        """Test the write-only field is still absent from responses."""
        body = self._get("/secret_dogs/", 200)
        for dog in body["secret_dogs"]:
            self.assertNotIn("fur", dog)


class WriteOnlyRelatedFilterTestCase(TestCase):
    """Test case for filtering a relation to a serializer with a write-only field."""

    def setUp(self):
        """Set up test case."""
        home = Location.objects.create(name="home")
        User.objects.create(name="u", last_name="secret", location=home)

    def test_relation_filter_on_a_write_only_field_works_by_default(self):
        """Test the existing behavior is kept unless protection is enabled."""
        url = "/secret_locations/?include[]=users.*&filter{users|last_name}=secret"
        self.assertEqual(200, self.client.get(url).status_code)

    @override_settings(DYNAMIC_REST=PROTECT)
    def test_relation_filter_on_a_write_only_field_is_rejected(self):
        """Test the relation filter syntax cannot reach a write-only field."""
        url = "/secret_locations/?include[]=users.*&filter{users|last_name}=secret"
        response = self.client.get(url)
        self.assertEqual(400, response.status_code, response.content)
        self.assertIn(
            "Invalid filter field: last_name", json.loads(response.content)[0]
        )

    @override_settings(DYNAMIC_REST=PROTECT)
    def test_relation_filter_on_a_readable_field_still_works(self):
        """Test the relation filter syntax works for fields that can be read."""
        url = "/secret_locations/?include[]=users.*&filter{users|name}=u"
        self.assertEqual(200, self.client.get(url).status_code)


class ProtectedCatSerializer(DynamicModelSerializer):
    """Serializer that protects its write-only relation, whatever the setting."""

    class Meta:
        """Meta class."""

        model = Cat
        name = "protected_cat"
        fields = ("id", "name", "home")
        protect_write_only_fields = True

    home = DynamicRelationField("tests.serializers.LocationSerializer", write_only=True)


class OpenCatSerializer(DynamicModelSerializer):
    """Serializer that keeps its write-only relation usable, whatever the setting."""

    class Meta:
        """Meta class."""

        model = Cat
        name = "open_cat"
        fields = ("id", "name", "home")
        protect_write_only_fields = False

    home = DynamicRelationField("tests.serializers.LocationSerializer", write_only=True)


class DefaultCatSerializer(DynamicModelSerializer):
    """Serializer that follows the setting."""

    class Meta:
        """Meta class."""

        model = Cat
        name = "default_cat"
        fields = ("id", "name", "home")

    home = DynamicRelationField("tests.serializers.LocationSerializer", write_only=True)


def _filter_key(serializer_class):
    """Return the lookup for filtering a cat's home location name."""
    return FilterNode(["home", "name"], None, "x").generate_query_key(
        serializer_class()
    )


def _ordering(serializer_class):
    """Return the ordering for sorting cats by home location name."""
    view = SimpleNamespace(serializer_class=serializer_class)
    return DynamicSortingFilter().ordering_for("home.name", view)


class WriteOnlyRelationTestCase(SimpleTestCase):
    """Test case for write-only relations and the serializer override."""

    def test_nothing_is_protected_by_default(self):
        """Test a write-only relation can be followed unless protection is on."""
        self.assertEqual("home__name", _filter_key(DefaultCatSerializer)[0])
        self.assertEqual("home__name", _ordering(DefaultCatSerializer))

    @override_settings(DYNAMIC_REST=PROTECT)
    def test_setting_protects_write_only_relations(self):
        """Test a write-only relation cannot be followed when protection is on."""
        with self.assertRaises(ValidationError):
            _filter_key(DefaultCatSerializer)
        self.assertIsNone(_ordering(DefaultCatSerializer))

    def test_serializer_can_turn_protection_on(self):
        """Test Meta.protect_write_only_fields overrides the default setting."""
        with self.assertRaises(ValidationError):
            _filter_key(ProtectedCatSerializer)
        self.assertIsNone(_ordering(ProtectedCatSerializer))

    @override_settings(DYNAMIC_REST=PROTECT)
    def test_serializer_can_turn_protection_off(self):
        """Test Meta.protect_write_only_fields overrides the setting."""
        self.assertEqual("home__name", _filter_key(OpenCatSerializer)[0])
        self.assertEqual("home__name", _ordering(OpenCatSerializer))
