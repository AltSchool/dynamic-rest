import os

BASE_DIR = os.path.dirname(__file__)

SECRET_KEY = 'test'
INSTALL_DIR = '/usr/local/altschool/dynamic-rest/'
STATIC_URL = '/static/'
STATIC_ROOT = INSTALL_DIR + 'www/static'

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
        'NAME': os.path.abspath('db.sqlite3'),
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': ''
    }

MIDDLEWARE_CLASSES = ()

INSTALLED_APPS = (
    'django.contrib.staticfiles',
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sites',
    'dynamic_rest',
    'rest_framework',
    'benchmarks',
)

ROOT_URLCONF = 'benchmarks.urls'

DYNAMIC_REST = {
    'ENABLE_LINKS': False
}
