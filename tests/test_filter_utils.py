"""Tests for dynamic_rest.filters.utils."""
from unittest import mock

from django.test import SimpleTestCase

from dynamic_rest.filters.utils import has_joins, has_multivalued_joins
from tests.models import Cat, Location, User


class HasMultivaluedJoinsTestCase(SimpleTestCase):
    """Test case for has_multivalued_joins."""

    def test_no_joins(self):
        """Test a queryset without joins."""
        queryset = User.objects.filter(name="a")
        self.assertFalse(has_joins(queryset))
        self.assertFalse(has_multivalued_joins(queryset))

    def test_forward_foreign_key(self):
        """Test a forward foreign key join cannot repeat rows."""
        queryset = User.objects.filter(location__name="a")
        self.assertTrue(has_joins(queryset))
        self.assertFalse(has_multivalued_joins(queryset))

    def test_reverse_one_to_one(self):
        """Test a reverse one-to-one join cannot repeat rows."""
        queryset = User.objects.filter(profile__display_name="a")
        self.assertTrue(has_joins(queryset))
        self.assertFalse(has_multivalued_joins(queryset))

    def test_reverse_foreign_key(self):
        """Test a reverse foreign key join can repeat rows."""
        self.assertTrue(has_multivalued_joins(Location.objects.filter(user__name="a")))

    def test_many_to_many(self):
        """Test a many-to-many join can repeat rows."""
        self.assertTrue(has_multivalued_joins(User.objects.filter(groups__name="a")))

    def test_multivalued_join_after_single_valued_join(self):
        """Test a multi-valued join anywhere in the chain is detected."""
        queryset = Cat.objects.filter(home__user__name="a")
        self.assertTrue(has_multivalued_joins(queryset))

    def test_exclude_on_multivalued_relation_has_no_join(self):
        """Test an exclude uses a subquery, so it cannot repeat rows."""
        queryset = User.objects.exclude(groups__name="a")
        self.assertFalse(has_multivalued_joins(queryset))

    def test_unclassifiable_join_is_treated_as_multivalued(self):
        """Test a join without a join field is treated as multi-valued."""
        queryset = User.objects.filter(location__name="a")
        for join in queryset.query.alias_map.values():
            if join.join_type:
                join.join_field = None
        self.assertTrue(has_multivalued_joins(queryset))

    def _forward_join_field(self, queryset):
        """Return the field of the single join in a queryset."""
        (join,) = (j for j in queryset.query.alias_map.values() if j.join_type)
        return join.join_field

    def test_forward_join_without_a_unique_target_is_multivalued(self):
        """Test a forward field that does not guarantee a unique target.

        Django requires the target of a foreign object to be unique, unless
        the field class sets requires_unique_target to False. Such a join can
        match several rows, so it must be treated as multi-valued.
        """
        queryset = User.objects.filter(location__name="a")
        field = self._forward_join_field(queryset)
        self.assertTrue(field.requires_unique_target)
        self.assertFalse(has_multivalued_joins(queryset))

        with mock.patch.object(field, "requires_unique_target", False):
            self.assertTrue(has_multivalued_joins(queryset))

        self.assertFalse(has_multivalued_joins(queryset))
