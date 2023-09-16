"""Prefetching for FastQuery."""
import copy
import traceback
from collections import defaultdict
from functools import lru_cache

from django.db import models
from django.db.models import Prefetch, QuerySet

from dynamic_rest.meta import get_model_field_and_type


class FastObject(dict):
    """FastObject is a dict-like object that allows for dot notation."""

    def __init__(self, *args, **kwargs):
        """Initialise the FastObject."""
        self.pk_field = kwargs.pop("pk_field", "id")
        super().__init__(*args)

    @property
    def pk(self):
        """Return the pk."""
        return self[self.pk_field]

    @lru_cache()
    def _slow_getattr(self, name):
        """Get an attribute."""
        if "." in name:
            parts = name.split(".")
            obj = self
            for part in parts:
                obj = obj[part]
            return obj
        elif name == "*":
            return self
        else:
            raise AttributeError(name)

    def __getattr__(self, name):
        """Get an attribute."""
        try:
            return self[name]
        except KeyError:
            # Fast approach failed, fall back on slower logic.
            return self._slow_getattr(name)

    def __setattr__(self, name, value):
        """Set an attribute."""
        if name not in ("pk_field", "pk"):
            self[name] = value
        else:
            super().__setattr__(name, value)


class SlowObject(dict):
    """SlowObject is a dict-like object that allows for dot notation."""

    def __init__(self, *args, slow_object=None, **kwargs):
        """Initialise the SlowObject."""
        self.pk_field = kwargs.pop("pk_field", "id")
        self.data = slow_object
        super().__init__(slow_object=slow_object.__dict__, *args)

    @property
    def pk(self):
        """Return the pk."""
        return self[self.pk_field]

    def __getitem__(self, value):
        """Get an item."""
        if hasattr(self.data, str(value)):
            return getattr(self.data, str(value))

        # for the purpose of mapping serialized model + '_id' fields back to
        # internal models, we need to check if that pattern is present
        is_nested_obj = value.split("_")
        test_attr = "_".join(is_nested_obj[:-1])
        attr_exists = hasattr(self.data, test_attr)
        if is_nested_obj[-1] == "id" and attr_exists:
            return getattr(self.data, test_attr).id

        return None

    def __iter__(self):
        """Iterate over the object."""
        return iter([self.data])

    def __getattr__(self, value):
        """Get an attribute."""
        # EAFP
        return getattr(self.data, str(value))


class FastList(list):
    """FastList is a list-like object that allows for dot notation."""

    # shim for related m2m record sets
    def all(self):
        """Return self."""
        return self


class FastPrefetch(object):
    """FastPrefetch is a prefetch object that allows for dot notation."""

    def __init__(self, field, queryset=None):
        """Initialise the FastPrefetch."""
        if isinstance(queryset, models.Manager):
            queryset = queryset.all()
        if isinstance(queryset, QuerySet):
            queryset = FastQuery(queryset)

        assert queryset is None or isinstance(queryset, FastQuery)

        self.field = field
        self.query = queryset

    @classmethod
    def make_from_field(cls, model=None, field_name=None, field=None):
        """Create a FastPrefetch from a field."""
        assert (
            model and field_name
        ) or field, "make_from_field required model+field_name or field"

        # For nested prefetch, only handle first level.
        field_parts = field_name.split("__")
        field_name = field_parts[0]
        nested_prefetches = "__".join(field_parts[1:])

        field, ftype = get_model_field_and_type(model, field_name)
        if not ftype:
            raise RuntimeError(f"{field_name} is not prefetchable")

        qs = field.remote_field.model.objects.all()

        field_name = field_name or field.name
        prefetch = cls(field_name, qs)

        # For nested prefetch, recursively pass down remainder
        if nested_prefetches:
            prefetch.query.prefetch_related(nested_prefetches)

        return prefetch

    @classmethod
    def make_from_prefetch(cls, prefetch: Prefetch, parent_model):
        """Create a FastPrefetch from a Django Prefetch object."""
        assert isinstance(prefetch, Prefetch)

        if isinstance(prefetch.queryset, FastQuery):
            return cls(prefetch.prefetch_through, prefetch.queryset)
        else:
            return cls.make_from_field(
                model=parent_model, field_name=prefetch.prefetch_through
            )


