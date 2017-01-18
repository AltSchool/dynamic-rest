from rest_framework import exceptions

from dynamic_rest.viewsets import DynamicModelViewSet
from tests.models import (
    Cat,
    Dog,
    Group,
    Horse,
    Location,
    Permission,
    Profile,
    User,
    Zebra
)
from tests.serializers import (
    CatSerializer,
    DogSerializer,
    GroupSerializer,
    HorseSerializer,
    LocationSerializer,
    PermissionSerializer,
    ProfileSerializer,
    UserLocationSerializer,
    UserSerializer,
    ZebraSerializer
)


class UserViewSet(DynamicModelViewSet):
    features = (
        DynamicModelViewSet.INCLUDE, DynamicModelViewSet.EXCLUDE,
        DynamicModelViewSet.FILTER, DynamicModelViewSet.SORT,
        DynamicModelViewSet.SIDELOADING, DynamicModelViewSet.DEBUG
    )
    model = User
    serializer_class = UserSerializer
    queryset = User.objects.all()

    def get_queryset(self):
        location = self.request.query_params.get('location')
        qs = self.queryset
        if location:
            qs = qs.filter(location=location)
        return qs

    def list(self, request, *args, **kwargs):
        query_params = self.request.query_params
        # for testing query param injection
        if query_params.get('name'):
            query_params.add('filter{name}', query_params.get('name'))
        return super(UserViewSet, self).list(request, *args, **kwargs)


class GroupNoMergeDictViewSet(DynamicModelViewSet):
    model = Group
    serializer_class = GroupSerializer
    queryset = Group.objects.all()

    def create(self, request, *args, **kwargs):
        response = super(GroupNoMergeDictViewSet, self).create(
            request,
            *args,
            **kwargs
        )
        if hasattr(request, 'data'):
            try:
                # Django<1.9, DRF<3.2
                from django.utils.datastructures import MergeDict
                if isinstance(request.data, MergeDict):
                    raise exceptions.ValidationError(
                        "request.data is MergeDict"
                    )
                elif not isinstance(request.data, dict):
                    raise exceptions.ValidationError(
                        "request.data is not a dict"
                    )
            except:
                pass

        return response


class GroupViewSet(DynamicModelViewSet):
    features = (
        DynamicModelViewSet.INCLUDE, DynamicModelViewSet.EXCLUDE,
        DynamicModelViewSet.FILTER, DynamicModelViewSet.SORT
    )
    model = Group
    serializer_class = GroupSerializer
    queryset = Group.objects.all()


class LocationViewSet(DynamicModelViewSet):
    features = (
        DynamicModelViewSet.INCLUDE, DynamicModelViewSet.EXCLUDE,
        DynamicModelViewSet.FILTER, DynamicModelViewSet.SORT,
        DynamicModelViewSet.DEBUG, DynamicModelViewSet.SIDELOADING
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
        DynamicModelViewSet.SORT
    )
    model = Profile
    serializer_class = ProfileSerializer
    queryset = Profile.objects.all()


class CatViewSet(DynamicModelViewSet):
    serializer_class = CatSerializer
    queryset = Cat.objects.all()


class DogViewSet(DynamicModelViewSet):
    model = Dog
    serializer_class = DogSerializer
    queryset = Dog.objects.all()


class HorseViewSet(DynamicModelViewSet):
    features = (DynamicModelViewSet.SORT,)
    model = Horse
    serializer_class = HorseSerializer
    queryset = Horse.objects.all()
    ordering_fields = ('name',)
    ordering = ('-name',)


class ZebraViewSet(DynamicModelViewSet):
    features = (DynamicModelViewSet.SORT,)
    model = Zebra
    serializer_class = ZebraSerializer
    queryset = Zebra.objects.all()
    ordering_fields = '__all__'


class PermissionViewSet(DynamicModelViewSet):
    serializer_class = PermissionSerializer
    queryset = Permission.objects.all()
