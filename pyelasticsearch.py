# -*- coding: utf-8 -*-
"""
Create ElasticSearch connection
>>> import time
>>> conn = ElasticSearch('http://localhost:9200/')

Add a few documents

>>> conn.index({"name":"Joe Tester"}, "test-index", "test-type", 1)
{'_type': 'test-type', '_id': '1', 'ok': True, '_index': 'test-index'}
>>> conn.index({"name":"Bill Baloney"}, "test-index", "test-type", 2)
{'_type': 'test-type', '_id': '2', 'ok': True, '_index': 'test-index'}

Get one

>>> conn.refresh(["test-index"]) # doctest: +ELLIPSIS
{'ok': True, '_shards': {...}}
>>> conn.get("test-index", "test-type", 1)
{'_type': 'test-type', '_id': '1', '_source': {'name': 'Joe Tester'}, '_index': 'test-index'}

Get a count
>>> conn.count("name:joe")
{'count': 1, '_shards': {'successful': 5, 'failed': 0, 'total': 5}}

Search

>>> conn.search("name:joe")
{'hits': {'hits': [{'_type': 'test-type', '_id': '1', '_source': {'name': 'Joe Tester'}, '_index': 'test-index'}], 'total': 1}, '_shards': {'successful': 5, 'failed': 0, 'total': 5}}

Terms

>>> conn.terms(['name'])
{'docs': {'max_doc': 2, 'num_docs': 2, 'deleted_docs': 0}, 'fields': {'name': {'terms': [{'term': 'baloney', 'doc_freq': 1}, {'term': 'bill', 'doc_freq': 1}, {'term': 'joe', 'doc_freq': 1}, {'term': 'tester', 'doc_freq': 1}]}}, '_shards': {'successful': 5, 'failed': 0, 'total': 5}}
>>> conn.terms(['name'], indexes=['test-index'])
{'docs': {'max_doc': 2, 'num_docs': 2, 'deleted_docs': 0}, 'fields': {'name': {'terms': [{'term': 'baloney', 'doc_freq': 1}, {'term': 'bill', 'doc_freq': 1}, {'term': 'joe', 'doc_freq': 1}, {'term': 'tester', 'doc_freq': 1}]}}, '_shards': {'successful': 5, 'failed': 0, 'total': 5}}
>>> conn.terms(['name'], min_freq=2)
{'docs': {'max_doc': 2, 'num_docs': 2, 'deleted_docs': 0}, 'fields': {'name': {'terms': []}}, '_shards': {'successful': 5, 'failed': 0, 'total': 5}}

More Like This
>>> conn.index({"name":"Joe Test"}, "test-index", "test-type", 3)
{'_type': 'test-type', '_id': '3', 'ok': True, '_index': 'test-index'}
>>> conn.refresh(["test-index"]) # doctest: +ELLIPSIS
{'ok': True, '_shards': {...}}
>>> conn.morelikethis("test-index", "test-type", 1, ['name'], min_term_frequency=1, min_doc_freq=1)
{'hits': {'hits': [{'_type': 'test-type', '_id': '3', '_source': {'name': 'Joe Test'}, '_index': 'test-index'}], 'total': 1}, '_shards': {'successful': 5, 'failed': 0, 'total': 5}}
>>> conn.delete("test-index", "test-type", 3)
{'_type': 'test-type', '_id': '3', 'ok': True, '_index': 'test-index'}

Delete Bill

>>> conn.delete("test-index", "test-type", 2)
{'_type': 'test-type', '_id': '2', 'ok': True, '_index': 'test-index'}

Delete the index

>>> conn.delete_index("test-index")
{'acknowledged': True, 'ok': True}

Create the index anew

>>> conn.create_index("test-index")
{'acknowledged': True, 'ok': True}

Try (and fail) to create an existing index

>>> conn.create_index("test-index")
{'error': '[test-index] Already exists'}

Put mapping

>>> conn.put_mapping("test-type", {"test-type" : {"properties" : {"name" : {"type" : "string", "store" : "yes"}}}})
{'acknowledged': True, 'ok': True}

Get status

>>> conn.status(["test-index"]) # doctest: +ELLIPSIS
{'indices': {'test-index': ...}}

>>> conn.flush(["test-index"]) # doctest: +ELLIPSIS
{'ok': True, '_shards': {...}}

>>> conn.refresh(["test-index"]) # doctest: +ELLIPSIS
{'ok': True, '_shards': {...}}

>>> conn.optimize(["test-index"]) # doctest: +ELLIPSIS
{'ok': True, '_shards': {...}}

Test adding with automatic id generation
>>> conn.index({"name":"Joe Tester"}, "test-index", "test-type") # doctest: +ELLIPSIS
{'_type': 'test-type', '_id': '...', 'ok': True, '_index': 'test-index'}


"""

__author__ = 'Robert Eanes'
__all__ = ['ElasticSearch']
__version__ = (0, 0, 3)

def get_version():
    return "%s.%s.%s" % __version__

try:
    # For Python < 2.6 or people using a newer version of simplejson
    import simplejson as json
except ImportError:
    # For Python >= 2.6
    import json
    
from httplib import HTTPConnection
from urlparse import urlsplit
from urllib import urlencode
import logging