class FastQueryCompatMixin(object):
    """Compatibility mixin for FastQuery.

    Mixins for FastQuery to provide QuerySet-compatibility APIs.
    They basically just modify the underlying QuerySet object.
    Separated in a mixin, so it's clearer which APIs are supported.
    """

    def prefetch_related(self, *args):
        """Prefetch related objects."""
        model = self.model
        try:
            for arg in args:
                if isinstance(arg, str):
                    arg = FastPrefetch.make_from_field(model=model, field_name=arg)
                elif isinstance(arg, Prefetch):
                    arg = FastPrefetch.make_from_prefetch(arg, model)
                if not isinstance(arg, FastPrefetch):
                    raise ValueError("Must be FastPrefetch object")

                if arg.field in self.prefetches:
                    raise RuntimeError(
                        f"Prefetch for field '{arg.field}' already exists."
                    )
                self.prefetches[arg.field] = arg
        except Exception:  # noqa pylint: disable=broad-exception-caught
            traceback.print_exc()

        return self

    def only(self, *fields):  # pylint: disable=unused-argument
        """Only support not implemented.

        # TODO: support this for realz
        self.fields = set(self.fields) + set(fields)
        """
        return self

    def exclude(self, *args, **kwargs):
        """Exclude query args."""
        self.queryset = self.queryset.exclude(*args, **kwargs)
        return self

    def count(self):
        """Return the count."""
        qs = self.queryset._clone()  # pylint: disable=protected-access
        return qs.count()

    def extra(self, *args, **kwargs):
        """Extra query args."""
        self.queryset = self.queryset.extra(*args, **kwargs)
        return self

    def filter(self, *args, **kwargs):
        """Filter query args."""
        self.queryset = self.queryset.filter(*args, **kwargs)
        return self

    def order_by(self, *ordering):
        """Order by query args."""
        self.queryset = self.queryset.order_by(*ordering)
        return self

    def distinct(self, *args, **kwargs):
        """Distinct query args."""
        self.queryset = self.queryset.distinct(*args, **kwargs)
        return self

    def get(self, *args, **kwargs):
        """Get query args."""
        # Returns ORM object
        queryset = self._get_django_queryset()
        return queryset.get(*args, **kwargs)

    def first(self, *args, **kwargs):  # pylint: disable=unused-argument
        """Get first query args.

        Returns ORM object.
        """
        queryset = self._get_django_queryset()
        return queryset.first()

    @property
    def query(self):
        """Return the query."""
        return self.queryset.query

    def _clone(self):
        """Clone the queryset."""
        new = copy.copy(self)
        new.queryset = new.queryset._clone()  # pylint: disable=protected-access
        return new

    def _get_django_queryset(self):
        """Return Django QuerySet with prefetches properly configured."""
        prefetches = []
        for field, fprefetch in self.prefetches.items():
            has_query = hasattr(fprefetch, "query")
            qs = fprefetch.query.queryset if has_query else None
            prefetches.append(Prefetch(field, queryset=qs))

        queryset = self.queryset
        if prefetches:
            queryset = queryset.prefetch_related(*prefetches)

        return queryset

    def annotate(self, *args, **kwargs):
        """Annotate query args."""
        self.queryset = self.queryset.annotate(*args, **kwargs)
        return self


