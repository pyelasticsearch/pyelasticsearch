from six import iteritems
import requests
import simplejson as json  # for use_decimal
from simplejson import JSONDecodeError
try:
    # PY3
    from urllib.parse import urlencode, quote_plus, urlparse
except ImportError:
    # PY2
    from urllib import urlencode, quote_plus
    from urlparse import urlparse

from pyelasticsearch.utils import obj_to_utf8, obj_to_query
from pyelasticsearch.exceptions import InvalidJsonResponseError

class RequestsHandler(object):
    def __init__(self, host, port=9200, secure=False, timeout=60):
        self.timeout = timeout
        self.session = requests.session()
        self.host = host
        self.port = port
        self.schema = ('https' if secure else 'http')
        self.base = '%s://%s:%s'%(self.schema, self.host, self.port)

    def _decode_response(self, response):
        """Return a native-Python representation of a response's JSON blob."""
        try:
            json_response = response.json()
        except JSONDecodeError:
            raise InvalidJsonResponseError(response)
        return json_response

    def do(self, method, uri, parameters=None, headers=None, body=None):
        req_method = getattr(self.session, method.lower())
        extra = {'data': body} if body else {}
        if parameters:
            uri = '%s?%s'%(
                self.base,
                uri,
                urlencode(dict((k, obj_to_utf8(obj_to_query(v))) for k, v in
                                iteritems(parameters)))
            )

        resp = req_method(self.base+uri, timeout=self.timeout, **extra)
        return self._decode_response(resp), resp.status_code

def handler_from_url(url, **kwargs):
    parsed_url = urlparse(url)
    if url.find('://') < 0:
        url = 'http://%s'%url
    host = parsed_url.hostname
    port = parsed_url.port
    secure = parsed_url.scheme == 'https'
    return RequestsHandler(host=host, port=port, secure=secure, **kwargs)
