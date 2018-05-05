from django.db.models import Q
from django.db import transaction
from rest_framework import exceptions
from django.utils.functional import cached_property


class Me(object):
    def __repr__(self):
        return '<the current user>'


class Filter(object):
    def __repr__(self):
        return str(self.spec)

    def __init__(self, spec, user=None):
        self.spec = spec
        self.user = user

    def __and__(self, other):
        no_access = self.no_access
        if no_access:
            return self.NO_ACCESS
        no_access = other.no_access
        if no_access:
            return self.NO_ACCESS

        access = self.full_access
        if access:
            return other
        access = other.full_access
        if access:
            return self

        filters = self.filters & other.filters
        return self(filters, self.user)

    def __or__(self, other):
        access = self.full_access
        if access:
            return self.FULL_ACCESS
        access = other.full_access
        if access:
            return self.FULL_ACCESS

        no_access = self.no_access
        if no_access:
            return other
        no_access = other.no_access
        if no_access:
            return self

        filters = self.filters | other.filters
        return Filter(filters, self.user)

    def __bool__(self):
        if self.no_access:
            return False
        return True

    __nonzero__ = __bool__

    def __not__(self):
        if self.full_access:
            return self.NO_ACCESS
        if self.no_access:
            return self.FULL_ACCESS
        return Filter(~self.filters, self.user)

    @cached_property
    def filters(self):
        if self.full_access:
            return Q()
        if self.no_access:
            return Q(pk=None)

        user = self.user
        spec = self.spec

        if callable(spec):
            try:
                spec = spec(user)
            except TypeError:
                pass

        if isinstance(spec, Q):
            return spec

        if isinstance(spec, Me) or spec is Me:
            return Q(pk=user.pk)

        if isinstance(spec, dict):
            spec = {
                k: user if isinstance(v, Me) or v is Me else v
                for k, v in spec.items()
            }
            return Q(**spec)

        raise Exception(
            "Not sure how to deal with: %s" % spec
        )

    @property
    def no_access(self):
        return self.spec is False or self.spec is None

    @property
    def full_access(self):
        return self.spec is True


Filter.FULL_ACCESS = Filter(True)

Filter.NO_ACCESS = Filter(False)


class Role(object):
    def __repr__(self):
        return str(self.spec)

    def __init__(self, spec, user):
        self.user = user
        self.spec = spec

    @cached_property
    def write_fields(self):
        return self.get('write_fields')

    @cached_property
    def read_fields(self):
        return self.get('read_fields')

    @cached_property
    def list(self):
        return self.get('list')

    @cached_property
    def read(self):
        return self.get('read')

    @cached_property
    def delete(self):
        return self.get('delete')

    @cached_property
    def create(self):
        return self.get('create')

    @cached_property
    def update(self):
        return self.get('update')

    def get(self, name):
        spec = self.spec.get(name, False)
        while isinstance(spec, Filter):
            spec = spec.spec

        if spec is False:
            return Filter.NO_ACCESS

        if spec is True:
            return Filter.FULL_ACCESS

        return Filter(
            spec,
            self.user,
        )


class Permissions(object):
    def __repr__(self):
        return str(self.spec)

    def __init__(self, spec, user):
        self.spec = spec
        self.user = user

    def has_role(self, role):
        if role == '*':
            return True
        role = getattr(self.user, role, None)
        return bool(role)

    @cached_property
    def roles(self):
        user = self.user
        return [
            Role(v, user)
            for k, v in self.spec.items()
            if self.has_role(k)
        ]

    @cached_property
    def write_fields(self):
        return self.get('write_fields')

    @cached_property
    def read_fields(self):
        return self.get('read_fields')

    @cached_property
    def list(self):
        return self.get('list')

    @cached_property
    def read(self):
        return self.get('read')

    @cached_property
    def delete(self):
        return self.get('delete')

    @cached_property
    def update(self):
        return self.get('update')

    @cached_property
    def create(self):
        return self.get('create')

    def get(self, name):
        roles = self.roles
        f = Filter.NO_ACCESS
        for role in roles:
            f |= getattr(role, name)
        return f


class PermissionsSerializerMixin(object):
    @cached_property
    def permissions(self):
        user = self.get_request_attribute('user')
        if not user or user.is_superuser:
            return None

        permissions = getattr(
            self.get_meta(), 'permissions', None
        )
        if permissions:
            return Permissions(
                permissions,
                user
            )

        return None

    def create(self, data, **kwargs):
        permissions = self.permissions

        if permissions:
            access = self.permissions.create
            if access.no_access:
                raise exceptions.PermissionDenied()
            with transaction.atomic():
                instance = super(
                    PermissionsSerializerMixin, self
                ).create(data, **kwargs)
                if access.full_access:
                    return instance
                else:
                    model = self.serializer_class.get_model()
                    if model:
                        if not model.objects.filter(access.filters).filter(
                            pk__in=instance.pk
                        ).exists():
                            raise exceptions.PermissionDenied()
                    return instance
        else:
            return super(
                PermissionsSerializerMixin, self
            ).create(data, **kwargs)


class PermissionsViewSetMixin(object):
    @classmethod
    def get_user_permissions(cls, user, even_if_superuser=False):
        if not user or (not even_if_superuser and user.is_superuser):
            return None

        permissions = getattr(
            cls.serializer_class.get_meta(), 'permissions', None
        )
        if permissions:
            return Permissions(
                permissions,
                user,
            )

        return None

    @cached_property
    def permissions(self):
        return self.get_user_permissions(self.request.user)

    def list(self, request, **kwargs):
        permissions = self.permissions
        if not permissions or permissions.list:
            return super(PermissionsViewSetMixin, self).list(request, **kwargs)
        else:
            raise exceptions.PermissionDenied()

    def get_serializer(self, *args, **kwargs):
        permissions = self.get_user_permissions(
            self.request.user,
            even_if_superuser=True
        )
        serializer = super(PermissionsViewSetMixin, self).get_serializer(
            *args,
            **kwargs
        )
        if permissions:
            write_fields = permissions.write_fields
            if write_fields.spec:
                for field_name in write_fields.spec:
                    field = serializer.fields.get(field_name)
                    if field:
                        field.read_only = False
        return serializer

    def get_queryset(self):
        permissions = self.permissions
        request_method = self.request.method.lower()
        queryset = super(PermissionsViewSetMixin, self).get_queryset()

        if permissions:
            access = None
            if request_method == 'get':
                access = permissions.read
            elif request_method == 'put':
                access = permissions.update
            elif request_method == 'delete':
                access = permissions.delete
            else:
                return queryset

            if access.full_access:
                return queryset
            elif access.no_access:
                return queryset.none()
            else:
                return queryset.filter(access.filters)
        else:
            return queryset
