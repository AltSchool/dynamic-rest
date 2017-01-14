import json
import requests
from .exceptions import AuthenticationFailed
from .resource import APIResource

API_AUTH_ENDPOINT = '/accounts/login/'


class APIClient(object):

    def __init__(
        self,
        host,
        version=None,
        session=None,
        sessionid=None,
        username=None,
        password=None,
        token=None,
        authorization_type='JWT',
        scheme='https'
    ):
        self._authorization_type = authorization_type
        self._host = host
        self._version = version
        self._session = session or requests.session()
        self._session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self._username = username
        self._password = password
        self._scheme = scheme
        self._authenticated = False
        self._resources = {}

        if token:
            self.token = token
        if sessionid:
            self.sessionid = sessionid

    @property
    def token(self):
        return self._token

    @token.setter
    def token(self, value):
        self._token = value
        self._authenticated = bool(value)
        if value:
            self._session.headers.update({
                'Authorization': '%s %s' % (
                    self._authorization_type,
                    self._token
                )
            })

    @property
    def sessionid(self):
        return self._sessionid

    @sessionid.setter
    def sessionid(self, value):
        self._sessionid = value
        self._authenticated = bool(value)
        if value:
            self._session.headers.update({
                'Cookie': 'sessionid=%s' % value
            })

    def post(self, url, params=None, data=None):
        return self._request('POST', url, params, data)

    def get(self, url, params=None, data=None):
        return self._request('GET', url, params, data)

    def put(self, url, params=None, data=None):
        return self._request('PUT', url, params, data)

    def delete(self, url, params=None, data=None):
        return self._request('DELETE', url, params, data)

    def __getattr__(self, key):
        key = key.lower()
        return self._resources.get(key, APIResource(self, key))

    def _authenticate(self, raise_exception=True):
        response = None
        if not self._authenticated:
            username = self._username
            password = self._password
            response = requests.post(
                self._build_url(API_AUTH_ENDPOINT),
                data={
                    'login': username,
                    'password': password
                },
                allow_redirects=False
            )
            if raise_exception:
                response.raise_for_status()

            self.sessionid = response.cookies.get('sessionid')

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

    def _request(self, method, url, params=None, data=None):
        self._authenticate()
        response = self._session.request(
            method,
            self._build_url(url, prefix=self._version),
            params=params,
            data=data
        )
        if response.status_code == 401:
            raise AuthenticationFailed()

        response.raise_for_status()
        return json.loads(response.content)
