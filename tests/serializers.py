from tests.models import *
from dynamic_rest.serializers import DynamicModelSerializer

class LocationSerializer(DynamicModelSerializer):
  class Meta:
    model = Location
    name = 'location'
    fields = ('id', 'name')

class PermissionSerializer(DynamicModelSerializer):
  class Meta:
    model = Permission
    name = 'permission'
    fields = ('id', 'name', 'code')
    deferred_fields = ('code',)

class GroupSerializer(DynamicModelSerializer):
  class Meta:
    model = Group
    name = 'group'
    fields = ('id', 'name', 'permissions')
    deferred_fields = ('permissions',)

  permissions = PermissionSerializer(many=True)

class UserSerializer(DynamicModelSerializer):
  class Meta:
    model = User
    name = 'user'
    fields = ('id', 'name', 'permissions', 'groups', 'location', 'last_name')
    deferred_fields = ('permissions', 'groups', 'last_name')

  location = LocationSerializer()
  permissions = PermissionSerializer(many=True)
  groups = GroupSerializer(many=True)
