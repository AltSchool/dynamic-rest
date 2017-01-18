import json
import requests
from .exceptions import AuthenticationFailed, BadRequest, DoesNotExist
from .resource import DRESTResource

AUTH_ENDPOINT = '/accounts/login/'


class DRESTClient(object):

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
            sessionid = authentication.get('sessionid')
            if token:
                self._use_token(token)
            if sessionid:
                self._use_sessionid(sessionid)

    def __repr__(self):
        return '%s%s' % (
            self._host,
            '/%s/' % self._version if self._version else ''
        )

    def _use_token(self, value):
        self._token = value
        self._authenticated = bool(value)
        self._client.headers.update({
            'Authorization': self._token if value else ''
        })

    def _use_sessionid(self, value):
        self._sessionid = value
        self._authenticated = bool(value)
        self._client.headers.update({
            'Cookie': 'sessionid=%s' % value if value else ''
        })

    def __getattr__(self, key):
        key = key.lower()
        return self._resources.get(key, DRESTResource(self, key))

    def _login(self, raise_exception=True):
        username = self._username
        password = self._password
        response = requests.post(
            self._build_url(AUTH_ENDPOINT),
            data={
                'login': username,
                'password': password
            },
            allow_redirects=False
        )
        if raise_exception:
            response.raise_for_status()

        self._use_sessionid(response.cookies.get('sessionid'))

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

        return json.loads(response.content)
