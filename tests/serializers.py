"""Test serializers for dynamic_rest."""

from rest_framework.serializers import CharField

from dynamic_rest.fields import (
    CountField,
    DynamicField,
    DynamicGenericRelationField,
    DynamicMethodField,
    DynamicRelationField,
)
from dynamic_rest.serializers import DynamicEphemeralSerializer, DynamicModelSerializer
from tests.models import (
    Car,
    Cat,
    Country,
    Dog,
    Group,
    Horse,
    Location,
    Part,
    Permission,
    Profile,
    User,
    Zebra,
)


def backup_home_link(name, field, data, obj):  # pylint: disable=unused-argument
    """Link to backup home."""
    return f"/locations/{obj.backup_home_id}/?include[]=address"


class CatSerializer(DynamicModelSerializer):
    """Cat serializer."""

    home = DynamicRelationField("LocationSerializer", link=None)
    backup_home = DynamicRelationField("LocationSerializer", link=backup_home_link)
    foobar = DynamicRelationField(
        "LocationSerializer", source="hunting_grounds", many=True
    )
    parent = DynamicRelationField("CatSerializer", immutable=True)

    class Meta:
        """Meta class."""

        model = Cat
        name = "cat"
        fields = ("id", "name", "home", "backup_home", "foobar", "parent")
        deferred_fields = ("home", "backup_home", "foobar", "parent")
        immutable_fields = ("name",)
        untrimmed_fields = ("name",)


class LocationSerializer(DynamicModelSerializer):
    """Location serializer."""

    class Meta:
        """Meta class."""

        defer_many_relations = False
        model = Location
        name = "location"
        fields = (
            "id",
            "name",
            "users",
            "user_count",
            "address",
            "cats",
            "friendly_cats",
            "bad_cats",
        )

    users = DynamicRelationField(
        "UserSerializer", source="user_set", many=True, deferred=True
    )
    user_count = CountField("users", required=False, deferred=True)
    address = DynamicField(source="blob", required=False, deferred=True)
    cats = DynamicRelationField(
        "CatSerializer", source="cat_set", many=True, deferred=True
    )
    friendly_cats = DynamicRelationField("CatSerializer", many=True, deferred=True)
    bad_cats = DynamicRelationField(
        "CatSerializer", source="annoying_cats", many=True, deferred=True
    )

    def filter_queryset(self, query):
        """Filter out Atlantis."""
        return query.exclude(name="Atlantis")


class PermissionSerializer(DynamicModelSerializer):
    """Permission serializer."""

    class Meta:
        """Meta class."""

        defer_many_relations = True
        model = Permission
        name = "permission"
        fields = ("id", "name", "code", "users", "groups")
        deferred_fields = ("code",)

    users = DynamicRelationField("UserSerializer", many=True, deferred=False)
    groups = DynamicRelationField("GroupSerializer", many=True)


class GroupSerializer(DynamicModelSerializer):
    """Group serializer."""

    class Meta:
        """Meta class."""

        model = Group
        name = "group"
        fields = (
            "id",
            "name",
            "permissions",
            "members",
            "users",
            "loc1users",
            "loc1users_lambda",
        )

    permissions = DynamicRelationField("PermissionSerializer", many=True, deferred=True)
    members = DynamicRelationField(
        "UserSerializer", source="users", many=True, deferred=True
    )

    # Intentional duplicate of 'users':
    users = DynamicRelationField("UserSerializer", many=True, deferred=True)

    # For testing default queryset on relations:
    loc1users = DynamicRelationField(
        "UserSerializer",
        source="users",
        many=True,
        queryset=User.objects.filter(location_id=1),
        deferred=True,
    )

    loc1users_lambda = DynamicRelationField(
        "UserSerializer",
        source="users",
        many=True,
        queryset=lambda srlzr: User.objects.filter(location_id=1),
        deferred=True,
    )


