import os
SECRET_KEY = 'test'
INSTALL_DIR = '/usr/local/dynamic-rest/'
STATIC_URL = '/static/'
STATIC_ROOT = INSTALL_DIR + 'www/static'

DEBUG = True

DATABASES = {
  'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': INSTALL_DIR + 'db.sqlite3',
    'USER': '',
    'PASSWORD': '',
    'HOST': '',
    'PORT': ''
  }
}

MIDDLEWARE_CLASSES = ()

INSTALLED_APPS = (
  'rest_framework',
  'django.contrib.staticfiles',
  'tests',
)

ROOT_URLCONF = 'tests.urls'

BASE_DIR = os.path.dirname(__file__)
