from tests.models import *
from dynamic_rest.serializers import DynamicModelSerializer

class LocationSerializer(DynamicModelSerializer):
  class Meta:
    model = Location
    name = 'location'
    plural_name = 'locations'
    fields = ('id', 'name')

class PermissionSerializer(DynamicModelSerializer):
  class Meta:
    model = Permission
    name = 'permission'
    plural_name = 'permissions'
    fields = ('id', 'name', 'code')
    deferred_fields = ('code',)

class GroupSerializer(DynamicModelSerializer):
  class Meta:
    model = Group
    name = 'group'
    plural_name = 'groups'
    fields = ('id', 'name', 'permissions')
    deferred_fields = ('permissions',)

  permissions = PermissionSerializer(many=True)

class UserSerializer(DynamicModelSerializer):
  class Meta:
    model = User
    name = 'user'
    plural_name = 'users'
    fields = ('id', 'name', 'permissions', 'groups', 'location', 'last_name')
    deferred_fields = ('permissions', 'groups', 'last_name')

  location = LocationSerializer()
  permissions = PermissionSerializer(many=True)
  groups = GroupSerializer(many=True)
