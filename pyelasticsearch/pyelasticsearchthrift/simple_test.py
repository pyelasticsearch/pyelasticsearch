#!/usr/bin/env python
from __future__ import absolute_import
import sys
import pprint
from urlparse import urlparse
from thrift.transport import TTransport
from thrift.transport import TSocket
from thrift.transport import THttpClient
from thrift.protocol import TBinaryProtocol

from .Rest import Client
from .ttypes import *

pp = pprint.PrettyPrinter(indent = 4)
host = 'mediante.local'
port = 9500
uri = ''
framed = False
http = False
argi = 1

socket = TSocket.TSocket(host, port)
transport = TTransport.TBufferedTransport(socket)
protocol = TBinaryProtocol.TBinaryProtocol(transport)
client = Client(protocol)
transport.open()

res = RestRequest(Method._NAMES_TO_VALUES["POST"], "/test-index/test-type/1", {}, {})
print client.execute(res)

transport.close()
