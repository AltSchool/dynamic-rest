import os

BASE_DIR = os.path.dirname(__file__)

SECRET_KEY = 'test'
INSTALL_DIR = '/usr/local/altschool/dynamic-rest/'

STATIC_URL = '/static/'
STATIC_ROOT = os.environ.get('STATIC_ROOT', INSTALL_DIR + 'www/static')

DEBUG = True

DATABASES = {}
if os.environ.get('DATABASE_URL'):
    # remote database
    import dj_database_url
    DATABASES['default'] = dj_database_url.config()
else:
    # local sqlite database file
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': INSTALL_DIR + 'db.sqlite3',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': ''
    }

MIDDLEWARE_CLASSES = ()

INSTALLED_APPS = (
    'rest_framework',
    'django.contrib.staticfiles',
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sites',
    'tests',
)

REST_FRAMEWORK = {
    'PAGE_SIZE': 50,
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'dynamic_rest.renderers.DynamicBrowsableAPIRenderer'
    )
}
ROOT_URLCONF = 'tests.urls'


TEMPLATE_DIRS = (
    os.path.join(BASE_DIR, '../dynamic_rest/templates'),
)

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, '../dynamic_rest/static'),
)

DYNAMIC_REST = {
    'ENABLE_LINKS': True,
    'DEBUG': os.environ.get('DYNAMIC_REST_DEBUG', 'false').lower() == 'true'
}
