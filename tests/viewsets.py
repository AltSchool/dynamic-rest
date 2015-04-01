from dynamic_rest.viewsets import DynamicModelViewSet
from tests.serializers import UserSerializer, GroupSerializer
from tests.models import User, Group

class UserViewSet(DynamicModelViewSet):
  model = User
  serializer_class = UserSerializer
  queryset = User.objects.all()

class GroupViewSet(DynamicModelViewSet):
  model = Group
  serializer_class = GroupSerializer
  queryset = Group.objects.all()
