import json
import requests
import inflection


API_AUTH_ENDPOINT = '/accounts/login/'


class AuthenticationFailed(Exception):
    pass


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
        self.host = host
        self.version = version
        self.session = session or requests.session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.sessionid = sessionid
        self.username = username
        self.password = password
        self.token = token
        self.scheme = scheme
        self.authorization_type = authorization_type

    @property
    def token(self):
        return self._token

    @token.setter
    def token(self, value):
        self._token = value
        self.authenticated = bool(value)
        if value:
            self.session.headers.update({
                'Authorization': '%s %s' % (
                    self.authorization_type,
                    self._token
                )
            })

    @property
    def sessionid(self):
        return self._sessionid

    @sessionid.setter
    def sessionid(self, value):
        self._sessionid = value
        self.authenticated = bool(value)
        if value:
            self.session.headers.update({
                'Cookie': 'sessionid=%s' % value
            })

    def authenticate(self, raise_exception=True):
        response = None
        if not self.authenticated:
            username = self.username
            password = self.password
            response = requests.post(
                self.build_url(API_AUTH_ENDPOINT),
                data={
                    'login': username,
                    'password': password
                },
                allow_redirects=False
            )
            if raise_exception:
                response.raise_for_status()

            self.sessionid = response.cookies.get('sessionid')

        if raise_exception and not self.authenticated:
            raise AuthenticationFailed(
                response.text if response else 'Unknown error'
            )
        return self.authenticated

    def build_url(self, url, prefix=None):
        if not url.startswith('/'):
            url = '/%s' % url

        if prefix:
            if not prefix.startswith('/'):
                prefix = '/%s' % prefix

            url = '%s%s' % (prefix, url)
        return '%s://%s%s' % (self.scheme, self.host, url)

    def save(
        self,
        resource,
        data,
        **kwargs
    ):
        if 'id' in data:
            update = True
            pk = data['id']
        else:
            update = False
            pk = None

        data = json.dumps(data)
        url = self.get_resource_url(resource, pk)
        try:
            verb = 'put' if update else 'post'
            response = getattr(self, verb)(url, data=data)
            return response
        except requests.exceptions.HTTPError as e:
            return e.response

    def get_resource_body(self, response, resource, many=False):
        body = json.loads(response.text)
        key = resource if many else inflection.singularize(resource)
        return body[key]

    def get_resource_url(self, resource, pk=None):
        return '%s/%s' % (
            resource,
            '%s/' % pk if pk else ''
        )

    def find(
        self,
        resource,
        *args,
        **kwargs
    ):
        pk = args[0] if len(args) else None
        many = False if pk else True
        url = self.get_resource_url(resource, pk)
        filters = kwargs.get('filters')
        include = kwargs.get('include')
        params = []
        if filters:
            for key, value in filters.items():
                params.append('filter{%s}=%s' % (key, value))
        if include:
            for key in include:
                params.append('include[]=%s' % key)
        if params:
            url = '%s?%s' % (url, '&'.join(params))
        response = self.get(url)
        return self.get_resource_body(response, resource, many=many)

    def destroy(
        self,
        resource,
        pk
    ):
        url = self.get_resource_url(resource, pk)
        try:
            return self.delete(url)
        except requests.exceptions.HTTPError as e:
            return e.response

    def post(self, url, params=None, data=None):
        return self.request('POST', url, params, data)

    def get(self, url, params=None, data=None):
        return self.request('GET', url, params, data)

    def put(self, url, params=None, data=None):
        return self.request('PUT', url, params, data)

    def delete(self, url, params=None, data=None):
        return self.request('DELETE', url, params, data)

    def request(self, method, url, params=None, data=None):
        self.authenticate()
        response = self.session.request(
            method,
            self.build_url(url, prefix=self.version),
            params=params,
            data=data
        )
        if response.status_code == 401:
            raise AuthenticationFailed()

        response.raise_for_status()
        return response
