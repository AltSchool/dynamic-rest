from dynamic_rest.viewsets import DynamicModelViewSet
from tests.serializers import UserSerializer, GroupSerializer, LocationSerializer
from tests.models import User, Group, Location

class UserViewSet(DynamicModelViewSet):
  features = (DynamicModelViewSet.INCLUDE, DynamicModelViewSet.EXCLUDE)
  model = User
  serializer_class = UserSerializer
  queryset = User.objects.all()

class GroupViewSet(DynamicModelViewSet):
  features = (DynamicModelViewSet.INCLUDE, DynamicModelViewSet.EXCLUDE)
  model = Group
  serializer_class = GroupSerializer
  queryset = Group.objects.all()

class LocationViewSet(DynamicModelViewSet):
  features = (DynamicModelViewSet.INCLUDE, DynamicModelViewSet.EXCLUDE)
  model = Location 
  serializer_class = LocationSerializer
  queryset = Location.objects.all()
