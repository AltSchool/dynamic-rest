from django.conf import settings as django_settings
from django.test.signals import setting_changed

DYNAMIC_REST = {
    # DEBUG: enable/disable internal debugging
    'DEBUG': False,

    # AUTH_ENDPOINT: authentication endpoint (used by DREST client)
    'AUTH_LOGIN_ENDPOINT': '/accounts/login/',

    # AUTH_COOKIE_NAME: sessionid cookie
    'AUTH_COOKIE_NAME': 'sessionid',

    # AUTH_TYPE: authentication type
    'AUTH_TYPE': 'JWT',

    # ENABLE_BROWSABLE_API: enable/disable the browsable API.
    # It can be useful to disable it in production.
    'ENABLE_BROWSABLE_API': True,

    # ENABLE_LINKS: enable/disable relationship links
    'ENABLE_LINKS': True,

    # ENABLE_SERIALIZER_CACHE: enable/disable caching of related serializers
    'ENABLE_SERIALIZER_CACHE': True,

    # ENABLE_SERIALIZER_OPTIMIZATIONS: enable/disable representation speedups
    'ENABLE_SERIALIZER_OPTIMIZATIONS': True,

    # ENABLE_BULK_PARTIAL_CREATION: enable/disable partial creation in bulk
    'ENABLE_BULK_PARTIAL_CREATION': False,

    # ENABLE_BULK_UPDATE: enable/disable update in bulk
    'ENABLE_BULK_UPDATE': True,

    # DEFER_MANY_RELATIONS: automatically defer many-relations, unless
    # `deferred=False` is explicitly set on the field.
    'DEFER_MANY_RELATIONS': False,

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
}


class Settings(object):

    def __init__(self, name, defaults, settings):
        self.name = name
        self.defaults = defaults
        self.keys = set(defaults.keys())

        self._cache = {}
        self._reload(getattr(settings, self.name, {}))

        setting_changed.connect(self._settings_changed)

    def _reload(self, value):
        """Reload settings after a change."""
        self.settings = value
        self._cache = {}

    def __getattr__(self, attr):
        """Get a setting."""
        if attr not in self._cache:

            if attr not in self.keys:
                raise AttributeError("Invalid API setting: '%s'" % attr)

            if attr in self.settings:
                val = self.settings[attr]
            else:
                val = self.defaults[attr]

            # Cache the result
            self._cache[attr] = val

        return self._cache[attr]

    def _settings_changed(self, *args, **kwargs):
        """Handle changes to core settings."""
        setting, value = kwargs['setting'], kwargs['value']
        if setting == self.name:
            self._reload(value)


settings = Settings('DYNAMIC_REST', DYNAMIC_REST, django_settings)
