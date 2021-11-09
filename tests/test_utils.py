from django.test import TestCase, override_settings

from dynamic_rest.utils import (
    is_truthy,
    unpack,
    internal_id_from_model_and_external_id,
    model_from_definition
)
from tests.models import User


class UtilsTestCase(TestCase):
    def setUp(self):
        User.objects.create(name="Marie")
        User.objects.create(name="Rosalind")

    def test_is_truthy(self):
        self.assertTrue(is_truthy("faux"))
        self.assertTrue(is_truthy(1))
        self.assertFalse(is_truthy("0"))
        self.assertFalse(is_truthy("False"))
        self.assertFalse(is_truthy("false"))
        self.assertFalse(is_truthy(""))

    def test_unpack_empty_value(self):
        self.assertIsNone(unpack(None))

    def test_unpack_non_empty_value(self):
        content = {"hello": "world", "meta": "worldpeace", "missed": "a 't'"}
        self.assertIsNotNone(unpack(content))

    def test_unpack_meta_first_key(self):
        content = {"meta": "worldpeace", "missed": "a 't'"}
        self.assertEqual(unpack(content), "a 't'")

    def test_unpack_meta_not_first_key(self):
        content = {"hello": "world", "meta": "worldpeace", "missed": "a 't'"}
        self.assertEqual(unpack(content), "world")

    @override_settings(
        ENABLE_HASHID_FIELDS=True,
        HASHIDS_SALT="If my calculations are correct, "
                     "when this vaby hits 88 miles per hour, "
                     "you're gonna see some serious s***.",
    )
    def test_int_id_from_model_ext_id_obj_does_not_exits(
            self):
        self.assertRaises(
            User.DoesNotExist,
            internal_id_from_model_and_external_id,
            model=User,
            external_id="skdkahh",
        )

    def test_model_from_definition(self):
        self.assertEqual(model_from_definition('tests.models.User'), User)
        self.assertEqual(model_from_definition(User), User)
        self.assertRaises(
            AssertionError,
            model_from_definition,
            model_definition='django.test.override_settings'
        )
        self.assertRaises(
            AssertionError,
            model_from_definition,
            model_definition=User()
        )
