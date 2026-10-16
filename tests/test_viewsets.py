"""Tests for viewsets."""
import json
import os
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.models import QuerySet
from django.test import override_settings
from django.test.client import RequestFactory
from django.test.utils import CaptureQueriesContext
from rest_framework import exceptions, permissions, status
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from dynamic_rest.datastructures import FilterNode
from dynamic_rest.filters import DynamicFilterBackend
from dynamic_rest.filters.base import _get_requested_filters
from tests.models import Dog, Group, User
from tests.serializers import GroupSerializer
from tests.setup import create_fixture
from tests.viewsets import DogViewSet, GroupNoMergeDictViewSet, UserViewSet

if os.getenv("DATABASE_URL"):
    from tests.test_cases import ResetTestCase as TestCase
else:
    from tests.test_cases import TestCase


class TestUserViewSet(TestCase):
    """Test case for UserViewSet."""

    def setUp(self):
        """Set up test case."""
        self.view = UserViewSet()
        self.rf = RequestFactory()

    def test_get_request_fields(self):
        """Test get request fields."""
        request = Request(
            self.rf.get(
                "/users/",
                {
                    "include[]": ["name", "groups.permissions"],
                    "exclude[]": ["groups.name"],
                },
            )
        )
        self.view.request = request
        fields = self.view.get_request_fields()

        self.assertEqual(
            {"groups": {"name": False, "permissions": True}, "name": True}, fields
        )

    def test_get_request_fields_disabled(self):
        """Test get request fields disabled."""
        self.view.features = self.view.INCLUDE
        request = Request(
            self.rf.get(
                "/users/",
                {"include[]": ["name", "groups"], "exclude[]": ["groups.name"]},
            )
        )
        self.view.request = request
        fields = self.view.get_request_fields()

        self.assertEqual({"groups": True, "name": True}, fields)

    def test_get_request_fields_invalid(self):
        """Test get request fields invalid."""
        for invalid_field in ("groups..name", "groups.."):
            request = Request(self.rf.get("/users/", {"include[]": [invalid_field]}))
            self.view.request = request
            self.assertRaises(exceptions.ParseError, self.view.get_request_fields)

    def test_filter_extraction(self):
        """Test filter extraction."""
        filters_map = {
            "attr": ["bar"],
            "attr2.eq": ["bar"],
            "-attr3": ["bar"],
            "rel|attr1": ["val"],
            "-rel|attr2": ["val"],
            "rel.attr": ["baz"],
            "rel.bar|attr": ["val"],
            "attr4.lt": ["val"],
            "attr5.in": ["val1", "val2", "val3"],
        }

        backend = DynamicFilterBackend()
        # pylint: disable=protected-access
        out = _get_requested_filters(
            getattr(backend, "view", None), filters_map=filters_map
        )
        self.assertEqual(out["_include"]["attr"].value, "bar")
        self.assertEqual(out["_include"]["attr2"].value, "bar")
        self.assertEqual(out["_exclude"]["attr3"].value, "bar")
        self.assertEqual(out["rel"]["_include"]["attr1"].value, "val")
        self.assertEqual(out["rel"]["_exclude"]["attr2"].value, "val")
        self.assertEqual(out["_include"]["rel__attr"].value, "baz")
        self.assertEqual(out["rel"]["bar"]["_include"]["attr"].value, "val")
        self.assertEqual(out["_include"]["attr4__lt"].value, "val")
        self.assertEqual(len(out["_include"]["attr5__in"].value), 3)

    def test_is_null_casting(self):
        """Test is null casting."""
        filters_map = {
            "f1.isnull": [True],
            "f2.isnull": [["a"]],
            "f3.isnull": ["true"],
            "f4.isnull": ["1"],
            "f5.isnull": [1],
            "f6.isnull": [False],
            "f7.isnull": [[]],
            "f8.isnull": ["false"],
            "f9.isnull": ["0"],
            "f10.isnull": [0],
            "f11.isnull": [""],
            "f12.isnull": [None],
        }

        backend = DynamicFilterBackend()
        # pylint: disable=protected-access
        out = _get_requested_filters(
            getattr(backend, "view", None), filters_map=filters_map
        )

        self.assertEqual(out["_include"]["f1__isnull"].value, True)
        self.assertEqual(out["_include"]["f2__isnull"].value, ["a"])
        self.assertEqual(out["_include"]["f3__isnull"].value, True)
        self.assertEqual(out["_include"]["f4__isnull"].value, True)
        self.assertEqual(out["_include"]["f5__isnull"].value, 1)

        self.assertEqual(out["_include"]["f6__isnull"].value, False)
        self.assertEqual(out["_include"]["f7__isnull"].value, [])
        self.assertEqual(out["_include"]["f8__isnull"].value, False)
        self.assertEqual(out["_include"]["f9__isnull"].value, False)
        self.assertEqual(out["_include"]["f10__isnull"].value, False)
        self.assertEqual(out["_include"]["f11__isnull"].value, False)
        self.assertEqual(out["_include"]["f12__isnull"].value, None)

    def test_nested_filter_rewrite(self):
        """Test nested filter rewrite."""
        node = FilterNode(["members", "id"], "in", [1])
        gs = GroupSerializer(include_fields="*")
        filter_key, _ = node.generate_query_key(gs)
        self.assertEqual(filter_key, "users__id__in")


