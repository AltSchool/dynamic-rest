from django.utils.datastructures import MergeDict

from rest_framework import exceptions

from dynamic_rest.viewsets import DynamicModelViewSet
from tests.serializers import (
    CatSerializer,
    LocationSerializer,
    GroupSerializer,
    ProfileSerializer,
    UserSerializer,
    UserLocationSerializer
)
from tests.models import (
    Cat,
    Group,
    Location,
    Profile,
    User,
)


class UserViewSet(DynamicModelViewSet):
    features = (
        DynamicModelViewSet.INCLUDE, DynamicModelViewSet.EXCLUDE,
        DynamicModelViewSet.FILTER
    )
    model = User
    serializer_class = UserSerializer
    queryset = User.objects.all()

    def get_queryset(self):
        location = self.request.QUERY_PARAMS.get('location')
        qs = self.queryset
        if location:
            qs = qs.filter(location=location)
        return qs

    def list(self, request, *args, **kwargs):
        query_params = self.request.QUERY_PARAMS
        # for testing query param injection
        if query_params.get('name'):
            query_params.add('filter{name}', query_params.get('name'))
        return super(UserViewSet, self).list(request, *args, **kwargs)


class GroupNoMergeDictViewSet(DynamicModelViewSet):
    model = Group
    serializer_class = GroupSerializer
    queryset = Group.objects.all()

    def create(self, request, *args, **kwargs):
        if hasattr(request, 'data'):
            if isinstance(request.data, MergeDict):
                raise exceptions.ValidationError("request.data is MergeDict")
            elif not isinstance(request.data, dict):
                raise exceptions.ValidationError("request.data is not a dict")
            elif isinstance(request.data[request.data.keys()[0]], list):
                raise exceptions.ValidationError(
                    "request.data is a dict of lists"
                )
        return super(GroupNoMergeDictViewSet, self).create(
            request,
            *args,
            **kwargs
        )


class GroupViewSet(DynamicModelViewSet):
    features = (
        DynamicModelViewSet.INCLUDE, DynamicModelViewSet.EXCLUDE,
        DynamicModelViewSet.FILTER
    )
    model = Group
    serializer_class = GroupSerializer
    queryset = Group.objects.all()


class LocationViewSet(DynamicModelViewSet):
    features = (
        DynamicModelViewSet.INCLUDE, DynamicModelViewSet.EXCLUDE,
        DynamicModelViewSet.FILTER
    )
    model = Location
    serializer_class = LocationSerializer
    queryset = Location.objects.all()


class UserLocationViewSet(DynamicModelViewSet):
    model = User
    serializer_class = UserLocationSerializer
    queryset = User.objects.all()


class ProfileViewSet(DynamicModelViewSet):
    features = (
        DynamicModelViewSet.EXCLUDE,
        DynamicModelViewSet.FILTER,
        DynamicModelViewSet.INCLUDE,
    )
    model = Profile
    serializer_class = ProfileSerializer
    queryset = Profile.objects.all()


class CatViewSet(DynamicModelViewSet):
    serializer_class = CatSerializer
    queryset = Cat.objects.all()
