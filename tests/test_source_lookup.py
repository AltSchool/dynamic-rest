"""Tests for turning serializer sources into ORM lookups."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from dynamic_rest.datastructures import FilterNode
from dynamic_rest.fields import DynamicField
from dynamic_rest.filters import DynamicSortingFilter
from dynamic_rest.meta import get_lookup_path
from dynamic_rest.serializers import DynamicModelSerializer
from tests.models import Cat, Location, Profile, User


class ColleagueSerializer(DynamicModelSerializer):
    """Serializer with fields whose sources cross reverse relations."""

    class Meta:
        """Meta class."""

        model = User
        name = "colleague"
        fields = ("id", "colleague_names", "display_name")

    colleague_names = DynamicField(
        source="location.user_set.name", read_only=True, deferred=True
    )
    display_name = DynamicField(
        source="profile.display_name", read_only=True, deferred=True
    )


class GetLookupPathTestCase(SimpleTestCase):
    """Test case for get_lookup_path."""

    def test_plain_field(self):
        """Test a source without dots is returned as is."""
        self.assertEqual("name", get_lookup_path(User, "name"))

    def test_forward_relations(self):
        """Test a multi-hop forward source."""
        self.assertEqual(
            "user__location__name", get_lookup_path(Profile, "user.location.name")
        )

    def test_reverse_relation_uses_query_name(self):
        """Test a reverse accessor is replaced by its related query name."""
        self.assertEqual("user", get_lookup_path(Location, "user_set"))

    def test_reverse_relation_inside_a_dotted_source(self):
        """Test a reverse accessor in the middle of a dotted source."""
        self.assertEqual(
            "location__user__name", get_lookup_path(User, "location.user_set.name")
        )

    def test_custom_related_query_name(self):
        """Test a reverse relation with a custom related_query_name."""
        self.assertEqual(
            "getoffmylawn__name", get_lookup_path(Location, "annoying_cats.name")
        )

    def test_source_that_is_not_a_model_field(self):
        """Test the remainder of the path is kept once resolution stops."""
        self.assertEqual("location__nope__x", get_lookup_path(User, "location.nope.x"))

    def test_unknown_model(self):
        """Test a source is joined as is when there is no model."""
        self.assertEqual("a__b", get_lookup_path(None, "a.b"))

    def test_resolved_paths_are_accepted_by_the_orm(self):
        """Test Django accepts every resolved lookup."""
        User.objects.filter(**{get_lookup_path(User, "location.user_set.name"): "x"})
        Cat.objects.filter(**{get_lookup_path(Cat, "home.user_set.name"): "x"})


class SourceLookupTestCase(SimpleTestCase):
    """Test filtering and sorting on sources that cross reverse relations."""

    def test_filter_on_source_through_reverse_relation(self):
        """Test the filter key for a source through a reverse relation."""
        key, _ = FilterNode(["colleague_names"], None, "x").generate_query_key(
            ColleagueSerializer()
        )
        self.assertEqual("location__user__name", key)
        User.objects.filter(**{key: "x"})

    def test_filter_on_source_through_forward_relation(self):
        """Test the filter key for a source through a forward one-to-one."""
        key, _ = FilterNode(["display_name"], "icontains", "x").generate_query_key(
            ColleagueSerializer()
        )
        self.assertEqual("profile__display_name__icontains", key)

    def test_sort_on_source_through_reverse_relation(self):
        """Test the ordering for a source through a reverse relation."""
        view = SimpleNamespace(serializer_class=ColleagueSerializer)
        ordering = DynamicSortingFilter().ordering_for("colleague_names", view)
        self.assertEqual("location__user__name", ordering)
