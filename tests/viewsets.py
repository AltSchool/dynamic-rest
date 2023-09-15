"""ViewSets for testing."""
from django.db.models import Q
from rest_framework import exceptions

from dynamic_rest.viewsets import DynamicModelViewSet
from tests.models import (
    Car,
    Cat,
    Dog,
    Group,
    Horse,
    Location,
    Permission,
    Profile,
    User,
    Zebra,
)
from tests.serializers import (
    CarSerializer,
    CatSerializer,
    DogSerializer,
    GroupSerializer,
    HorseSerializer,
    LocationSerializer,
    PermissionSerializer,
    ProfileSerializer,
    UserLocationSerializer,
    UserSerializer,
    ZebraSerializer,
)


class UserViewSet(DynamicModelViewSet):
    """User viewset."""

    features = (
        DynamicModelViewSet.INCLUDE,
        DynamicModelViewSet.EXCLUDE,
        DynamicModelViewSet.FILTER,
        DynamicModelViewSet.SORT,
        DynamicModelViewSet.SIDELOADING,
        DynamicModelViewSet.DEBUG,
    )
    model = User
    serializer_class = UserSerializer
    queryset = User.objects.all()

    def get_queryset(self):
        """Get queryset."""
        location = self.request.query_params.get("location")
        qs = self.queryset
        if location:
            qs = qs.filter(location=location)
        return qs

    def list(self, request, *args, **kwargs):
        """List."""
        query_params = self.request.query_params
        # for testing query param injection
        if query_params.get("name"):
            query_params.add("filter{name}", query_params.get("name"))
        return super().list(request, *args, **kwargs)


class GroupNoMergeDictViewSet(DynamicModelViewSet):
    """Group viewset."""

    model = Group
    serializer_class = GroupSerializer
    queryset = Group.objects.all()

    def create(self, request, *args, **kwargs):
        """Create."""
        response = super().create(request, *args, **kwargs)
        if hasattr(request, "data"):
            try:
                # Django<1.9, DRF<3.2
                # pylint: disable-next=import-outside-toplevel
                from django.utils.datastructures import MergeDict

                if isinstance(request.data, MergeDict):
                    raise exceptions.ValidationError("request.data is MergeDict")
                elif not isinstance(request.data, dict):
                    raise exceptions.ValidationError("request.data is not a dict")
            except BaseException:  # pylint: disable=broad-exception-caught
                pass

        return response


class GroupViewSet(DynamicModelViewSet):
    """Group viewset."""

    features = (
        DynamicModelViewSet.INCLUDE,
        DynamicModelViewSet.EXCLUDE,
        DynamicModelViewSet.FILTER,
        DynamicModelViewSet.SORT,
    )
    model = Group
    serializer_class = GroupSerializer
    queryset = Group.objects.all()


class LocationViewSet(DynamicModelViewSet):
    """Location viewset."""

    features = (
        DynamicModelViewSet.INCLUDE,
        DynamicModelViewSet.EXCLUDE,
        DynamicModelViewSet.FILTER,
        DynamicModelViewSet.SORT,
        DynamicModelViewSet.DEBUG,
        DynamicModelViewSet.SIDELOADING,
    )
    model = Location
    serializer_class = LocationSerializer
    queryset = Location.objects.all()


class AlternateLocationViewSet(DynamicModelViewSet):
    """Alternate location viewset."""

    model = Location
    serializer_class = LocationSerializer
    queryset = Location.objects.all()

    def filter_queryset(self, queryset):
        """Filter queryset."""
        user_name_separate_filter = self.request.query_params.get("user_name_separate")
        if user_name_separate_filter:
            queryset = queryset.filter(user__name=user_name_separate_filter)
        return super().filter_queryset(queryset)

    def get_extra_filters(self, request):
        """Get extra filters."""
        user_name = request.query_params.get("user_name")
        if user_name:
            return Q(user__name=user_name)
        return None


class UserLocationViewSet(DynamicModelViewSet):
    """User location viewset."""

    model = User
    serializer_class = UserLocationSerializer
    queryset = User.objects.all()


class ProfileViewSet(DynamicModelViewSet):
    """Profile viewset."""

    features = (
        DynamicModelViewSet.EXCLUDE,
        DynamicModelViewSet.FILTER,
        DynamicModelViewSet.INCLUDE,
        DynamicModelViewSet.SORT,
    )
    model = Profile
    serializer_class = ProfileSerializer
    queryset = Profile.objects.all()


class CatViewSet(DynamicModelViewSet):
    """Cat viewset."""

    serializer_class = CatSerializer
    queryset = Cat.objects.all()


class DogViewSet(DynamicModelViewSet):
    """Dog viewset."""

    model = Dog
    serializer_class = DogSerializer
    queryset = Dog.objects.all()
    ENABLE_PATCH_ALL = True


class HorseViewSet(DynamicModelViewSet):
    """Horse viewset."""

    features = (DynamicModelViewSet.SORT,)
    model = Horse
    serializer_class = HorseSerializer
    queryset = Horse.objects.all()
    ordering_fields = ("name",)
    ordering = ("-name",)


class ZebraViewSet(DynamicModelViewSet):
    """Zebra viewset."""

    features = (DynamicModelViewSet.SORT,)
    model = Zebra
    serializer_class = ZebraSerializer
    queryset = Zebra.objects.all()
    ordering_fields = "__all__"


class PermissionViewSet(DynamicModelViewSet):
    """Permission viewset."""

    serializer_class = PermissionSerializer
    queryset = Permission.objects.all()


class CarViewSet(DynamicModelViewSet):
    """Car viewset."""

    serializer_class = CarSerializer
    queryset = Car.objects.all()
