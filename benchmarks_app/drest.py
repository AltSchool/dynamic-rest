"""Benchmark setup for DREST."""
from benchmarks_app.models import Group, Permission, User
from dynamic_rest import fields, routers, serializers, viewsets


class UserSerializer(serializers.DynamicModelSerializer):
    """User serializer."""

    class Meta:
        """Meta class."""

        model = User
        name = "user"
        fields = ("id", "name", "groups")

    groups = fields.DynamicRelationField(
        "GroupSerializer", embed=True, many=True, deferred=True
    )


class GroupSerializer(serializers.DynamicModelSerializer):
    """Group serializer."""

    class Meta:
        """Meta class."""

        model = Group
        name = "group"
        fields = ("id", "name", "permissions")

    permissions = fields.DynamicRelationField(
        "PermissionSerializer", embed=True, many=True, deferred=True
    )


class PermissionSerializer(serializers.DynamicModelSerializer):
    """Permission serializer."""

    class Meta:
        """Meta class."""

        model = Permission
        name = "permission"
        fields = ("id", "name")


# DREST views


class UserViewSet(viewsets.DynamicModelViewSet):
    """User viewset."""

    queryset = User.objects.all()
    serializer_class = UserSerializer


# DREST router

router = routers.DynamicRouter()
router.register(r"drest/users", UserViewSet)
