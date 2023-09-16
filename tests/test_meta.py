"""Tests for dynamic_rest.meta."""
import os

from dynamic_rest.meta import get_model_field_and_type
from tests.models import Group, Location, Profile, User

if os.getenv("DATABASE_URL"):
    from tests.test_cases import ResetTestCase as TestCase
else:
    from tests.test_cases import TestCase


class TestMeta(TestCase):
    """Test case for dynamic_rest.meta."""

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
