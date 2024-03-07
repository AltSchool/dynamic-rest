"""Test models."""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class User(models.Model):
    """User model."""

    name = models.TextField()
    last_name = models.TextField()
    groups = models.ManyToManyField("Group", related_name="users")
    permissions = models.ManyToManyField("Permission", related_name="users")
    date_of_birth = models.DateField(null=True, blank=True)
    # 'related_name' intentionally left unset in location field below:
    location = models.ForeignKey(
        "Location", null=True, blank=True, on_delete=models.CASCADE
    )
    favorite_pet_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.CASCADE
    )
    favorite_pet_id = models.TextField(null=True, blank=True)
    favorite_pet = GenericForeignKey(
        "favorite_pet_type",
        "favorite_pet_id",
    )
    is_dead = models.BooleanField(null=True, default=False)


class Profile(models.Model):
    """Profile model."""

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    display_name = models.TextField()
    thumbnail_url = models.TextField(null=True, blank=True)


class Cat(models.Model):
    """Cat model."""

    name = models.TextField()
    home = models.ForeignKey("Location", on_delete=models.CASCADE)
    backup_home = models.ForeignKey(
        "Location", related_name="friendly_cats", on_delete=models.CASCADE
    )
    hunting_grounds = models.ManyToManyField(
        "Location", related_name="annoying_cats", related_query_name="getoffmylawn"
    )
    parent = models.ForeignKey(
        "Cat", null=True, blank=True, related_name="kittens", on_delete=models.CASCADE
    )


class Dog(models.Model):
    """Dog model."""

    name = models.TextField()
    fur_color = models.TextField()
    origin = models.TextField()


class Horse(models.Model):
    """Horse model."""

    name = models.TextField()
    origin = models.TextField()


class Zebra(models.Model):
    """Zebra model."""

    name = models.TextField()
    origin = models.TextField()


class Group(models.Model):
    """Group model."""

    name = models.TextField(unique=True)
    permissions = models.ManyToManyField("Permission", related_name="groups")


class Permission(models.Model):
    """Permission model."""

    name = models.TextField()
    code = models.IntegerField()


class Location(models.Model):
    """Location model."""

    name = models.TextField()
    blob = models.TextField()


class Event(models.Model):
    """Event model.

     -- Intentionally missing serializer and viewset, so they
    can be added as part of a codelab.
    """

    name = models.TextField()
    status = models.TextField(default="current")
    location = models.ForeignKey(
        "Location", null=True, blank=True, on_delete=models.CASCADE
    )
    users = models.ManyToManyField("User")


class A(models.Model):
    """A Model."""

    name = models.TextField(blank=True)


class B(models.Model):
    """B Model."""

    a = models.OneToOneField("A", related_name="b", on_delete=models.CASCADE)


class C(models.Model):
    """C Model."""

    b = models.ForeignKey("B", related_name="cs", on_delete=models.CASCADE)
    d = models.ForeignKey("D", on_delete=models.CASCADE)


class D(models.Model):
    """D Model."""

    name = models.TextField(blank=True)


class Country(models.Model):
    """Country model."""

    name = models.CharField(max_length=60)
    short_name = models.CharField(max_length=30)


class Car(models.Model):
    """Car model."""

    name = models.CharField(max_length=60)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)


class Part(models.Model):
    """Part model."""

    car = models.ForeignKey(Car, on_delete=models.CASCADE)
    name = models.CharField(max_length=60)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
