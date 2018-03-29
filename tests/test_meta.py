from django.test import TestCase

from dynamic_rest.meta import (
    get_model_field,
    get_model_field_and_type,
    get_remote_model,
    reverse_m2m_field_name
)
from tests.models import Group, Location, Profile, User


class TestMeta(TestCase):

    def test_get_remote_model(self):
        tests = [
            (Location, 'user_set', User),
            (User, 'location', Location),
            (User, 'profile', Profile),
            (User, 'groups', Group),
            (Group, 'users', User),
            (Profile, 'user', User),
        ]

        for model, field_name, expected in tests:
            remote_model = get_remote_model(
                get_model_field(model, field_name)
            )
            self.assertEqual(
                expected,
                remote_model,
                "For %s.%s expected %s got %s" % (
                    model,
                    field_name,
                    expected,
                    remote_model
                )
            )

    def test_model_field_and_type(self):

        tests = [
            (Location, 'user_set', 'm2o'),
            (User, 'location', 'fk'),
            (User, 'profile', 'o2or'),
            (User, 'groups', 'm2m'),
            (Group, 'users', 'm2m'),
            (Profile, 'user', 'o2o'),
            (User, 'id', '')
        ]

        for model, field_name, expected in tests:
            field, typestr = get_model_field_and_type(model, field_name)
            self.assertEqual(
                expected,
                typestr,
                "%s.%s should be '%s', got '%s'" % (
                    model,
                    field_name,
                    expected,
                    typestr,
                )
            )

    def test_reverse_m2m_field_name(self):
        m2m_field = get_model_field(User, 'groups')
        reverse = reverse_m2m_field_name(m2m_field)
        self.assertEquals('users', reverse)
