# -*- coding: utf-8 -*-
"""
NOTE: You should use the unit tests, not these doctests, which are harder to get running consistently.
I've left them here as documentation only, they are accurate as usage examples.

Create ElasticSearch connection
>>> conn = ElasticSearch('http://localhost:9200/')

Or a more verbose log level.
>>> import logging
>>> class VerboseElasticSearch(ElasticSearch):
...     def setup_logging(self):
...         log = super(VerboseElasticSearch, self).setup_logging()
...         log.addHandler(logging.StreamHandler())
...         log.setLevel(logging.DEBUG)
...         return log
>>> conn = VerboseElasticSearch('http://localhost:9200/')

Add a few documents

>>> conn.index({"name":"Joe Tester"}, "test-index", "test-type", 1)
{'_type': 'test-type', '_id': '1', 'ok': True, '_index': 'test-index'}
>>> conn.index({"name":"Bill Baloney"}, "test-index", "test-type", 2)
{'_type': 'test-type', '_id': '2', 'ok': True, '_index': 'test-index'}

Get one

>>> conn.refresh("test-index") # doctest: +ELLIPSIS
{'ok': True, '_shards': {...}}
>>> conn.get("test-index", "test-type", 1)
{'_type': 'test-type', '_id': '1', '_source': {'name': 'Joe Tester'}, '_index': 'test-index'}

Get a count
>>> conn.count("name:joe")
{'count': 1, '_shards': {'successful': 5, 'failed': 0, 'total': 5}}

Search

>>> conn.search("name:joe")
{'hits': {'hits': [{'_type': 'test-type', '_id': '1', '_source': {'name': 'Joe Tester'}, '_index': 'test-index'}], 'total': 1}, '_shards': {'successful': 5, 'failed': 0, 'total': 5}}

More Like This

>>> conn.index("test-index", "test-type", {"name":"Joe Test"}, 3)
{'_type': 'test-type', '_id': '3', 'ok': True, '_index': 'test-index'}
>>> conn.refresh(["test-index"]) # doctest: +ELLIPSIS
{'ok': True, '_shards': {...}}
>>> conn.more_like_this("test-index", "test-type", 1, ['name'], min_term_freq=1, min_doc_freq=1)
{'hits': {'hits': [{'_type': 'test-type', '_id': '3', '_source': {'name': 'Joe Test'}, '_index': 'test-index'}], 'total': 1}, '_shards': {'successful': 5, 'failed': 0, 'total': 5}}
>>> conn.delete("test-index", "test-type", 3)
{'_type': 'test-type', '_id': '3', 'ok': True, '_index': 'test-index'}

Delete Bill

>>> conn.delete("test-index", "test-type", 2)
{'_type': 'test-type', '_id': '2', 'ok': True, '_index': 'test-index'}

>>> conn.delete_by_query("test-index, "test-type", {"query_string": {"query": "name:joe OR name:bill"}})
{'ok': True, '_indices': {'test-index': {'_shards': {'successful': 5, 'failed': 0, 'total': 5}}}}

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
>>> conn.index("test-index", "test-type", {"name":"Joe Tester"}) # doctest: +ELLIPSIS
{'_type': 'test-type', '_id': '...', 'ok': True, '_index': 'test-index'}
"""
from __future__ import absolute_import

from datetime import datetime
from functools import wraps
from logging import getLogger
import re
from urllib import urlencode

import requests
from requests import Timeout, ConnectionError
# import either simplejson or the json module in Python >= 2.6
from requests.compat import json

from pyelasticsearch.downtime import DowntimePronePool
from pyelasticsearch.exceptions import (ElasticHttpError, NonJsonResponseError,
                                        ElasticHttpNotFoundError)

__author__ = 'Robert Eanes'
__all__ = ['ElasticSearch', 'ElasticHttpError', 'NonJsonResponseError',
           'Timeout', 'ConnectionError', 'ElasticHttpNotFoundError']
__version__ = '0.2.1'
__version_info__ = tuple(__version__.split('.'))

get_version = lambda: __version_info__


DATETIME_REGEX = re.compile(
    r'^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})T'
    r'(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(\.\d+)?$')


