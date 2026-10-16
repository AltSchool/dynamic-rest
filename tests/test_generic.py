"""Tests for generic relations."""
import json
import os

from dynamic_rest.fields import DynamicGenericRelationField
from dynamic_rest.routers import DynamicRouter
from tests.models import User, Zebra
from tests.serializers import UserSerializer
from tests.setup import create_fixture

if os.getenv("DATABASE_URL"):
    from tests.test_cases import ResetAPITestCase as TestCase
else:
    from rest_framework.test import APITestCase as TestCase


class TestGenericRelationFieldAPI(TestCase):
    """Test case for generic relation fields."""

    def setUp(self):
        """Set up test case."""
        self.fixture = create_fixture()
        f = self.fixture
        f.users[0].favorite_pet = f.cats[0]
        f.users[0].save()

        f.users[1].favorite_pet = f.cats[1]
        f.users[1].save()

        f.users[2].favorite_pet = f.dogs[1]
        f.users[2].save()

    def test_id_only(self):
        """Test id only.

        In the id_only case, the favorite_pet field looks like:

        ```
            "favorite_animal" : {
                "type": "cats",
                "id": "1"
            }
        ```
        """
        url = "/users/?include[]=favorite_pet" "&filter{favorite_pet_id.isnull}=false"
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        content = json.loads(response.content.decode("utf-8"))
        self.assertTrue(all(_["favorite_pet"] for _ in content["users"]))
        self.assertFalse("cats" in content)
        self.assertFalse("dogs" in content)
        self.assertTrue("type" in content["users"][0]["favorite_pet"])
        self.assertTrue("id" in content["users"][0]["favorite_pet"])

    def test_sideload(self):
        """Test side-load."""
        url = "/users/?include[]=favorite_pet." "&filter{favorite_pet_id.isnull}=false"
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        content = json.loads(response.content.decode("utf-8"))
        self.assertTrue(all(_["favorite_pet"] for _ in content["users"]))
        self.assertTrue("cats" in content)
        self.assertEqual(2, len(content["cats"]))
        self.assertTrue("dogs" in content)
        self.assertEqual(1, len(content["dogs"]))
        self.assertTrue("type" in content["users"][0]["favorite_pet"])
        self.assertTrue("id" in content["users"][0]["favorite_pet"])

    def test_multi_sideload_include(self):
        """Test multi side-load include."""
        url = (
            "/cars/1/?include[]=name&include[]=country.short_name"
            "&include[]=parts.name&include[]=parts.country.name"
        )
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        content = json.loads(response.content.decode("utf-8"))
        self.assertTrue("countries" in content)

        country = None
        for _ in content["countries"]:
            if _["id"] == 1:
                country = _

        self.assertTrue(country)
        self.assertTrue("short_name" in country)
        self.assertTrue("name" in country)

    def test_query_counts(self):
        """Test query counts."""
        # NOTE: Django doesn't seem to prefetch ContentType objects
        #       themselves, and rather caches internally. That means
        #       this call could do 5 SQL queries if the Cat and Dog
        #       ContentType objects haven't been cached.
        with self.assertNumQueries(3):
            url = (
                "/users/?include[]=favorite_pet."
                "&filter{favorite_pet_id.isnull}=false"
            )
            response = self.client.get(url)
            self.assertEqual(200, response.status_code)

        with self.assertNumQueries(3):
            url = "/users/?include[]=favorite_pet."
            response = self.client.get(url)
            self.assertEqual(200, response.status_code)

    def test_unknown_resource(self):
        """Test unknown resource.

        Test case where polymorphic relation pulls in an object for
        which there is no known canonical serializer.
        """
        zork = Zebra.objects.create(name="Zork", origin="San Francisco Zoo")

        user = self.fixture.users[0]
        user.favorite_pet = zork
        user.save()

        self.assertIsNone(DynamicRouter.get_canonical_serializer(Zebra))

        url = f"/users/{user.pk}/?include[]=favorite_pet"
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        content = json.loads(response.content.decode("utf-8"))
        self.assertTrue("user" in content)
        self.assertFalse("zebras" in content)  # Not sideloaded
        user_obj = content["user"]
        self.assertTrue("favorite_pet" in user_obj)
        self.assertEqual("Zebra", user_obj["favorite_pet"]["type"])
        self.assertEqual(zork.pk, user_obj["favorite_pet"]["id"])

    def test_dgrf_with_requires_raises(self):
        """Test dgrf with requires raises."""
        with self.assertRaises(Exception):
            DynamicGenericRelationField(requires=["foo", "bar"])

    def test_if_field_inclusion_then_error(self):
        """Test if field inclusion then error."""
        url = (
            "/users/?include[]=favorite_pet.name"
            "&filter{favorite_pet_id.isnull}=false"
        )
        response = self.client.get(url)
        self.assertEqual(400, response.status_code)

    def test_patch_resource(self):
        """Test patch resource.

        Test that patching a content-type field updates the underlying
        relationship.
        """
        user = self.fixture.users[0]

        url = f"/users/{user.pk}/?include[]=favorite_pet."
        response = self.client.patch(
            url,
            json.dumps({"id": user.id, "favorite_pet": {"type": "dog", "id": 1}}),
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        content = json.loads(response.content.decode("utf-8"))
        self.assertTrue("user" in content)
        self.assertFalse("cats" in content)
        self.assertTrue("dogs" in content)
        self.assertEqual(1, content["dogs"][0]["id"])

    def test_non_deferred_generic_field(self):
        """Test non deferred generic field."""

        class FooUserSerializer(UserSerializer):
            """Foo user serializer."""

            class Meta:
                """Meta class."""

                model = User
                name = "user"
                fields = (
                    "id",
                    "favorite_pet",
                )

        user = (
            User.objects.filter(favorite_pet_id__isnull=False)
            .prefetch_related("favorite_pet")
            .first()
        )

        data = FooUserSerializer(user, envelope=True).data["user"]
        self.assertIsNotNone(data)
        self.assertTrue("favorite_pet" in data)
        self.assertTrue(isinstance(data["favorite_pet"], dict))
        self.assertEqual({"id", "type"}, set(data["favorite_pet"].keys()))