class TestMergeDictConvertsToDict(TestCase):
    """Test case for MergeDict behavior in DRF 3.2."""

    def setUp(self):
        """Set up test case."""
        self.fixture = create_fixture()
        self.view = GroupNoMergeDictViewSet.as_view({"post": "create"})
        self.rf = RequestFactory()

    def test_merge_dict_request(self):
        """Test merge dict request."""
        data = {"name": "miao", "random_input": [1, 2, 3]}
        # Django test submits data as multipart-form by default,
        # which results in request.data being a MergeDict.
        # Wrote UserNoMergeDictViewSet to raise an exception (return 400)
        # if request.data ends up as MergeDict, is not a dict, or
        # is a dict of lists.
        request = self.rf.post("/groups/", data)
        try:
            response = self.view(request)
            self.assertEqual(response.status_code, 201)
        except NotImplementedError as e:
            message = f"{str(e)}"
            if "request.FILES" not in message:
                self.fail(f"Unexpected error: {message}")
            # otherwise, this is a known DRF 3.2 bug


class BulkUpdateTestCase(TestCase):
    """Test case for bulk update."""

    def setUp(self):
        """Set up test case."""
        self.fixture = create_fixture()

    def test_bulk_update_default_style(self):
        """Test that PATCH request partially updates all submitted resources."""
        data = [{"id": 1, "fur": "grey"}, {"id": 2, "fur": "grey"}]
        response = self.client.patch(
            "/dogs/", json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("dogs" in response.data)
        self.assertTrue(len(response.data["dogs"]) == 2)
        self.assertTrue(
            all(Dog.objects.get(id=pk).fur_color == "grey" for pk in (1, 2))
        )

    def test_bulk_update_drest_style(self):
        """Test that PATCH request partially updates all submitted resources."""
        # test to make sure both string '2' and integer 1 resolve correctly
        data = {"dogs": [{"id": 1, "fur": "grey"}, {"id": "2", "fur": "grey"}]}
        response = self.client.patch(
            "/dogs/", json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("dogs" in response.data)

    def test_bulk_update_with_filter(self):
        """Test that you can patch inside the filtered queryset."""
        data = [{"id": 3, "fur": "gold"}]
        response = self.client.patch(
            "/dogs/?filter{fur.contains}=brown",
            json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Dog.objects.get(id=3).fur_color == "gold")

    def test_bulk_update_fail_without_query_param(self):
        """Test bulk update fail without query param.

        Test that an update-all PATCH request will fail
        if not explicitly using update-all syntax
        """
        for data in [{"fur": "grey"}], []:
            response = self.client.patch(
                "/dogs/?filter{fur.contains}=brown",
                json.dumps(data),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_all_validation(self):
        """Test patch all validation."""
        # wrong format
        data = [{"fur": "grey"}]
        response = self.client.patch(
            "/dogs/?patch-all=true", json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # wrong field
        data = {"fury": "grey"}
        response = self.client.patch(
            "/dogs/?patch-all=true", json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue("fury" in response.content.decode("utf-8"))

        # non-source field
        data = {"is_red": True, "fur": "red"}
        response = self.client.patch(
            "/dogs/?patch-all=true", json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue("is_red" in response.content.decode("utf-8"))

    def test_patch_all(self):
        """Test patch all."""
        # the correct format for a patch-all request
        data = {"fur": "grey"}
        response = self.client.patch(
            "/dogs/?patch-all=true", json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        content = json.loads(response.content.decode("utf-8"))
        num_dogs = Dog.objects.all().count()
        self.assertEqual(num_dogs, content["meta"]["updated"])
        self.assertEqual(
            num_dogs,
            Dog.objects.filter(fur_color="grey").count(),
        )

    def test_patch_all_loads_records_in_batches(self):
        """Test patch all loads records in batches, not all at once."""
        num_dogs = Dog.objects.count()
        self.assertGreater(num_dogs, 2)
        data = {"fur": "grey"}
        with override_settings(DYNAMIC_REST={"PATCH_ALL_BATCH_SIZE": 2}):
            with CaptureQueriesContext(connection) as queries:
                response = self.client.patch(
                    "/dogs/?patch-all=true",
                    json.dumps(data),
                    content_type="application/json",
                )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        content = json.loads(response.content.decode("utf-8"))
        self.assertEqual(num_dogs, content["meta"]["updated"])
        self.assertEqual(num_dogs, Dog.objects.filter(fur_color="grey").count())

        table = Dog._meta.db_table  # pylint: disable=protected-access
        selects = [
            q
            for q in queries
            if q["sql"].lstrip().upper().startswith("SELECT") and table in q["sql"]
        ]
        # one query for the primary keys, then one per batch of two records
        self.assertEqual(1 + -(-num_dogs // 2), len(selects))

    def test_patch_all_with_filter_updates_only_matching_records(self):
        """Test patch all in batches only updates records matching the filter."""
        matching = Dog.objects.filter(fur_color__contains="brown").count()
        self.assertGreater(matching, 2)
        self.assertLess(matching, Dog.objects.count())
        with override_settings(DYNAMIC_REST={"PATCH_ALL_BATCH_SIZE": 2}):
            response = self.client.patch(
                "/dogs/?patch-all=true&filter{fur.contains}=brown",
                json.dumps({"fur": "grey"}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        content = json.loads(response.content.decode("utf-8"))
        self.assertEqual(matching, content["meta"]["updated"])
        self.assertEqual(matching, Dog.objects.filter(fur_color="grey").count())

    def test_patch_all_rejects_invalid_batch_size(self):
        """Test patch all requires a positive integer batch size."""
        for value in (0, -1, "10", None):
            with self.subTest(value=value):
                with override_settings(DYNAMIC_REST={"PATCH_ALL_BATCH_SIZE": value}):
                    with self.assertRaises(ImproperlyConfigured):
                        self.client.patch(
                            "/dogs/?patch-all=true",
                            json.dumps({"fur": "grey"}),
                            content_type="application/json",
                        )
        self.assertEqual(0, Dog.objects.filter(fur_color="grey").count())


class DenyBrownDogs(permissions.BasePermission):
    """Object-level permission that denies dogs with brown fur."""

    def has_object_permission(self, request, view, obj):
        """Deny brown dogs."""
        return "brown" not in obj.fur_color


class PatchAllObjectPermissionsTestCase(TestCase):
    """Test case for object-level permission checks in patch-all."""

    def setUp(self):
        """Set up test case."""
        self.fixture = create_fixture()
        self.factory = APIRequestFactory()

    def _patch_all(
        self,
        query="true",
        filters="",
        permission_classes=None,
        check=True,
        data=None,
        **view_kwargs,
    ):
        """Send a patch-all request straight to the dog viewset."""
        view = DogViewSet.as_view(
            {"patch": "update"},
            permission_classes=permission_classes or [DenyBrownDogs],
            PATCH_ALL_CHECK_OBJECT_PERMISSIONS=check,
            **view_kwargs,
        )
        request = self.factory.patch(
            f"/dogs/?patch-all={query}{filters}",
            {"fur": "grey"} if data is None else data,
            format="json",
        )
        return view(request)

    def _grey_count(self):
        return Dog.objects.filter(fur_color="grey").count()

    def test_option_is_off_by_default(self):
        """Test viewsets do not check object permissions unless told to."""
        self.assertFalse(DogViewSet.PATCH_ALL_CHECK_OBJECT_PERMISSIONS)

    def test_object_permissions_are_not_checked_when_disabled(self):
        """Test patch-all keeps updating every record in the queryset."""
        for query in ("true", "query"):
            with self.subTest(query=query):
                Dog.objects.update(fur_color="red")
                response = self._patch_all(query=query, check=False)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(Dog.objects.count(), self._grey_count())

    def test_denied_object_rejects_the_whole_update(self):
        """Test one denied record rejects the request and updates nothing."""
        for query in ("true", "query"):
            with self.subTest(query=query):
                before = dict(Dog.objects.values_list("pk", "fur_color"))
                response = self._patch_all(query=query)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                self.assertEqual(
                    before, dict(Dog.objects.values_list("pk", "fur_color"))
                )

    def test_allowed_objects_are_updated(self):
        """Test a request that only matches permitted records succeeds."""
        for query in ("true", "query"):
            with self.subTest(query=query):
                Dog.objects.update(fur_color="red")
                Dog.objects.filter(name="Spike").update(fur_color="brown")
                response = self._patch_all(query=query, filters="&filter{fur}=red")
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(
                    Dog.objects.exclude(name="Spike").count(), self._grey_count()
                )
                self.assertEqual(self._grey_count(), response.data["meta"]["updated"])

    def test_each_matching_object_is_checked_once(self):
        """Test the permission check runs once per record in the queryset."""
        with mock.patch.object(
            DogViewSet, "check_object_permissions"
        ) as check_object_permissions:
            response = self._patch_all(permission_classes=[permissions.AllowAny])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Dog.objects.count(), check_object_permissions.call_count)

    def test_records_that_appear_after_the_check_are_not_updated(self):
        """Test only the records that were checked are updated."""
        original = DogViewSet._check_patch_all_permissions

        def check_then_add_a_record(view, queryset):
            checked = original(view, queryset)
            # another request creates a record the check never saw
            Dog.objects.create(name="Late", fur_color="brown", origin="x")
            return checked

        for query in ("true", "query"):
            with self.subTest(query=query):
                Dog.objects.filter(name="Late").delete()
                Dog.objects.update(fur_color="red")
                with mock.patch.object(
                    DogViewSet,
                    "_check_patch_all_permissions",
                    check_then_add_a_record,
                ):
                    response = self._patch_all(query=query)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual("brown", Dog.objects.get(name="Late").fur_color)
                self.assertEqual(
                    Dog.objects.exclude(name="Late").count(), self._grey_count()
                )

    def test_permissions_are_checked_before_the_payload_is_validated(self):
        """Test a denied request does not learn anything from validation."""
        response = self._patch_all(data={"no_such_field": 1})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        Dog.objects.update(fur_color="red")
        response = self._patch_all(data={"no_such_field": 1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_records_are_locked_before_they_are_checked_in_batches(self):
        """Test each batch is locked, then checked, using the batch size setting."""
        events = []
        select_for_update = QuerySet.select_for_update

        def record_lock(queryset, *args, **kwargs):
            events.append("lock")
            return select_for_update(queryset, *args, **kwargs)

        def record_check(view, request, obj):
            events.append("check")

        with override_settings(DYNAMIC_REST={"PATCH_ALL_BATCH_SIZE": 2}):
            with mock.patch.object(QuerySet, "select_for_update", record_lock):
                with mock.patch.object(
                    DogViewSet, "check_object_permissions", record_check
                ):
                    response = self._patch_all(
                        permission_classes=[permissions.AllowAny]
                    )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        num_dogs = Dog.objects.count()
        self.assertEqual(num_dogs, events.count("check"))
        self.assertEqual(-(-num_dogs // 2), events.count("lock"))
        # a batch is locked before any of its records is checked
        self.assertEqual("lock", events[0])
        self.assertEqual(["lock", "check", "check"], events[:3])

    def test_batch_size_setting_is_validated_when_checking_permissions(self):
        """Test an invalid batch size is rejected before any record is checked."""
        for value in (0, -1, "10", None):
            with self.subTest(value=value):
                with override_settings(DYNAMIC_REST={"PATCH_ALL_BATCH_SIZE": value}):
                    with self.assertRaises(ImproperlyConfigured):
                        self._patch_all(permission_classes=[permissions.AllowAny])
        self.assertEqual(0, self._grey_count())

    def test_check_and_update_share_a_transaction(self):
        """Test a failure while updating a later batch undoes earlier ones."""
        Dog.objects.update(fur_color="red")
        real_update = DogViewSet._patch_all_query
        calls = []

        def fail_on_the_second_batch(view, queryset, data):
            calls.append(queryset)
            if len(calls) == 2:
                raise exceptions.ValidationError("boom")
            return real_update(view, queryset, data)

        with override_settings(DYNAMIC_REST={"PATCH_ALL_BATCH_SIZE": 2}):
            with mock.patch.object(
                DogViewSet, "_patch_all_query", fail_on_the_second_batch
            ):
                response = self._patch_all(query="query")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(2, len(calls))
        self.assertEqual(0, self._grey_count())


class BulkCreationTestCase(TestCase):
    """Test case for bulk creation."""

    def test_post_single(self):
        """Test post single.

        Test that POST request with single resource only creates a single
        resource.
        """
        data = {"name": "foo", "random_input": [1, 2, 3]}
        response = self.client.post(
            "/groups/", json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(1, Group.objects.all().count())

    def test_post_bulk_from_resource_plural_name(self):
        """Test post bulk from resource plural name."""
        data = {
            "groups": [
                {"name": "foo", "random_input": [1, 2, 3]},
                {"name": "bar", "random_input": [4, 5, 6]},
            ]
        }
        response = self.client.post(
            "/groups/", json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(2, Group.objects.all().count())

    def test_post_bulk_from_list(self):
        """Test post bulk from list.

        Test that POST request with multiple resources created all posted
        resources.
        """
        data = [
            {
                "name": "foo",
                "random_input": [1, 2, 3],
            },
            {
                "name": "bar",
                "random_input": [4, 5, 6],
            },
        ]
        response = self.client.post(
            "/groups/", json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(2, Group.objects.all().count())
        self.assertEqual(
            ["foo", "bar"], list(Group.objects.all().values_list("name", flat=True))
        )

    def test_post_bulk_with_existing_items_and_disabled_partial_creation(self):
        """Test post bulk with existing items and disabled partial creation."""
        data = [{"name": "foo"}, {"name": "bar"}]
        Group.objects.create(name="foo")
        response = self.client.post(
            "/groups/", json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(1, Group.objects.all().count())
        self.assertTrue("errors" in response.data)

    def test_post_bulk_with_sideloaded_results(self):
        """Test post bulk with sideloaded results."""
        u1 = User.objects.create(name="foo", last_name="bar")
        u2 = User.objects.create(name="foo", last_name="baz")
        data = [
            {
                "name": "foo",
                "members": [u1.pk],
            },
            {
                "name": "bar",
                "members": [u2.pk],
            },
        ]
        response = self.client.post(
            "/groups/?include[]=members.",
            json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        resp_data = response.data

        # Check top-level keys
        self.assertEqual({"users", "groups"}, set(resp_data.keys()))

        # Should be 2 of each
        self.assertEqual(2, len(resp_data["users"]))
        self.assertEqual(2, len(resp_data["groups"]))


class BulkDeletionTestCase(TestCase):
    """Test case for bulk deletion."""

    def setUp(self):
        """Set up test case."""
        self.fixture = create_fixture()
        self.ids = [i.pk for i in self.fixture.dogs]
        self.ids_to_delete = self.ids[:2]

    def test_bulk_delete_default_style(self):
        """Test bulk delete default style."""
        data = [{"id": i} for i in self.ids_to_delete]
        response = self.client.delete(
            "/dogs/",
            json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Dog.objects.filter(id__in=self.ids_to_delete).count(), 0)

    def test_bulk_delete_drest_style(self):
        """Test bulk delete drest style."""
        data = {"dogs": [{"id": i} for i in self.ids_to_delete]}
        response = self.client.delete(
            "/dogs/",
            json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Dog.objects.filter(id__in=self.ids_to_delete).count(), 0)

    def test_bulk_delete_single(self):
        """Test bulk delete single."""
        response = self.client.delete(f"/dogs/{self.ids_to_delete[0]}")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_bulk_delete_invalid_single(self):
        """Test bulk delete invalid single."""
        data = {"dog": {"id": self.ids_to_delete[0]}}
        response = self.client.delete(
            "/dogs/",
            json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_bulk_delete_invalid(self):
        """Test bulk delete invalid."""
        data = {"id": self.ids_to_delete[0]}
        response = self.client.delete(
            "/dogs/",
            json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_on_nonexistent_raises_404(self):
        """Test delete on nonexistent raises 404."""
        response = self.client.delete("/dogs/31415")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
