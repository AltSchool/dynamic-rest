"""DRF serializers and viewsets."""
from rest_framework import routers, serializers, viewsets

from benchmarks_app.models import Group, Permission, User


class UserSerializer(serializers.ModelSerializer):
    """User serializer."""

    class Meta:
        """Meta class."""

        model = User
        fields = ("id", "name")


class GroupSerializer(serializers.ModelSerializer):
    """Group serializer."""

    class Meta:
        """Meta class."""

        model = Group
        fields = ("id", "name")


class PermissionSerializer(serializers.ModelSerializer):
    """Permission serializer."""

    class Meta:
        """Meta class."""

        model = Permission
        fields = ("id", "name")


class UserWithGroupsSerializer(serializers.ModelSerializer):
    """User serializer."""

    class Meta:
        """Meta class."""

        model = User
        fields = ("id", "name", "groups")

    groups = GroupSerializer(many=True)


class GroupWithPermissionsSerializer(serializers.ModelSerializer):
    """Group serializer with permissions."""

    class Meta:
        """Meta class."""

        model = Group
        fields = ("id", "name", "permissions")

    permissions = PermissionSerializer(many=True)


class UserWithAllSerializer(serializers.ModelSerializer):
    """User serializer with groups and permissions."""

    class Meta:
        """Meta class."""

        model = User
        fields = ("id", "name", "groups")

    groups = GroupWithPermissionsSerializer(many=True)


# DRF viewsets


class UserViewSet(viewsets.ModelViewSet):
    """User viewset."""

    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserWithGroupsViewSet(viewsets.ModelViewSet):
    """User viewset with groups."""

    queryset = User.objects.all()
    serializer_class = UserWithGroupsSerializer


class UserWithAllViewSet(viewsets.ModelViewSet):
    """User viewset with groups and permissions."""

    queryset = User.objects.all()
    serializer_class = UserWithAllSerializer


# DRF routing

router = routers.DefaultRouter()
router.register(r"drf/users", UserWithGroupsViewSet)
router.register(r"drf/users_with_groups", UserWithGroupsViewSet)
router.register(r"drf/users_with_all", UserWithAllViewSet)
