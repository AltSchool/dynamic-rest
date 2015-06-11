from django.db import models
from annoying.fields import JSONField


class User(models.Model):
    name = models.TextField()
    last_name = models.TextField()
    groups = models.ManyToManyField('Group', related_name='users')
    permissions = models.ManyToManyField('Permission', related_name='users')
    # 'related_name' intentionally left unset in location field below:
    location = models.ForeignKey('Location', null=True, blank=True)


class Cat(models.Model):
    name = models.TextField()
    home = models.ForeignKey('Location')
    backup_home = models.ForeignKey('Location', related_name='friendly_cats')
    hunting_grounds = models.ManyToManyField(
        'Location',
        related_name='annoying_cats',
        related_query_name='getoffmylawn'
    )


class Group(models.Model):
    name = models.TextField()
    permissions = models.ManyToManyField('Permission', related_name='groups')


class Permission(models.Model):
    name = models.TextField()
    code = models.IntegerField()


class Location(models.Model):
    name = models.TextField()
    blob = models.TextField()
    metadata = JSONField(null=True, blank=True)


class Event(models.Model):
    """
    Event model -- Intentionally missing serializer and viewset, so they
    can be added as part of a codelab.
    """
    name = models.TextField()
    status = models.TextField(default="current")
    location = models.ForeignKey('Location', null=True, blank=True)
    users = models.ManyToManyField('User')
