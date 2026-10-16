"""Benchmark models."""
from django.db import models


class User(models.Model):
    """User model."""

    name = models.TextField()
    groups = models.ManyToManyField("Group", related_name="users")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


class Group(models.Model):
    """Group model."""

    name = models.TextField()
    max_size = models.PositiveIntegerField()
    permissions = models.ManyToManyField("Permission", related_name="groups")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


class Permission(models.Model):
    """Permission model."""

    name = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
