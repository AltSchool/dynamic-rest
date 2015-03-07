from rest_framework.renderers import BrowsableAPIRenderer

from dynamic_rest.viewsets import DynamicModelViewSet
from dynamic_rest.renderers import DynamicJSONRenderer

from tests.serializers import UserSerializer
from tests.models import User


class UserViewSet(DynamicModelViewSet):
  model = User
  serializer_class = UserSerializer
  renderer_classes = (DynamicJSONRenderer, BrowsableAPIRenderer)
  queryset = User.objects.all()