class ElasticSearch(object):
    """
    ElasticSearch connection object.
    """
    
    def __init__(self, url):
        self.url = url
        self.scheme, netloc, path, query, fragment = urlsplit(url)
        netloc = netloc.split(':')
        self.host = netloc[0]
        if len(netloc) == 1:
            self.host, self.port = netloc[0], None
        else:
            self.host, self.port = netloc
        
    def _send_request(self, method, path, body="", querystring_args={}):
        if querystring_args:
            path = "?".join([path, urlencode(querystring_args)])

        conn = HTTPConnection(self.host, int(self.port))
        if body:
            body = self._prep_request(body)
        logging.debug("making %s request to path: %s %s %s with body: %s" % (method, self.host, self.port, path, body))
        conn.request(method, path, body)
        response = conn.getresponse()
        http_status = response.status
        logging.debug("response status: %s" % http_status)
        response = self._prep_response(response.read())
        logging.debug("got response %s" % response)
        return response
    
    def _make_path(self, path_components):
        """
        Smush together the path components. Empty components will be ignored.
        """
        path_components = [str(component) for component in path_components if component]
        path = '/'.join(path_components)
        if not path.startswith('/'):
            path = '/'+path
        return path
    
    def _prep_request(self, body):
        """
        Encodes body as json.
        """
        return json.dumps(body)
        
    def _prep_response(self, response):
        """
        Parses json to a native python object.
        """
        return json.loads(response)
        
    def _query_call(self, query_type, query, body=None, indexes=['_all'], doc_types=[], **query_params):
        """
        This can be used for search and count calls.
        These are identical api calls, except for the type of query.
        """
        querystring_args = query_params
        if query:
            querystring_args['q'] = query
        path = self._make_path([','.join(indexes), ','.join(doc_types),query_type])
        response = self._send_request('GET', path, body, querystring_args)
        return response
        
    ## REST API
    
    def index(self, doc, index, doc_type, id=None, force_insert=False):
        """
    	Index a typed JSON document into a specific index and make it searchable.
        """
        if force_insert:
            querystring_args = {'opType':'create'}
        else:
            querystring_args = {}
            
        if id is None:
            request_method = 'POST'
        else:
            request_method = 'PUT'
        path = self._make_path([index, doc_type, id])
        response = self._send_request(request_method, path, doc, querystring_args)
        return response
        
    def delete(self, index, doc_type, id):
        """
        Delete a typed JSON document from a specific index based on its id.
        """
        path = self._make_path([index, doc_type, id])
        response = self._send_request('DELETE', path)
        return response
        
    def get(self, index, doc_type, id):
        """
        Get a typed JSON document from an index based on its id.
        """
        path = self._make_path([index, doc_type, id])
        response = self._send_request('GET', path)
        return response
        
    def search(self, query, body=None, indexes=['_all'], doc_types=[], **query_params):
        """
        Execute a search query against one or more indices and get back search hits.
        query must be a dictionary that will convert to Query DSL
        TODO: better api to reflect that the query can be either 'query' or 'body' argument.
        """
        return self._query_call("_search", query, body, indexes, doc_types, **query_params)
        
    def count(self, query, body=None, indexes=['_all'], doc_types=[], **query_params):
        """
        Execute a query against one or more indices and get hits count.
        """
        return self._query_call("_count", query, body, indexes, doc_types, **query_params)
                
    def put_mapping(self, doc_type, mapping, indexes=['_all']):
        """
        Register specific mapping definition for a specific type against one or more indices.
        """
        path = self._make_path([','.join(indexes), doc_type,"_mapping"])
        response = self._send_request('PUT', path, mapping)
        return response
    
    def terms(self, fields, indexes=['_all'], **query_params):
        """
        Extract terms and their document frequencies from one or more fields.
        The fields argument must be a list or tuple of fields.
        For valid query params see: 
        http://www.elasticsearch.com/docs/elasticsearch/rest_api/terms/
        """
        path = self._make_path([','.join(indexes), "_terms"])
        query_params['fields'] = ','.join(fields)
        response = self._send_request('GET', path, querystring_args=query_params)
        return response
    
    def morelikethis(self, index, doc_type, id, fields, **query_params):
        """
        Execute a "more like this" search query against one or more fields and get back search hits.
        """
        path = self._make_path([index, doc_type, id, '_mlt'])
        query_params['fields'] = ','.join(fields)
        response = self._send_request('GET', path, querystring_args=query_params)
        return response
    
    ## Index Admin API
    
    def status(self, indexes=['_all']):
        """
        Retrieve the status of one or more indices
        """
        path = self._make_path([','.join(indexes), '_status'])
        response = self._send_request('GET', path)
        return response

    def create_index(self, index, settings=None):
        """
        Creates an index with optional settings.
        Settings must be a dictionary which will be converted to JSON.
        Elasticsearch also accepts yaml, but we are only passing JSON.
        """
        response = self._send_request('PUT', index, settings)
        return response
        
    def delete_index(self, index):
        """
        Deletes an index.
        """
        response = self._send_request('DELETE', index)
        return response
        
    def flush(self, indexes=['_all'], refresh=None):
        """
        Flushes one or more indices (clear memory)
        """
        path = self._make_path([','.join(indexes), '_flush'])
        args = {}
        if refresh is not None:
            args['refresh'] = refresh
        response = self._send_request('POST', path, querystring_args=args)
        return response

    def refresh(self, indexes=['_all']):
        """
        Refresh one or more indices
        """
        path = self._make_path([','.join(indexes), '_refresh'])
        response = self._send_request('POST', path)
        return response

    def gateway_snapshot(self, indexes=['_all']):
        """
        Gateway snapshot one or more indices
        """
        path = self._make_path([','.join(indexes), '_gateway', 'snapshot'])
        response = self._send_request('POST', path)
        return response
        

    def optimize(self, indexes=['_all'], **args):
        """
        Optimize one ore more indices
        """
        path = self._make_path([','.join(indexes), '_optimize'])
        response = self._send_request('POST', path, querystring_args=args)
        return response
        
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logging.debug("testing")
    import doctest
    doctest.testmod()