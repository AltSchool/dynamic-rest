from rest_framework.serializers import CharField

from dynamic_rest.fields import (
    CountField,
    DynamicField,
    DynamicGenericRelationField,
    DynamicMethodField,
    DynamicRelationField
)
from dynamic_rest.serializers import (
    DynamicEphemeralSerializer,
    DynamicModelSerializer
)
from tests.models import (
    Cat,
    Dog,
    Group,
    Horse,
    Location,
    Permission,
    Profile,
    User,
    Zebra
)


def backup_home_link(name, field, data, obj):
    return "/locations/%s/?include[]=address" % obj.backup_home_id


class CatSerializer(DynamicModelSerializer):
    home = DynamicRelationField('LocationSerializer', link=None)
    backup_home = DynamicRelationField(
        'LocationSerializer', link=backup_home_link)
    foobar = DynamicRelationField(
        'LocationSerializer', source='hunting_grounds', many=True)
    parent = DynamicRelationField('CatSerializer', immutable=True)

    class Meta:
        model = Cat
        name = 'cat'
        fields = ('id', 'name', 'home', 'backup_home', 'foobar', 'parent')
        deferred_fields = ('home', 'backup_home', 'foobar', 'parent')
        immutable_fields = ('name',)
        untrimmed_fields = ('name',)


class LocationSerializer(DynamicModelSerializer):

    class Meta:
        defer_many_relations = False
        model = Location
        name = 'location'
        fields = (
            'id', 'name', 'users', 'user_count', 'address',
            'cats', 'friendly_cats', 'bad_cats'
        )

    users = DynamicRelationField(
        'UserSerializer',
        source='user_set',
        many=True,
        deferred=True)
    user_count = CountField('users', required=False, deferred=True)
    address = DynamicField(source='blob', required=False, deferred=True)
    cats = DynamicRelationField(
        'CatSerializer', source='cat_set', many=True, deferred=True)
    friendly_cats = DynamicRelationField(
        'CatSerializer', many=True, deferred=True)
    bad_cats = DynamicRelationField(
        'CatSerializer', source='annoying_cats', many=True, deferred=True)


class PermissionSerializer(DynamicModelSerializer):

    class Meta:
        defer_many_relations = True
        model = Permission
        name = 'permission'
        fields = ('id', 'name', 'code', 'users', 'groups')
        deferred_fields = ('code',)

    users = DynamicRelationField('UserSerializer', many=True, deferred=False)
    groups = DynamicRelationField('GroupSerializer', many=True)


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
            'thumbnail_url',
            'number_of_cats',
            'profile',
            'date_of_birth',
            'favorite_pet_id',
            'favorite_pet',
            'is_dead',
        )
        deferred_fields = (
            'last_name',
            'date_of_birth',
            'display_name',
            'profile',
            'thumbnail_url',
            'favorite_pet_id',
            'favorite_pet',
            'is_dead',
        )
        read_only_fields = ('profile',)

    location = DynamicRelationField('LocationSerializer')
    permissions = DynamicRelationField(
        'PermissionSerializer',
        many=True,
        deferred=True
    )
    groups = DynamicRelationField('GroupSerializer', many=True, deferred=True)
    display_name = DynamicField(source='profile.display_name', read_only=True)
    thumbnail_url = DynamicField(
        source='profile.thumbnail_url',
        read_only=True
    )
    number_of_cats = DynamicMethodField(
        requires=['location.cat_set.*'],
        deferred=True
    )

    # Don't set read_only on this field directly. Used in test for
    # Meta.read_only_fields.
    profile = DynamicRelationField(
        'ProfileSerializer',
        deferred=True
    )
    favorite_pet = DynamicGenericRelationField(required=False)

    def get_number_of_cats(self, user):
        location = user.location
        return len(location.cat_set.all()) if location else 0


class ProfileSerializer(DynamicModelSerializer):

    class Meta:
        model = Profile
        name = 'profile'
        fields = (
            'user',
            'display_name',
            'thumbnail_url',
            'user_location_name',
        )

    user = DynamicRelationField('UserSerializer')
    user_location_name = DynamicField(
        source='user.location.name', read_only=True
    )


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
    count = CountField('values', unique=False)
    unique_count = CountField('values')


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


class DogSerializer(DynamicModelSerializer):

    class Meta:
        model = Dog
        fields = ('id', 'name', 'origin', 'fur')

    fur = CharField(source='fur_color')


class HorseSerializer(DynamicModelSerializer):

    class Meta:
        model = Horse
        name = 'horse'
        fields = (
            'id',
            'name',
            'origin',
        )


class ZebraSerializer(DynamicModelSerializer):

    class Meta:
        model = Zebra
        name = 'zebra'
        fields = (
            'id',
            'name',
            'origin',
        )
