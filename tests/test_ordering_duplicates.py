"""Tests for ordering across multi-valued relations."""
import json
import os
from unittest import mock

from tests.models import Group, Permission, User

if os.getenv("DATABASE_URL"):
    from tests.test_cases import ResetAPITestCase as TestCase
else:
    from tests.test_cases import APITestCase as TestCase


class OrderingAcrossMultiValuedRelationsTestCase(TestCase):
    """Rows must appear once, whatever the ordering joins across."""

    def setUp(self):
        """Set up test case."""
        groups = {name: Group.objects.create(name=name) for name in "abcdz"}
        self.u1 = User.objects.create(name="u1", last_name="x")
        self.u1.groups.set([groups["b"], groups["c"]])
        self.u2 = User.objects.create(name="u2", last_name="x")
        self.u2.groups.set([groups["a"], groups["z"]])
        self.u3 = User.objects.create(name="u3", last_name="x")
        self.u3.groups.set([groups["d"]])

    def _ids(self, url):
        """Return the user ids returned by a list request."""
        response = self.client.get(url)
        self.assertEqual(200, response.status_code, response.content)
        return [user["id"] for user in json.loads(response.content)["users"]]

    def _pks(self, *users):
        return [user.pk for user in users]

    def test_ascending_sort_orders_by_the_smallest_related_value(self):
        """Test each row is listed once, at its smallest related value."""
        ids = self._ids("/users/?sort[]=groups.name")
        self.assertEqual(self._pks(self.u2, self.u1, self.u3), ids)

    def test_descending_sort_orders_by_the_largest_related_value(self):
        """Test each row is listed once, at its largest related value."""
        ids = self._ids("/users/?sort[]=-groups.name")
        self.assertEqual(self._pks(self.u2, self.u3, self.u1), ids)

    def test_sort_can_combine_single_and_multi_valued_terms(self):
        """Test a multi-valued term can follow an ordinary one."""
        ids = self._ids("/users/?sort[]=-name&sort[]=groups.name")
        self.assertEqual(self._pks(self.u3, self.u2, self.u1), ids)

    def test_sort_follows_the_filter_on_the_same_relation(self):
        """Test the smallest value is taken among the related rows that match."""
        url = "/users/?filter{groups.name.in}=b&filter{groups.name.in}=c"
        url += "&filter{groups.name.in}=z&sort[]=groups.name"
        self.assertEqual(self._pks(self.u1, self.u2), self._ids(url))

    def test_pages_do_not_repeat_rows(self):
        """Test pagination counts and slices unique rows."""
        permissions = {
            n: Permission.objects.create(name=n, code=i) for i, n in enumerate("123")
        }
        for permission, names in (
            ("1", "bc"),
            ("2", "az"),
            ("3", "d"),
        ):
            for name in names:
                Group.objects.get(name=name).permissions.add(permissions[permission])

        def page(number):
            url = f"/permissions/?sort[]=groups.name&per_page=2&page={number}"
            body = json.loads(self.client.get(url).content)
            return body, [item["id"] for item in body["permissions"]]

        first, first_ids = page(1)
        _, second_ids = page(2)
        self.assertEqual(3, first["meta"]["total_results"])
        self.assertEqual(2, first["meta"]["total_pages"])
        self.assertEqual(self._pks(permissions["2"], permissions["1"]), first_ids)
        self.assertEqual(self._pks(permissions["3"]), second_ids)

    def test_default_ordering_across_a_multi_valued_relation(self):
        """Test a model's default ordering does not repeat rows either."""
        with mock.patch.object(User._meta, "ordering", ["groups__name"]):
            ids = self._ids("/users/")
        self.assertEqual(self._pks(self.u2, self.u1, self.u3), ids)

        with mock.patch.object(User._meta, "ordering", ["-groups__name"]):
            ids = self._ids("/users/")
        self.assertEqual(self._pks(self.u2, self.u3, self.u1), ids)

    def test_explicit_sort_replaces_the_default_ordering(self):
        """Test the default ordering is ignored when a sort is requested."""
        with mock.patch.object(User._meta, "ordering", ["groups__name"]):
            ids = self._ids("/users/?sort[]=-name")
        self.assertEqual(self._pks(self.u3, self.u2, self.u1), ids)

    def test_detail_requests_work_with_a_multi_valued_default_ordering(self):
        """Test fetching, updating and deleting one row is not ambiguous."""
        with mock.patch.object(User._meta, "ordering", ["groups__name"]):
            response = self.client.get(f"/users/{self.u2.pk}/")
            self.assertEqual(200, response.status_code, response.content)

            response = self.client.patch(
                f"/users/{self.u2.pk}/",
                json.dumps({"name": "renamed"}),
                content_type="application/json",
            )
            self.assertEqual(200, response.status_code, response.content)

            response = self.client.delete(f"/users/{self.u1.pk}/")
            self.assertEqual(204, response.status_code, response.content)
        self.assertEqual("renamed", User.objects.get(pk=self.u2.pk).name)
        self.assertFalse(User.objects.filter(pk=self.u1.pk).exists())

    def test_sort_on_a_single_valued_relation_is_unchanged(self):
        """Test ordering that cannot repeat rows is left as it was."""
        ids = self._ids("/users/?sort[]=-name")
        self.assertEqual(self._pks(self.u3, self.u2, self.u1), ids)