def es_kwargs(*args_to_convert):
    """
    Mark which kwargs will become query string params in the eventual ES call.

    Return a decorator that grabs the kwargs of the given names, plus any
    beginning with "es_", subtracts them from the ordinary kwargs, and passes
    them to the decorated function through the ``query_params`` kwarg. The
    remaining kwargs and the args are passed through unscathed.
    """
    convertible_args = set(args_to_convert)
    def decorator(func):
        @wraps(func)
        def decorate(*args, **kwargs):
            # Make kwargs the map of normal kwargs and query_params the map of
            # kwargs destined for query string params:
            query_params = {}
            for k, v in kwargs.items():  # NOT iteritems; we mutate kwargs
                if k.startswith('es_'):
                    query_params[k[3:]] = kwargs.pop(k)
                elif k in convertible_args:
                    query_params[k] = kwargs.pop(k)

            return func(*args, query_params=query_params, **kwargs)
        return decorate
    return decorator


class ElasticSearch(object):
    """ElasticSearch connection object."""

    def __init__(self, urls, timeout=60, max_retries=0, revival_delay=300):
        """
        :arg timeout: Number of seconds to wait for each request before raising
            Timeout
        :arg max_retries: How many other servers to try, in series, after a
            request times out or a connection fails
        :arg revival_delay: Number of seconds for which to avoid a server after
            it times out or is uncontactable
        """
        if isinstance(urls, basestring):
            urls = [urls]
        urls = [u.rstrip('/') for u in urls]
        self.servers = DowntimePronePool(urls, revival_delay)
        self.revival_delay = revival_delay

        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = getLogger('pyelasticsearch')
        self.session = requests.session()

    @staticmethod
    def _concat(items):
        """
        Return a comma-delimited concatenation of the elements of ``items``,
        with any occurrences of "_all" omitted.

        If ``items`` is a string, promote it to a 1-item list.
        """
        # TODO: Why strip out _all?
        if items is None:
            return ''
        if isinstance(items, basestring):
            items = [items]
        return ','.join(i for i in items if i != '_all')

    @classmethod
    def _to_query(cls, obj):
        """Convert a native-Python object to a query string representation."""
        # Quick and dirty thus far
        if isinstance(obj, basestring):
            return obj
        if isinstance(obj, bool):
            return 'true' if obj else 'false'
        if isinstance(obj, (long, int, float)):
            return str(obj)
        if isinstance(obj, (list, tuple)):
            return ','.join(cls._to_query(o) for o in obj)
        iso = _iso_datetime(obj)
        if iso:
            return iso
        raise TypeError("_to_query() doesn't know how to represent %r in an ES"
                        " query string." % (obj,))

    def _send_request(self,
                      method,
                      path_components,
                      body='',
                      query_params=None,
                      encode_body=True):
        """
        Send an HTTP request to ES, and return the JSON-decoded response.

        Retry the request on different servers if the first one is down and
        ``self.max_retries`` > 0.

        :arg method: An HTTP method, like "GET"
        :arg path_components: An iterable of path components, to be joined by
            "/"
        :arg body: The request body
        :arg query_params: A map of querystring param names to values or None
        :arg encode_body: Whether to encode the body of the request as JSON
        """
        def join_path(path_components):
            """Smush together the path components, ignoring empty ones."""
            path = '/'.join(str(p) for p in path_components if p)
            if not path.startswith('/'):
                path = '/' + path
            return path

        path = join_path(path_components)
        if query_params:
            path = '?'.join(
                [path, urlencode(dict((k, self._to_query(v)) for k, v in
                                      query_params.iteritems()))])

        kwargs = ({'data': self._encode_json(body) if encode_body else body}
                   if body else {})
        req_method = getattr(self.session, method.lower())

        # We do our own retrying rather than using urllib3's; we want to retry
        # a different node in the cluster if possible, not the same one again
        # (which may be down).
        for attempt in xrange(self.max_retries + 1):
            server_url, was_dead = self.servers.get()
            url = server_url + path
            self.logger.debug(
                'making %s request to path: %s %s with body: %s',
                method, url, path, kwargs.get('data', {}))
            try:
                # prefetch=True so the connection can be quickly returned to
                # the pool. This is the default in requests >=0.3.16.
                resp = req_method(
                    url, prefetch=True, timeout=self.timeout, **kwargs)
            except (ConnectionError, Timeout):
                self.servers.mark_dead(server_url)
                self.logger.info('%s marked as dead for %s seconds.',
                                 server_url,
                                 self.revival_delay)
                if attempt >= self.max_retries:
                    raise
            else:
                if was_dead:
                    self.servers.mark_live(server_url)
                break

        self.logger.debug('response status: %s', resp.status_code)
        prepped_response = self._decode_response(resp)
        if resp.status_code >= 400:
            error_class = (ElasticHttpNotFoundError if resp.status_code == 404
                           else ElasticHttpError)
            raise error_class(
                resp.status_code,
                prepped_response.get('error', prepped_response))
        self.logger.debug('got response %s', prepped_response)
        return prepped_response

    def _encode_json(self, body):
        """Return body encoded as JSON."""
        return json.dumps(body, cls=DateSavvyJsonEncoder)

    def _decode_response(self, response):
        """Return a native-Python representation of a JSON blob."""
        json_response = response.json
        if json_response is None:
            raise NonJsonResponseError(response)
        return json_response

    ## REST API

    @es_kwargs('routing', 'parent', 'timestamp', 'ttl', 'percolate',
               'consistency', 'replication', 'refresh', 'timeout')
    def index(self, index, doc_type, doc, id=None, force_insert=False,
              query_params=None):
        """
        Put a typed JSON document into a specific index to make it searchable.

        :arg index: The name of the index to which to add the document
        :arg doc_type: The type of the document
        :arg doc: A mapping, convertible to JSON, representing the document
        :arg id: The ID to give the document. Leave blank to make one up.
        :arg force_insert: If ``True`` and a document of the given ID already
            exists, fail rather than updating it.
        :arg routing: A value hashed to determine which shard this indexing
            request is routed to
        :arg parent: The ID of a parent document, which leads this document to
            be routed to the same shard as the parent, unless ``routing``
            overrides it.
        :arg timestamp: An explicit value for the (typically automatic)
            timestamp associated with a document, for use with ``ttl`` and such
        :arg ttl: The time until this document is automatically removed from
            the index. Can be an integral number of milliseconds or a duration
            like '1d'.
        :arg percolate: An indication of which percolator queries, registered
            against this index, should be checked against the new document: '*'
            or a query string like 'color:green'
        :arg consistency: An indication of how many active shards the contact
            node should demand to see in order to let the index operation
            succeed: 'one', 'quorum', or 'all'
        :arg replication: Set to 'async' to return from ES before finishing
            replication.
        :arg refresh: Pass True to refresh the index after adding the document.
        :arg timeout: A duration to wait for the relevant primary shard to
            become available, in the event that it isn't: for example, "5m"
        :arg query_params: A map of other querystring params to pass along to
            ES. This lets you use future ES features without waiting for an
            update to pyelasticsearch. If we just used **kwargs for this, ES
            could start using a querystring param that we already used as a
            kwarg, and we'd shadow it. Name these params according to the names
            they have in ES's REST API, but prepend "es_": for example,
            ``es_version=2``.

        See http://www.elasticsearch.org/guide/reference/api/index_.html for
        more about the index API.
        """
        # TODO: Support version along with associated "preference" and
        # "version_type" params.
        if force_insert:
            query_params['op_type'] = 'create'

        return self._send_request('POST' if id is None else 'PUT',
                                  [index, doc_type, id],
                                  doc,
                                  query_params)

    @es_kwargs('consistency', 'refresh')
    def bulk_index(self, index, doc_type, docs, id_field='id',
                   query_params=None):
        """Index a list of documents as efficiently as possible."""
        body_bits = []

        if not docs:
            raise ValueError('No documents provided for bulk indexing!')

        for doc in docs:
            action = {'index': {'_index': index, '_type': doc_type}}

            if doc.get(id_field):
                action['index']['_id'] = doc[id_field]

            body_bits.append(self._encode_json(action))
            body_bits.append(self._encode_json(doc))

        # Need the trailing newline.
        body = '\n'.join(body_bits) + '\n'
        query_params['op_type'] = 'create'  # TODO: Why?
        return self._send_request('POST',
                                  [index, '_bulk'],
                                  body,
                                  encode_body=False,
                                  query_params=query_params)

    _DELETE_KWARGS = ['routing', 'parent', 'replication', 'consistency',
                      'refresh']
    @es_kwargs(*_DELETE_KWARGS)
    def delete(self, index, doc_type, id, query_params=None):
        """
        Delete a typed JSON document from a specific index based on its ID.

        :arg index: The name of an index
        :arg doc_type: The name of a document type
        :arg id: The ID of the document to delete
        """
        # TODO: Raise ValueError if id boils down to a 0-length string.
        return self._send_request('DELETE', [index, doc_type, id],
                                  query_params=query_params)

    @es_kwargs(*_DELETE_KWARGS)
    def delete_all(self, index, doc_type, query_params=None):
        """
        Delete all documents of the given doctype from an index.

        :arg index: The name of an index. ES does not support this being empty
            or "_all" or a comma-delimited list of index names (in 0.19.9).
        :arg doc_type: The name of a document type
        """
        return self._send_request('DELETE', [index, doc_type],
                                  query_params=query_params)

    @es_kwargs('q', 'df', 'analyzer', 'default_operator', 'source' 'routing',
               'replication', 'consistency')
    def delete_by_query(self, index, doc_type, query, query_params=None):
        """
        Delete typed JSON documents from a specific index based on query.
        """
        return self._send_request('DELETE', [index, doc_type, '_query'], query,
                                  query_params=query_params)

    @es_kwargs('realtime', 'fields', 'routing', 'preference', 'refresh')
    def get(self, index, doc_type, id, query_params=None):
        """Get a typed JSON document from an index by ID."""
        return self._send_request('GET', [index, doc_type, id],
                                  query_params=query_params)

    def _search_or_count(self, kind, query, indexes=None, doc_types=None,
                         query_params=None):
        if isinstance(query, basestring):
            query_params['q'] = query
            body = ''
        else:
            body = query

        return self._send_request(
            'GET',
            [self._concat(indexes), self._concat(doc_types), kind],
            body,
            query_params=query_params)

    @es_kwargs('routing')
    def search(self, query, **kwargs):
        """
        Execute a search query against one or more indices and get back search
        hits.

        :arg query: A dictionary that will convert to ES's query DSL or a
            string that will serve as a textual query to be passed as the ``q``
            query string parameter
        """
        return self._search_or_count('_search', query, **kwargs)

    @es_kwargs('df', 'analyzer', 'default_operator', 'source', 'routing')
    def count(self, query, **kwargs):
        """
        Execute a query against one or more indices and get hit count.

        :arg query: A dictionary that will convert to ES's query DSL or a
            string that will serve as a textual query to be passed as the ``q``
            query string parameter
        """
        return self._search_or_count('_count', query, **kwargs)

    @es_kwargs()
    def get_mapping(self, indexes=None, doc_types=None, query_params=None):
        """Fetch the mapping definition for a specific index and type."""
        return self._send_request(
            'GET',
            [self._concat(indexes), self._concat(doc_types), '_mapping'],
            query_params=query_params)

    @es_kwargs('ignore_conflicts')
    def put_mapping(self, indexes, doc_type, mapping, query_params=None):
        """
        Register specific mapping definition for a specific type against one or
        more indices.
        """
        # TODO: Perhaps add a put_all_mappings() for consistency and so we
        # don't need to expose the "_all" magic string. We haven't done it yet
        # since this routine is not dangerous: ES makes you explicily pass
        # "_all" to update all mappings.
        return self._send_request(
            'PUT',
            [self._concat(indexes), doc_type, '_mapping'],
            mapping,
            query_params=query_params)

    @es_kwargs('search_type', 'search_indices', 'search_types',
               'search_scroll', 'search_size', 'search_from', 'fields',
               'like_text', 'percent_terms_to_match', 'min_term_freq',
               'max_query_terms', 'stop_words', 'min_doc_freq', 'max_doc_freq',
               'min_word_len', 'max_word_len', 'boost_terms', 'boost',
               'analyzer')
    def more_like_this(self, index, doc_type, id, fields, query_params=None):
        """
        Execute a "more like this" search query against one or more fields and
        get back search hits.
        """
        query_params['fields'] = self._concat(fields)
        return self._send_request('GET',
                                  [index, doc_type, id, '_mlt'],
                                  query_params=query_params)

    ## Index Admin API

    @es_kwargs('recovery', 'snapshot')
    def status(self, indexes=None, query_params=None):
        """
        Retrieve the status of one or more indices
        """
        return self._send_request('GET', [self._concat(indexes), '_status'],
                                  query_params=query_params)

    @es_kwargs()
    def create_index(self, index, settings=None, query_params=None):
        """
        Create an index with optional settings.

        :arg settings: A dictionary which will be converted to JSON
        """
        return self._send_request('PUT', [index], body=settings,
                                  query_params=query_params)

    @es_kwargs()
    def delete_index(self, indexes, query_params=None):
        """Delete an index."""
        if not indexes:
            raise ValueError('No indexes specified. To delete all indexes, use'
                             ' delete_all_indexes().')
        return self._send_request('DELETE', [self._concat(indexes)],
                                  query_params=query_params)

    def delete_all_indexes(self, **kwargs):
        """Delete all indexes."""
        return self.delete_index('_all', **kwargs)

    @es_kwargs()
    def close_index(self, index, query_params=None):
        """Close an index."""
        return self._send_request('POST', [index, '_close'],
                                  query_params=query_params)

    @es_kwargs()
    def open_index(self, index, query_params=None):
        """Open an index."""
        return self._send_request('POST', [index, '_open'],
                                  query_params=query_params)

    @es_kwargs()
    def update_settings(self, indexes, settings, query_params=None):
        """
        :arg indexes: An iterable of names of indexes to update
        """
        if not indexes:
            raise ValueError('No indexes specified. To update all indexes, use'
                             ' update_all_settings().')
        # If we implement the "update cluster settings" API, call that
        # update_cluster_settings().
        return self._send_request('PUT',
                                  [self._concat(indexes), '_settings'],
                                  body=settings,
                                  query_params=query_params)

    @es_kwargs()
    def update_all_settings(self, settings, query_params=None):
        """Update the settings of all indexes."""
        return self._send_request('PUT', ['_settings'], body=settings,
                                  query_params=query_params)

    @es_kwargs('refresh')
    def flush(self, indexes=None, query_params=None):
        """Flush one or more indices (clear memory)."""
        return self._send_request('POST',
                                  [self._concat(indexes), '_flush'],
                                  query_params=query_params)

    @es_kwargs()
    def refresh(self, indexes=None, query_params=None):
        """Refresh one or more indices."""
        return self._send_request('POST', [self._concat(indexes), '_refresh'],
                                  query_params=query_params)

    @es_kwargs()
    def gateway_snapshot(self, indexes=None, query_params=None):
        """Gateway snapshot one or more indices."""
        return self._send_request(
            'POST',
            [self._concat(indexes), '_gateway', 'snapshot'],
            query_params=query_params)

    @es_kwargs('max_num_segments', 'only_expunge_deletes', 'refresh', 'flush',
               'wait_for_merge')
    def optimize(self, indexes=None, query_params=None):
        """Optimize one ore more indices."""
        return self._send_request('POST',
                                  [self._concat(indexes), '_optimize'],
                                  query_params=query_params)

    @es_kwargs('level', 'wait_for_status', 'wait_for_relocating_shards',
               'wait_for_nodes', 'timeout')
    def health(self, indexes=None, query_params=None):
        """
        Report on the health of the cluster or certain indices.

        :arg indexes: The index or iterable of indexes to examine
        :arg kwargs: Passed through to the Cluster Health API verbatim
        """
        return self._send_request(
            'GET',
            ['_cluster', 'health', self._concat(indexes)],
            query_params=query_params)

    @staticmethod
    def from_python(value):
        """
        Convert Python values to a form suitable for ElasticSearch's JSON.
        """
        iso = _iso_datetime(value)
        if iso:
            return iso
        if isinstance(value, str):
            return unicode(value, errors='replace')  # TODO: Be stricter.
        return value

    @staticmethod
    def to_python(value):
        """Convert values from ElasticSearch to native Python values."""
        if isinstance(value, (int, float, long, complex, list, tuple, bool)):
            return value

        if isinstance(value, basestring):
            possible_datetime = DATETIME_REGEX.search(value)

            if possible_datetime:
                date_values = possible_datetime.groupdict()

                for dk, dv in date_values.items():
                    date_values[dk] = int(dv)

                return datetime(
                    date_values['year'], date_values['month'],
                    date_values['day'], date_values['hour'],
                    date_values['minute'], date_values['second'])

        try:
            # This is slightly gross but it's hard to tell otherwise what the
            # string's original type might have been. Be careful who you trust.
            converted_value = eval(value)

            # Try to handle most built-in types.
            if isinstance(
                    converted_value,
                    (list, tuple, set, dict, int, float, long, complex)):
                return converted_value
        except Exception:
            # If it fails (SyntaxError or its ilk) or we don't trust it,
            # continue on.
            pass

        return value


class DateSavvyJsonEncoder(json.JSONEncoder):
    def default(self, value):
        """Convert more Python data types to ES-understandable JSON."""
        return ElasticSearch.from_python(value)


def _iso_datetime(value):
    """
    If value appears to be something datetime-like, return it in ISO format.

    Otherwise, return None.
    """
    if hasattr(value, 'strftime'):
        if hasattr(value, 'hour'):
            return value.isoformat()
        else:
            return '%sT00:00:00' % value.isoformat()


if __name__ == '__main__':
    import doctest
    doctest.testmod()
