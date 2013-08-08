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

try:
    from thrift.transport import TTransport
    from thrift.transport import TSocket
    from thrift.protocol import TBinaryProtocol
    from pyelasticsearch.pyelasticsearchthrift import Rest as pyesRest, ttypes as pyesTtypes
    THRIFT_ENABLED = True
except:
    THRIFT_ENABLED = False

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

    def request(self, method, uri, parameters=None, headers=None, body=None):
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


class ThriftHandler(object):
    def __init__(self, host, port=9500, framed_transport=False, timeout=60, recycle=True):
        socket = TSocket.TSocket(host, port)
        if timeout is not None:
            socket.setTimeout(timeout * 1000.0)
        if framed_transport:
            transport = TTransport.TFramedTransport(socket)
        else:
            transport = TTransport.TBufferedTransport(socket)
        protocol = TBinaryProtocol.TBinaryProtocolAccelerated(transport)
        self.client = pyesRest.Client(protocol)
        transport.open()
        # transport.close()

    def request(self, method, uri, parameters=None, headers=None, body=None):
        print uri
        res = pyesTtypes.RestRequest(pyesTtypes.Method._NAMES_TO_VALUES[method.upper()], uri, parameters, {}, body)
        response = self.client.execute(res)
        return json.loads(response.body), response.status


THRIFT_PORTS = [9500]

def handler_from_url(url, **kwargs):
    parsed_url = urlparse(url)
    if url.find('://') < 0:
        url = 'http://%s'%url
    host = parsed_url.hostname
    port = parsed_url.port
    secure = parsed_url.scheme == 'https'
    if THRIFT_ENABLED and port in THRIFT_PORTS:
        return ThriftHandler(host=host, port=port)
    return RequestsHandler(host=host, port=port, secure=secure, **kwargs)
