from six import iteritems
import requests
import simplejson as json  # for use_decimal
from simplejson import JSONDecodeError
try:
    # PY3
    from urllib.parse import urlencode, quote_plus
except ImportError:
    # PY2
    from urllib import urlencode, quote_plus

from pyelasticsearch.utils import obj_to_utf8, obj_to_query
from pyelasticsearch.exceptions import InvalidJsonResponseError

class RequestsHandler(object):
    def __init__(self, es, timeout=60):
        self.es = es
        self.timeout = timeout
        self.session = requests.session()

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
                uri,
                urlencode(dict((k, obj_to_utf8(obj_to_query(v))) for k, v in
                                iteritems(parameters)))
            )

        resp = req_method(uri, timeout=self.timeout, **extra)
        return self._decode_response(resp), resp.status_code
