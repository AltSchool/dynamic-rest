SECRET_KEY = 'test'

DATABASES = {
  'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': 'db.sqlite3',
    'USER': '',
    'PASSWORD': '',
    'HOST': '',
    'PORT': ''
  }
}

MIDDLEWARE_CLASSES = ()

INSTALLED_APPS = (
  'tests',
)
