import inspect

from django.conf import settings as django_settings
from django.test.signals import setting_changed

DYNAMIC_REST = {
    # DEBUG: enable/disable internal debugging
    'DEBUG': False,

    # ENABLE_BROWSABLE_API: enable/disable the browsable API.
    # It can be useful to disable it in production.
    'ENABLE_BROWSABLE_API': True,

    # ENABLE_LINKS: enable/disable relationship links
    'ENABLE_LINKS': True,

    # ENABLE_SERIALIZER_CACHE: enable/disable caching of related serializers
    'ENABLE_SERIALIZER_CACHE': True,

    # ENABLE_SERIALIZER_OBJECT_CACHE: enable/disable caching of serialized
    # objects within a serializer instance/context. This can yield
    # significant performance improvements in cases where the same objects
    # are sideloaded repeatedly.
    'ENABLE_SERIALIZER_OBJECT_CACHE': True,

    # ENABLE_SERIALIZER_OPTIMIZATIONS: enable/disable representation speedups
    'ENABLE_SERIALIZER_OPTIMIZATIONS': True,

    # ENABLE_BULK_PARTIAL_CREATION: enable/disable partial creation in bulk
    'ENABLE_BULK_PARTIAL_CREATION': False,

    # ENABLE_BULK_UPDATE: enable/disable update in bulk
    'ENABLE_BULK_UPDATE': True,

    # ENABLE_PATCH_ALL: enable/disable patch by queryset
    'ENABLE_PATCH_ALL': False,

    # DEFER_MANY_RELATIONS: automatically defer many-relations, unless
    # `deferred=False` is explicitly set on the field.
    'DEFER_MANY_RELATIONS': False,

    # LIST_SERIALIZER_CLASS: Globally override the list serializer class.
    # Default is `DynamicListSerializer` and also can be overridden for
    # each serializer class by setting `Meta.list_serializer_class`.
    'LIST_SERIALIZER_CLASS': None,

    # MAX_PAGE_SIZE: global setting for max page size.
    # Can be overriden at the viewset level.
    'MAX_PAGE_SIZE': None,

    # PAGE_QUERY_PARAM: global setting for the pagination query parameter.
    # Can be overriden at the viewset level.
    'PAGE_QUERY_PARAM': 'page',

    # PAGE_SIZE: global setting for page size.
    # Can be overriden at the viewset level.
    'PAGE_SIZE': None,

    # PAGE_SIZE_QUERY_PARAM: global setting for the page size query parameter.
    # Can be overriden at the viewset level.
    'PAGE_SIZE_QUERY_PARAM': 'per_page',

    # ADDITIONAL_PRIMARY_RESOURCE_PREFIX: String to prefix additional
    # instances of the primary resource when sideloading.
    'ADDITIONAL_PRIMARY_RESOURCE_PREFIX': '+',

    # Enables host-relative links.  Only compatible with resources registered
    # through the dynamic router.  If a resource doesn't have a canonical
    # path registered, links will default back to being resource-relative urls
    'ENABLE_HOST_RELATIVE_LINKS': True,

    # Enables caching of serializer fields to speed up serializer usage
    # Needs to also be configured on a per-serializer basis
    'ENABLE_FIELDS_CACHE': False,

    # Enables use of hashid fields
    'ENABLE_HASHID_FIELDS': False,

    # Salt value to salt hash ids.
    # Needs to be non-nullable if 'ENABLE_HASHID_FIELDS' is set to True
    'HASHIDS_SALT': None,
}


# Attributes where the value should be a class (or path to a class)
CLASS_ATTRS = [
    'LIST_SERIALIZER_CLASS',
]


class Settings(object):
    def __init__(self, name, defaults, settings, class_attrs=None):
        self.name = name
        self.defaults = defaults
        self.keys = set(defaults.keys())
        self.class_attrs = class_attrs

        self._cache = {}
        self._reload(getattr(settings, self.name, {}))

        setting_changed.connect(self._settings_changed)

    def _reload(self, value):
        """Reload settings after a change."""
        self.settings = value
        self._cache = {}

    def _load_class(self, attr, val):
        if inspect.isclass(val):
            return val
        elif isinstance(val, str):
            parts = val.split('.')
            module_path = '.'.join(parts[:-1])
            class_name = parts[-1]
            mod = __import__(module_path, fromlist=[class_name])
            return getattr(mod, class_name)
        elif val:
            raise Exception("%s must be string or a class" % attr)

    def __getattr__(self, attr):
        """Get a setting."""
        if attr not in self._cache:

            if attr not in self.keys:
                raise AttributeError("Invalid API setting: '%s'" % attr)

            if attr in self.settings:
                val = self.settings[attr]
            else:
                val = self.defaults[attr]

            if attr in self.class_attrs and val:
                val = self._load_class(attr, val)

            # Cache the result
            self._cache[attr] = val

        return self._cache[attr]

    def _settings_changed(self, *args, **kwargs):
        """Handle changes to core settings."""
        setting, value = kwargs['setting'], kwargs['value']
        if setting == self.name:
            self._reload(value)


settings = Settings('DYNAMIC_REST', DYNAMIC_REST, django_settings, CLASS_ATTRS)
