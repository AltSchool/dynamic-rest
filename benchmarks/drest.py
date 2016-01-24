from dynamic_rest import (
    serializers as serializers,
    viewsets as viewsets,
    routers as routers,
    fields as fields
)
from .models import (
    User,
    Group,
    Permission,
)

# DREST

# DREST serializers


class UserSerializer(serializers.DynamicModelSerializer):

    class Meta:
        model = User
        name = 'user'

    permissions = fields.DynamicRelationField(
        'PermissionSerializer',
        embed=True,
        many=True,
        deferred=True
    )
    groups = fields.DynamicRelationField(
        'GroupSerializer',
        embed=True,
        many=True,
        deferred=True
    )


class GroupSerializer(serializers.DynamicModelSerializer):

    class Meta:
        model = Group
        name = 'group'

    permissions = fields.DynamicRelationField(
        'PermissionSerializer',
        embed=True,
        many=True,
        deferred=True
    )


class PermissionSerializer(serializers.DynamicModelSerializer):

    class Meta:
        model = Permission
        name = 'permission'

# DREST views


class UserViewSet(viewsets.DynamicModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

# DREST router

router = routers.DynamicRouter()
router.register(r'drest/users', UserViewSet)
