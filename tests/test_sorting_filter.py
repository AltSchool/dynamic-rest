"""Tests for how the sorting filter maps sort terms and finds the serializer."""
from types import SimpleNamespace

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from dynamic_rest.filters import DynamicSortingFilter
from tests.serializers import UserSerializer


def _view(**attributes):
    """Return a minimal view for the sorting filter."""
    return SimpleNamespace(serializer_class=UserSerializer, **attributes)


def _ordering_for(term, view=None):
    """Return the model ordering for a serializer sort term."""
    return DynamicSortingFilter().ordering_for(term, view or _view())


class OrderingForTestCase(SimpleTestCase):
    """Test case for DynamicSortingFilter.ordering_for."""

    def test_plain_field(self):
        """Test a serializer field maps to its model field."""
        self.assertEqual("name", _ordering_for("name"))

    def test_relation_path(self):
        """Test a path through a relation maps to a lookup."""
        self.assertEqual("location__name", _ordering_for("location.name"))

    def test_unknown_field(self):
        """Test a field the serializer does not have cannot be sorted on."""
        self.assertIsNone(_ordering_for("nope"))

    def test_field_without_a_single_source(self):
        """Test a field computed from the whole instance cannot be sorted on."""
        self.assertIsNone(_ordering_for("number_of_cats"))

    def test_path_through_a_field_that_is_not_a_relation(self):
        """Test only relations can be followed."""
        self.assertIsNone(_ordering_for("name.location"))
        self.assertIsNone(_ordering_for("nope.name"))

    def test_term_outside_the_viewset_ordering_fields(self):
        """Test a viewset can limit the fields that can be sorted on."""
        view = _view(ordering_fields=("name",))
        self.assertEqual("name", _ordering_for("name", view))
        self.assertIsNone(_ordering_for("id", view))


class SerializerClassTestCase(SimpleTestCase):
    """Test case for how the sorting filter finds the serializer class."""

    def test_serializer_class_attribute(self):
        """Test the serializer_class attribute is used."""
        serializer_class = DynamicSortingFilter()._get_serializer_class(
            SimpleNamespace(serializer_class=UserSerializer)
        )
        self.assertIs(UserSerializer, serializer_class)

    def test_get_serializer_class_method_is_preferred(self):
        """Test an overriding get_serializer_class method wins."""
        view = SimpleNamespace(
            serializer_class=None, get_serializer_class=lambda: UserSerializer
        )
        self.assertIs(
            UserSerializer, DynamicSortingFilter()._get_serializer_class(view)
        )

    def test_view_without_a_serializer_is_a_configuration_error(self):
        """Test a view that cannot provide a serializer is reported."""

        def no_serializer_class():
            raise AssertionError("no serializer_class")

        for view in (
            SimpleNamespace(),
            SimpleNamespace(get_serializer_class=no_serializer_class),
        ):
            with self.subTest(view=view):
                with self.assertRaises(ImproperlyConfigured):
                    DynamicSortingFilter()._get_serializer_class(view)
