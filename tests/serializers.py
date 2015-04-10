from tests.models import *
from dynamic_rest.serializers import DynamicModelSerializer
from dynamic_rest.fields import DynamicRelationField, CountField

class LocationSerializer(DynamicModelSerializer):
  class Meta:
    model = Location
    name = 'location'
    fields = ('id', 'name', 'users', 'user_count')

  users = DynamicRelationField('UserSerializer', source='user_set', many=True, 
      deferred=True)
  user_count = CountField('users', deferred=True)

class PermissionSerializer(DynamicModelSerializer):
  class Meta:
    model = Permission
    name = 'permission'
    fields = ('id', 'name', 'code', 'users', 'groups')
    deferred_fields = ('code',)

  users = DynamicRelationField('UserSerializer', many=True, deferred=True)
  groups = DynamicRelationField('GroupSerializer', many=True, deferred=True)

class GroupSerializer(DynamicModelSerializer):
  class Meta:
    model = Group
    name = 'group'
    fields = ('id', 'name', 'permissions', 'members')

  permissions = DynamicRelationField('PermissionSerializer', many=True, deferred=True)
  members = DynamicRelationField('UserSerializer', source='users', many=True, deferred=True)

class UserSerializer(DynamicModelSerializer):
  class Meta:
    model = User
    name = 'user'
    fields = ('id', 'name', 'permissions', 'groups', 'location', 'last_name')
    deferred_fields = ('last_name',)

  location = DynamicRelationField('LocationSerializer')
  permissions = DynamicRelationField('PermissionSerializer', many=True, deferred=True)
  groups = DynamicRelationField('GroupSerializer', many=True, deferred=True)
