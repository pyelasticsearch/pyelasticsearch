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

>>> time.sleep(2) # need to give it some time to become available
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
{'docs': {'numDocs': 2, 'deletedDocs': 0, 'maxDoc': 2}, 'fields': {'name': {'terms': [{'term': 'baloney', 'docFreq': 1}, {'term': 'bill', 'docFreq': 1}, {'term': 'joe', 'docFreq': 1}, {'term': 'tester', 'docFreq': 1}]}}, '_shards': {'successful': 5, 'failed': 0, 'total': 5}}
>>> conn.terms(['name'], indexes=['test-index'])
{'docs': {'numDocs': 2, 'deletedDocs': 0, 'maxDoc': 2}, 'fields': {'name': {'terms': [{'term': 'baloney', 'docFreq': 1}, {'term': 'bill', 'docFreq': 1}, {'term': 'joe', 'docFreq': 1}, {'term': 'tester', 'docFreq': 1}]}}, '_shards': {'successful': 5, 'failed': 0, 'total': 5}}
>>> conn.terms(['name'], minFreq=2)
{'docs': {'numDocs': 2, 'deletedDocs': 0, 'maxDoc': 2}, 'fields': {'name': {'terms': []}}, '_shards': {'successful': 5, 'failed': 0, 'total': 5}}

More Like This
>>> conn.index({"name":"Joe Test"}, "test-index", "test-type", 3)
{'_type': 'test-type', '_id': '3', 'ok': True, '_index': 'test-index'}
>>> time.sleep(2)
>>> conn.morelikethis("test-index", "test-type", 1, ['name'], minTermFrequency=1, minDocFreq=1)
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

"""

__author__ = 'Robert Eanes'
__all__ = ['ElasticSearch']
__version__ = (0, 0, 2)

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

        conn = HTTPConnection(self.host, self.port)
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
        querystring_args = {'q':query}
        querystring_args.update(**query_params)
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
        path = self._make_path([index, doc_type, id])
        response = self._send_request('PUT', path, doc, querystring_args)
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
        """
        return self._query_call("_search", query, body, indexes, doc_types, **query_params)
        
    def count(self, query, body=None, indexes=['_all'], doc_types=[], **query_params):
        """
        Execute a query against one or more indices and get hits count.
        """
        return self._query_call("_count", query, body, indexes, doc_types, **query_params)
        
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
        path = self._make_path([index, doc_type, id, '_moreLikeThis'])
        query_params['fields'] = ','.join(fields)
        response = self._send_request('GET', path, querystring_args=query_params)
        return response
    
    ## Admin API
    
    # TODO
        
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logging.debug("testing")
    import doctest
    doctest.testmod()