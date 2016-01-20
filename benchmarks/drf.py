from rest_framework import routers, serializers, viewsets

from .models import Group, Permission, User


# DRF

# DRF Serializers


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ('id', 'name')


class GroupSerializer(serializers.ModelSerializer):

    class Meta:
        model = Group
        fields = ('id', 'name')


class PermissionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Permission
        fields = ('id', 'name')


class UserWithGroupsSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ('id', 'name', 'groups')
    groups = GroupSerializer(many=True)


class GroupWithPermissionsSerializer(serializers.ModelSerializer):

    class Meta:
        model = Group
        fields = ('id', 'name', 'permissions')

    permissions = PermissionSerializer(many=True)


class UserWithAllSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ('id', 'name', 'groups')

    groups = GroupWithPermissionsSerializer(many=True)

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
