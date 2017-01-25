import json
import requests
from .exceptions import AuthenticationFailed, BadRequest, DoesNotExist
from .resource import DRESTResource
from dynamic_rest.conf import settings


class DRESTClient(object):
    """DREST Python client.

    Exposes a DREST API to Python using a Django-esque interface.
    Resources are available on the client through access-by-name.

    Arguments:
        host: hostname to a DREST API
        version: version (defaults to no version)
        client: HTTP client (defaults to requests.session)
        scheme: defaults to https
        authentication: if unset, authentication is disabled.
            If set, provides credentials: {
                usename: login username,
                password: login password,
                token: authorization token,
                cookie: session cookie
            }
            Either username/password, token, or cookie should be provided.

    Examples:

    Assume there is a DREST resource at "https://my.api.io/v0/users",
    and that we can access this resource with an auth token "secret".

    Getting a client:

        client = DRESTClient(
            'my.api.io',
            version='v0',
            authentication={'token': 'secret'}
        )

    Getting a single record of the Users resource

        client.Users.get('123')

    Getting all records (automatic pagination):

        client.Users.all()

    Filtering records:

        client.Users.filter(name__icontains='john')
        other_users = client.Users.exclude(name__icontains='john')

    Ordering records:

        users = client.Users.sort('-name')

    Including / excluding fields:

        users = client.Users.all()
        .excluding('birthday')
        .including('events.*')
        .get('123')

    Mapping by field:

        users_by_id = client.Users.map()
        users_by_name = client.Users.map('name')

    Updating records:

        user = client.Users.first()
        user.name = 'john'
        user.save()

    Creating records:

        user = client.Users.create(name='john')
    """
    def __init__(
        self,
        host,
        version=None,
        client=None,
        scheme='https',
        authentication=None
    ):
        self._host = host
        self._version = version
        self._client = client or requests.session()
        self._client.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self._resources = {}
        self._scheme = scheme
        self._authenticated = True
        self._authentication = authentication

        if authentication:
            self._authenticated = False
            token = authentication.get('token')
            cookie = authentication.get('cookie')
            if token:
                self._use_token(token)
            if cookie:
                self._use_cookie(cookie)

    def __repr__(self):
        return '%s%s' % (
            self._host,
            '/%s/' % self._version if self._version else ''
        )

    def _use_token(self, value):
        self._token = value
        self._authenticated = bool(value)
        self._client.headers.update({
            'Authorization': '%s %s' % (
                settings.AUTH_TYPE, self._token if value else ''
            )
        })

    def _use_cookie(self, value):
        self._cookie = value
        self._authenticated = bool(value)
        self._client.headers.update({
            'Cookie': '%s=%s' % (settings.AUTH_COOKIE_NAME, value)
        })

    def __getattr__(self, key):
        key = key.lower()
        return self._resources.get(key, DRESTResource(self, key))

    def _login(self, raise_exception=True):
        username = self._username
        password = self._password
        response = requests.post(
            self._build_url(settings.AUTH_LOGIN_ENDPOINT),
            data={
                'login': username,
                'password': password
            },
            allow_redirects=False
        )
        if raise_exception:
            response.raise_for_status()

        self._use_cookie(response.cookies.get(settings.AUTH_COOKIE_NAME))

    def _authenticate(self, raise_exception=True):
        response = None
        if not self._authenticated:
            self._login(self._username, self._password, raise_exception)
        if raise_exception and not self._authenticated:
            raise AuthenticationFailed(
                response.text if response else 'Unknown error'
            )
        return self._authenticated

    def _build_url(self, url, prefix=None):
        if not url.startswith('/'):
            url = '/%s' % url

        if prefix:
            if not prefix.startswith('/'):
                prefix = '/%s' % prefix

            url = '%s%s' % (prefix, url)
        return '%s://%s%s' % (self._scheme, self._host, url)

    def request(self, method, url, params=None, data=None):
        self._authenticate()
        response = self._client.request(
            method,
            self._build_url(url, prefix=self._version),
            params=params,
            data=data
        )

        if response.status_code == 401:
            raise AuthenticationFailed()

        if response.status_code == 404:
            raise DoesNotExist()

        if response.status_code >= 400:
            raise BadRequest()

        return json.loads(response.content.decode('utf-8'))