class UserSerializer(DynamicModelSerializer):
    """User serializer."""

    class Meta:
        """Meta class."""

        model = User
        name = "user"
        fields = (
            "id",
            "name",
            "permissions",
            "groups",
            "location",
            "last_name",
            "display_name",
            "thumbnail_url",
            "number_of_cats",
            "profile",
            "date_of_birth",
            "favorite_pet_id",
            "favorite_pet",
            "is_dead",
        )
        deferred_fields = (
            "last_name",
            "date_of_birth",
            "display_name",
            "profile",
            "thumbnail_url",
            "favorite_pet_id",
            "favorite_pet",
            "is_dead",
        )
        read_only_fields = ("profile",)

    location = DynamicRelationField("LocationSerializer")
    permissions = DynamicRelationField("PermissionSerializer", many=True, deferred=True)
    groups = DynamicRelationField("GroupSerializer", many=True, deferred=True)
    display_name = DynamicField(source="profile.display_name", read_only=True)
    thumbnail_url = DynamicField(source="profile.thumbnail_url", read_only=True)
    number_of_cats = DynamicMethodField(requires=["location.cat_set.*"], deferred=True)

    # Don't set read_only on this field directly. Used in test for
    # Meta.read_only_fields.
    profile = DynamicRelationField("ProfileSerializer", deferred=True)
    favorite_pet = DynamicGenericRelationField(required=False)

    def get_number_of_cats(self, user):
        """Get number of cats."""
        if not self.context.get("request"):
            # Used in test_api.py::test_relation_includes_context
            raise RuntimeError("No request object in context")
        location = user.location
        return len(location.cat_set.all()) if location else 0


class ProfileSerializer(DynamicModelSerializer):
    """Profile serializer."""

    class Meta:
        """Meta class."""

        model = Profile
        name = "profile"
        fields = (
            "user",
            "display_name",
            "thumbnail_url",
            "user_location_name",
        )

    user = DynamicRelationField("UserSerializer")
    user_location_name = DynamicField(
        source="user.location.name", requires=["user.location.name"], read_only=True
    )


class LocationGroupSerializer(DynamicEphemeralSerializer):
    """Location group serializer."""

    class Meta:
        """Meta class."""

        name = "locationgroup"

    id = DynamicField(field_type=str)
    location = DynamicRelationField("LocationSerializer", deferred=False)
    groups = DynamicRelationField("GroupSerializer", many=True, deferred=False)


class CountsSerializer(DynamicEphemeralSerializer):
    """Counts serializer."""

    class Meta:
        """Meta class."""

        name = "counts"

    values = DynamicField(field_type=list)
    count = CountField("values", unique=False)
    unique_count = CountField("values")


class NestedEphemeralSerializer(DynamicEphemeralSerializer):
    """Nested ephemeral serializer."""

    class Meta:
        """Meta class."""

        name = "nested"

    value_count = DynamicRelationField("CountsSerializer", deferred=False)


class UserLocationSerializer(UserSerializer):
    """Serializer to test embedded fields."""

    class Meta:
        """Meta class."""

        model = User
        name = "user_location"
        fields = ("groups", "location", "id")

    location = DynamicRelationField("LocationSerializer", embed=True)
    groups = DynamicRelationField("GroupSerializer", many=True, embed=True)


class DogSerializer(DynamicModelSerializer):
    """Dog serializer."""

    class Meta:
        """Meta class."""

        model = Dog
        fields = ("id", "name", "origin", "fur", "is_red")

    fur = CharField(source="fur_color")
    is_red = DynamicMethodField(deferred=True, requires=["fur_color"])

    def get_is_red(self, instance):
        """Get is red."""
        return instance.fur_color == "red"


class HorseSerializer(DynamicModelSerializer):
    """Horse serializer."""

    class Meta:
        """Meta class."""

        model = Horse
        name = "horse"
        fields = (
            "id",
            "name",
            "origin",
        )


class ZebraSerializer(DynamicModelSerializer):
    """Zebra serializer."""

    class Meta:
        """Meta class."""

        model = Zebra
        name = "zebra"
        fields = (
            "id",
            "name",
            "origin",
        )


class CountrySerializer(DynamicModelSerializer):
    """Country serializer."""

    class Meta:
        """Meta class."""

        model = Country
        fields = ("id", "name", "short_name")
        deferred_fields = ("name", "short_name")


class PartSerializer(DynamicModelSerializer):
    """Part serializer."""

    country = DynamicRelationField("CountrySerializer")

    class Meta:
        """Meta class."""

        model = Part
        fields = ("id", "name", "country")
        deferred_fields = ("name", "country")


class CarSerializer(DynamicModelSerializer):
    """Car serializer."""

    country = DynamicRelationField("CountrySerializer")
    parts = DynamicRelationField("PartSerializer", many=True, source="part_set")  # noqa

    class Meta:
        """Meta class."""

        model = Car
        fields = ("id", "name", "country", "parts")
        deferred_fields = ("name", "country", "parts")
