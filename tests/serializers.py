from tests.models import (
    Cat,
    Group,
    Location,
    Permission,
    Profile,
    User
)
from dynamic_rest.serializers import DynamicModelSerializer
from dynamic_rest.serializers import DynamicEphemeralSerializer
from dynamic_rest.fields import DynamicRelationField, CountField, DynamicField


class CatSerializer(DynamicModelSerializer):

    class Meta:
        model = Cat
        name = 'cat'
        deferred_fields = ('home', 'backup_home', 'hunting_grous')


class LocationSerializer(DynamicModelSerializer):

    class Meta:
        model = Location
        name = 'location'
        fields = (
            'id', 'name', 'users', 'user_count', 'address', 'metadata',
            'cats', 'friendly_cats', 'bad_cats'
        )

    users = DynamicRelationField(
        'UserSerializer',
        source='user_set',
        many=True,
        deferred=True)
    user_count = CountField('users', required=False, deferred=True)
    address = DynamicField(source='blob', required=False, deferred=True)
    metadata = DynamicField(deferred=True, required=False)
    cats = DynamicRelationField(
        'CatSerializer', source='cat_set', many=True, deferred=True)
    friendly_cats = DynamicRelationField(
        'CatSerializer', many=True, deferred=True)
    bad_cats = DynamicRelationField(
        'CatSerializer', source='annoying_cats', many=True, deferred=True)


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
        fields = (
            'id',
            'name',
            'permissions',
            'members',
            'users',
            'loc1users',
            'loc1usersLambda'
        )

    permissions = DynamicRelationField(
        'PermissionSerializer',
        many=True,
        deferred=True)
    members = DynamicRelationField(
        'UserSerializer',
        source='users',
        many=True,
        deferred=True)

    # Intentional duplicate of 'users':
    users = DynamicRelationField(
        'UserSerializer',
        many=True,
        deferred=True)

    # For testing default queryset on relations:
    loc1users = DynamicRelationField(
        'UserSerializer',
        source='users',
        many=True,
        queryset=User.objects.filter(location_id=1),
        deferred=True)

    loc1usersLambda = DynamicRelationField(
        'UserSerializer',
        source='users',
        many=True,
        queryset=lambda srlzr: User.objects.filter(location_id=1),
        deferred=True)


class UserSerializer(DynamicModelSerializer):

    class Meta:
        model = User
        name = 'user'
        fields = (
            'id',
            'name',
            'permissions',
            'groups',
            'location',
            'last_name',
            'display_name',
            'thumbnail_url')
        deferred_fields = ('last_name', 'display_name', 'thumbnail_url')

    location = DynamicRelationField('LocationSerializer')
    permissions = DynamicRelationField(
        'PermissionSerializer',
        many=True,
        deferred=True)
    groups = DynamicRelationField('GroupSerializer', many=True, deferred=True)
    display_name = DynamicField(source='profile.display_name', read_only=True)
    thumbnail_url = DynamicField(
        source='profile.thumbnail_url',
        read_only=True
    )


class ProfileSerializer(DynamicModelSerializer):

    class Meta:
        model = Profile
        name = 'profile'

    user = DynamicRelationField('UserSerializer')
    user_location_name = DynamicField(
        source='user.location.name', read_only=True
    )


class AsyncUserGroupsSerializer(UserSerializer):
    """ Like UserSerializer but with async groups field"""
    class Meta:
        model = User
        name = 'user'
        fields = ('id', 'name', 'groups')

    groups = DynamicRelationField(
        'GroupSerializer', many=True, deferred=True, async=True)



class LocationGroupSerializer(DynamicEphemeralSerializer):

    class Meta:
        name = 'locationgroup'

    id = DynamicField(field_type=str)
    location = DynamicRelationField('LocationSerializer', deferred=False)
    groups = DynamicRelationField('GroupSerializer', many=True, deferred=False)


class CountsSerializer(DynamicEphemeralSerializer):
    class Meta:
        name = 'counts'

    values = DynamicField(field_type=list)
    count = CountField(source='values', unique=False)
    unique_count = CountField(source='values')


class NestedEphemeralSerializer(DynamicEphemeralSerializer):
    class Meta:
        name = 'nested'

    value_count = DynamicRelationField('CountsSerializer', deferred=False)


class UserLocationSerializer(UserSerializer):
    """ Serializer to test embedded fields """
    class Meta:
        model = User
        name = 'user_location'
        fields = ('groups', 'location', 'id')

    location = DynamicRelationField('LocationSerializer', embed=True)
    groups = DynamicRelationField('GroupSerializer', many=True, embed=True)
