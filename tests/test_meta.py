"""Tests for dynamic_rest.meta."""
from django.test import TestCase

from dynamic_rest.meta import (
    get_model_field,
    get_model_field_and_type,
    get_remote_model,
    reverse_m2m_field_name,
)
from tests.models import Group, Location, Profile, User


class TestMeta(TestCase):
    """Test case for dynamic_rest.meta."""

    def test_get_remote_model(self):
        """Test get remote model."""
        tests = [
            (Location, "user_set", User),
            (User, "location", Location),
            (User, "profile", Profile),
            (User, "groups", Group),
            (Group, "users", User),
            (Profile, "user", User),
        ]

        for model, field_name, expected in tests:
            remote_model = get_remote_model(get_model_field(model, field_name))
            self.assertEqual(
                expected,
                remote_model,
                f"For {model}.{field_name} expected {expected} got {remote_model}",
            )

    def test_model_field_and_type(self):
        """Test model field and type."""
        tests = [
            (Location, "user_set", "m2o"),
            (User, "location", "fk"),
            (User, "profile", "o2or"),
            (User, "groups", "m2m"),
            (Group, "users", "m2m"),
            (Profile, "user", "o2o"),
            (User, "id", ""),
        ]

        for model, field_name, expected in tests:
            _, typestr = get_model_field_and_type(model, field_name)
            self.assertEqual(
                expected,
                typestr,
                f"{model}.{field_name} should be '{expected}', got '{typestr}'",
            )

    def test_reverse_m2m_field_name(self):
        """Test reverse m2m field name."""
        m2m_field = get_model_field(User, "groups")
        reverse = reverse_m2m_field_name(m2m_field)
        self.assertEqual("users", reverse)
