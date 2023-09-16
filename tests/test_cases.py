"""Test cases for the API."""
from django.test import (  # noqa pylint: disable=unused-import
    TestCase,
    TransactionTestCase,
)
from rest_framework.test import APITestCase


class ResetTestCase(TransactionTestCase):
    """Reset API test case."""

    reset_sequences = True


class ResetAPITestCase(APITestCase):
    """Reset API test case."""

    reset_sequences = True
