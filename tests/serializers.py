from tests.models import *
from dynamic_rest.serializers import DynamicModelSerializer
from dynamic_rest.fields import DynamicRelationField

class LocationSerializer(DynamicModelSerializer):
  class Meta:
    model = Location
    name = 'location'
    fields = ('id', 'name', 'users')

  users = DynamicRelationField('UserSerializer', many=True)

class PermissionSerializer(DynamicModelSerializer):
  class Meta:
    model = Permission
    name = 'permission'
    fields = ('id', 'name', 'code', 'users', 'groups')
    deferred_fields = ('code',)

  users = DynamicRelationField('UserSerializer', many=True)
  groups = DynamicRelationField('GroupSerializer', many=True)

class GroupSerializer(DynamicModelSerializer):
  class Meta:
    model = Group
    name = 'group'
    fields = ('id', 'name', 'permissions', 'users')

  permissions = DynamicRelationField('PermissionSerializer', many=True)
  users = DynamicRelationField('UserSerializer', many=True)

class UserSerializer(DynamicModelSerializer):
  class Meta:
    model = User
    name = 'user'
    fields = ('id', 'name', 'permissions', 'groups', 'location', 'last_name')
    deferred_fields = ('last_name',)

  location = DynamicRelationField('LocationSerializer', deferred=False)
  permissions = DynamicRelationField('PermissionSerializer', many=True)
  groups = DynamicRelationField('GroupSerializer', many=True)
