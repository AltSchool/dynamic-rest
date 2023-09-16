"""Test cases for the API."""
from django.test import TestCase
from rest_framework.test import APITestCase


class ResetTestCase(TestCase):
    """Reset API test case."""

    reset_sequences = True


class ResetAPITestCase(APITestCase):
    """Reset API test case."""

    reset_sequences = True