class FastQuery(FastQueryCompatMixin, object):
    """FastQuery is a fast queryset that supports prefetching."""

    def __init__(self, queryset):
        """Initialise the FastQuery."""
        if isinstance(queryset, models.Manager):
            queryset = queryset.all()
        self.queryset = queryset
        self.model = queryset.model
        self.prefetches = {}
        self.fields = None
        self.pk_field = queryset.model._meta.pk.attname
        self._data = None
        self._my_ids = None

    def execute(self):
        """Execute."""
        if self._data is not None:
            return self._data

        # TODO: check if queryset already has values() called
        # TODO: use self.fields
        qs = self.queryset._clone()  # pylint: disable=protected-access

        use_fastquery = getattr(self.model, "USE_FASTQUERY", True)

        if use_fastquery:
            data = list(qs.values())

            self.merge_prefetch(data)
            self._data = FastList(
                map(lambda obj: FastObject(obj, pk_field=self.pk_field), data)
            )
        else:

            def make_prefetch(fast_prefetch):
                """Make a prefetch."""
                queryset = None
                if fast_prefetch.query is not None:
                    queryset = fast_prefetch.query.queryset
                return Prefetch(fast_prefetch.field, queryset=queryset)

            prefetches = [
                make_prefetch(prefetch) for prefetch in self.prefetches.values()
            ]
            if prefetches:
                qs = qs.prefetch_related(*prefetches)
            self._data = FastList(
                map(lambda obj: SlowObject(obj, pk_field=self.pk_field), qs.all())
            )

        return self._data

    def __iter__(self):
        """Allow this to be cast to an iterable.

        Note: as with Django QuerySets, calling this will cause the
              query to execute.
        """
        return iter(self.execute())

    def __getitem__(self, k):
        """Support list index and slicing, similar to Django QuerySet."""
        if self._data is not None:
            # Query has already been executed. Extract from local cache.
            return self._data[k]

        # Query hasn't yet been executed. Update queryset.
        if isinstance(k, slice):
            if k.step:
                raise TypeError("Stepping not supported")

            start = int(k.start) if k.start is not None else None
            stop = int(k.stop) if k.stop is not None else None
            self.queryset.query.set_limits(start, stop)
        else:
            self.queryset.query.set_limits(k, k + 1)
        return self.execute()

    def __len__(self):
        """Return the length."""
        return len(self.execute())

    def get_ids(self, ids):
        """Return a queryset filtered by IDs."""
        self.queryset = self.queryset.filter(pk__in=ids)
        return self

    def merge_prefetch(self, data):
        """Merge prefetches into data."""
        model = self.queryset.model

        rel_func_map = {
            "fk": self.merge_fk,
            "o2o": self.merge_o2o,
            "o2or": self.merge_o2or,
            "m2m": self.merge_m2m,
            "m2o": self.merge_m2o,
        }

        for prefetch in self.prefetches.values():
            # TODO: here we assume we're dealing with Prefetch objects
            #       we could support field notation as well.
            field, rel_type = get_model_field_and_type(model, prefetch.field)
            if not rel_type:
                # Not a relational field... weird.
                # TODO: maybe raise?
                continue

            func = rel_func_map[rel_type]
            func(data, field, prefetch)

        return data

    def _make_id_map(self, items, pk_field="id"):
        """Make an ID map."""
        return {item[pk_field]: item for item in items}

    def _get_my_ids(self, data):
        """Get my IDs."""
        if self._my_ids is None:
            pk_field = (
                self.queryset.model._meta.pk.attname  # pylint: disable=protected-access
            )
            self._my_ids = {o[pk_field] for o in data}

        return self._my_ids

    def merge_fk(self, data, field, prefetch):
        """Merge a foreign key."""
        # Strategy: pull out field_id values from each row, pass to
        #           prefetch queryset using `pk__in`.

        id_field = field.attname
        ids = {row[id_field] for row in data if id_field in row}
        prefetched_data = prefetch.query.get_ids(ids).execute()
        id_map = self._make_id_map(prefetched_data)

        for row in data:
            row[field.name] = id_map.get(row[id_field], None)

        return data

    def merge_o2o(self, data, field, prefetch):
        """Merge a one-to-one."""
        # Same as FK.
        return self.merge_fk(data, field, prefetch)

    def merge_o2or(self, data, field, prefetch, m2o_mode=False):
        """Merge a one-to-one remote."""
        # Strategy: get my IDs, filter remote model for rows pointing at
        #           my IDs.
        #           For m2o_mode, account for there many objects, while
        #           for o2or only support one reverse object.

        my_ids = self._get_my_ids(data)

        # If prefetching User.profile, construct filter like:
        #   Profile.objects.filter(user__in=<user_ids>)
        remote_field = field.remote_field.attname
        remote_filter_key = f"{remote_field}__in"
        filter_args = {remote_filter_key: my_ids}

        # Fetch remote objects
        remote_objects = prefetch.query.filter(**filter_args).execute()
        id_map = self._make_id_map(data, pk_field=self.pk_field)

        field_name = prefetch.field
        reverse_found = []  # IDs of local objects that were reversed
        for remote_obj in remote_objects:
            # Pull out ref on remote object pointing at us, and
            # get local object. There *should* always be a matching
            # local object because the remote objects were filtered
            # for those that referenced the local IDs.
            reverse_ref = remote_obj[remote_field]
            local_obj = id_map[reverse_ref]

            if m2o_mode:
                # in many-to-one mode, this is a list
                if field_name not in local_obj:
                    local_obj[field_name] = FastList([])
                local_obj[field_name].append(remote_obj)
            else:
                # in o2or mode, there can only be one
                local_obj[field_name] = remote_obj

            reverse_found.append(reverse_ref)

        # Set value to None for objects that didn't have a matching prefetch
        not_found = my_ids - set(reverse_found)
        for pk in not_found:
            id_map[pk][field_name] = FastList([]) if m2o_mode else None

        return data

    def merge_m2m(self, data, field, prefetch):
        """Merge a many-to-many."""
        # Strategy: pull out all my IDs, do a reverse filter on remote object.
        # e.g.: If prefetching User.groups, do
        #       Groups.filter(users__in=<user_ids>)

        my_ids = self._get_my_ids(data)

        base_qs = prefetch.query.queryset  # base queryset on remote model
        # get pk field name
        remote_pk_field = (
            base_qs.model._meta.pk.attname  # pylint: disable=protected-access
        )
        reverse_field = field.remote_field.name

        if reverse_field is None:
            # Note: We can't just reuse self.queryset here because it's
            #       been sliced already.
            filters = {f"{field.attname}__isnull": False}
            qs = self.queryset.model.objects.filter(pk__in=my_ids, **filters)
            joins = list(qs.values_list(field.attname, self.pk_field))
        else:
            # Get reverse mapping (for User.groups, get Group.users)
            # Note: `qs` already has base filter applied on remote model.
            filters = {f"{reverse_field}__in": my_ids}
            joins = list(
                base_qs.filter(**filters).values_list(remote_pk_field, reverse_field)
            )

        # Fetch remote objects, as values.
        remote_ids = {o[0] for o in joins}
        remote_objects = prefetch.query.get_ids(remote_ids).execute()
        id_map = self._make_id_map(remote_objects, pk_field=remote_pk_field)

        # Create mapping of local ID -> remote objects
        to_field = prefetch.field
        object_map = defaultdict(FastList)
        for remote_id, local_id in joins:
            if remote_id in id_map:
                object_map[local_id].append(id_map[remote_id])

        # Merge into working data set.
        for row in data:
            row[to_field] = object_map[row[self.pk_field]]

        return data

    def merge_m2o(self, data, field, prefetch):
        """Merge a many-to-one."""
        # Same as o2or but allow for many reverse objects.
        return self.merge_o2or(data, field, prefetch, m2o_mode=True)
