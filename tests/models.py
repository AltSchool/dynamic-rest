from django.db import models


class User(models.Model):
  name = models.TextField()
  last_name = models.TextField()
  groups = models.ManyToManyField('Group', related_name='users')
  permissions = models.ManyToManyField('Permission', related_name='users')
  # 'related_name' intentionally left unset in location field below:
  location = models.ForeignKey('Location', null=True, blank=True) 


class Group(models.Model):
  name = models.TextField()
  permissions = models.ManyToManyField('Permission', related_name='groups')


class Permission(models.Model):
  name = models.TextField()
  code = models.IntegerField()


class Location(models.Model):
  name = models.TextField()
