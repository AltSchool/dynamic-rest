from rest_framework import (
    serializers,
    viewsets,
    routers
)
from .models import (
    User,
    Group,
    Permission,
)

# DRF

# DRF Serializers


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User


class GroupSerializer(serializers.ModelSerializer):

    class Meta:
        model = Group


class PermissionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Permission


class UserWithGroupsSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
    groups = GroupSerializer(many=True)


class GroupWithPermissionsSerializer(serializers.ModelSerializer):

    class Meta:
        model = Group
    permissions = PermissionSerializer(many=True)


class UserWithAllSerializer(serializers.ModelSerializer):

    class Meta:
        model = User

    groups = GroupWithPermissionsSerializer(many=True)
    permissions = PermissionSerializer(many=True)

# DRF viewsets


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserWithGroupsViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserWithGroupsSerializer


class UserWithAllViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserWithAllSerializer

# DRF routing

router = routers.DefaultRouter()
router.register(r'drf/users', UserWithGroupsViewSet)
router.register(r'drf/users_with_groups', UserWithGroupsViewSet)
router.register(r'drf/users_with_all', UserWithAllViewSet)
