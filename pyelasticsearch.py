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

>>> conn.index({"name":"Joe Test"}, "test-index", "test-type", 3)
{'_type': 'test-type', '_id': '3', 'ok': True, '_index': 'test-index'}
>>> conn.refresh(["test-index"]) # doctest: +ELLIPSIS
{'ok': True, '_shards': {...}}
>>> conn.morelikethis("test-index", "test-type", 1, ['name'], min_term_freq=1, min_doc_freq=1)
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
>>> conn.index({"name":"Joe Tester"}, "test-index", "test-type") # doctest: +ELLIPSIS
{'_type': 'test-type', '_id': '...', 'ok': True, '_index': 'test-index'}

"""
from collections import deque
from datetime import datetime
from contextlib import contextmanager
import logging
import random
import re
from threading import Lock
from time import time
from urllib import urlencode

import requests
from requests import Timeout, ConnectionError
# import either simplejson or the json module in Python >= 2.6
from requests.compat import json

__author__ = 'Robert Eanes'
__all__ = ['ElasticSearch', 'ElasticSearchError', 'ElasticHttpError',
           'Timeout', 'ConnectionError']
__version__ = '0.1'
__version_info__ = tuple(__version__.split('.'))

get_version = lambda: __version_info__


DATETIME_REGEX = re.compile(
    r'^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})T'
    r'(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(\.\d+)?$')


class ElasticSearchError(Exception):
    pass


class ElasticHttpError(ElasticSearchError):
    """Exception raised when ES returns a non-OK (>=400) HTTP status code"""

    @property
    def status_code(self):
        return self.args[0]

    @property
    def error(self):
        return self.args[1]

    def __unicode__(self):
        return 'Non-OK status code returned (%d) containing %r.' % (
            self.status_code, self.error)


class NullHandler(logging.Handler):
    def emit(self, record):
        pass


class ElasticSearch(object):
    """
    ElasticSearch connection object.
    """
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
        urls = [u[:-1] if u.endswith('/') else u for u in urls]
        self.servers = DowntimePronePool(urls, revival_delay)

        self.timeout = timeout
        self.max_retries = max_retries
        self.log = self.setup_logging()
        self.session = requests.session()

    def setup_logging(self):
        """
        Set up the logging.

        Done as a method so others can override as needed without complex
        setup.

        """
        log = logging.getLogger('pyelasticsearch')
        null = NullHandler()
        log.addHandler(null)
        log.setLevel(logging.ERROR)
        return log

    def _make_path(self, *path_components):
        """Smush together the path components, ignoring empty ones."""
        path = '/'.join(str(p) for p in path_components if p)
        if not path.startswith('/'):
            path = '/' + path
        return path

    def _concat(self, items):
        """
        Return a comma-delimited concatenation of the elements of ``items``,
        with any occurrences of "_all" omitted.

        If ``items`` is a string, promote it to a 1-item list.
        """
        if items is None:
            return ''
        if isinstance(items, basestring):
            items = [items]
        return ','.join(i for i in items if i != '_all')

    def _send_request(self,
                      method,
                      path,
                      body='',
                      querystring_args=None,
                      prepare_body=True):
        if querystring_args:
            path = '?'.join([path, urlencode(querystring_args)])

        kwargs = {}
        server_url, was_dead = self.servers.get()
        url = server_url + path

        if body:
            kwargs['data'] = self._prep_request(body) if prepare_body else body

        req_method = getattr(self.session, method.lower())
        self.log.debug('making %s request to path: %s %s with body: %s',
                       method, url, path, kwargs.get('data', {}))

        for attempt in xrange(self.max_retries + 1):
            try:
                # prefetch=True so the connection can be quickly returned to
                # the pool. This is the default in requests >=0.3.16.
                resp = req_method(
                    url, prefetch=True, timeout=self.timeout, **kwargs)
            except (ConnectionError, Timeout):
                self.servers.mark_dead(server_url)
                self.log.info('%s marked as dead for awhile.', server_url)
                if attempt >= self.max_retries:
                    raise
            else:
                break

        if was_dead:
            self.servers.mark_live(server_url)

        self.log.debug('response status: %s', resp.status_code)
        prepped_response = self._prep_response(resp)
        if resp.status_code >= 400:
            raise ElasticHttpError(
                resp.status_code,
                prepped_response.get('error', prepped_response))
        self.log.debug('got response %s', prepped_response)
        return prepped_response

    def _prep_request(self, body):
        """Return body encoded as JSON."""
        try:
            return json.dumps(body, cls=DateSavvyJsonEncoder)
        except (TypeError, json.JSONDecodeError, ValueError), e:
            raise ElasticSearchError('Invalid JSON %r' % (body,), e)

    def _prep_response(self, response):
        """Return a native-Python representation of a JSON blob."""
        try:
            json_response = response.json
        except (TypeError, json.JSONDecodeError), e:
            raise ElasticSearchError('Invalid JSON %r' % (response,), e)
        if json_response is None:
            raise ElasticSearchError('Invalid JSON %r' % (response,))
        return json_response

    def _query_call(self, query_type, query, body=None, indexes=None,
                    doc_types=None, **query_params):
        """
        This can be used for search and count calls.
        These are identical api calls, except for the type of query.
        """
        querystring_args = query_params
        if query:
            querystring_args['q'] = query
        path = self._make_path(self._concat(indexes),
                               self._concat(doc_types),
                               query_type)
        response = self._send_request('GET', path, body, querystring_args)
        return response

    ## REST API

    def index(self, doc, index, doc_type, id=None, force_insert=False):
        """
        Index a typed JSON document into a specific index, and make it
        searchable.
        """
        if force_insert:
            querystring_args = {'op_type': 'create'}
        else:
            querystring_args = {}

        if id is None:
            request_method = 'POST'
        else:
            request_method = 'PUT'
        path = self._make_path(index, doc_type, id)
        return self._send_request(request_method, path, doc, querystring_args)

    def bulk_index(self, index, doc_type, docs, id_field='id'):
        """Index a list of documents as efficiently as possible."""
        body_bits = []

        if not docs:
            raise ElasticSearchError(
                'No documents provided for bulk indexing!')

        for doc in docs:
            action = {'index': {'_index': index, '_type': doc_type}}

            if doc.get(id_field):
                action['index']['_id'] = doc[id_field]

            body_bits.append(self._prep_request(action))
            body_bits.append(self._prep_request(doc))

        path = self._make_path(index, '_bulk')
        # Need the trailing newline.
        body = '\n'.join(body_bits) + '\n'
        return self._send_request(
            'POST', path, body, {'op_type': 'create'}, prepare_body=False)

    def delete(self, index, doc_type, id=None):
        """
        Delete a typed JSON document from a specific index based on its ID.

        If ``id`` is omitted, delete all documents of the given doctype.
        """
        path_parts = [index, doc_type]
        if id:
            path_parts.append(id)

        path = self._make_path(*path_parts)
        return self._send_request('DELETE', path)

    def delete_by_query(self, index, doc_type, query):
        """
        Delete typed JSON documents from a specific index based on query.
        """
        path = self._make_path(index, doc_type, '_query')
        response = self._send_request('DELETE', path, query)
        return response

    def get(self, index, doc_type, id):
        """Get a typed JSON document from an index by ID."""
        path = self._make_path(index, doc_type, id)
        return self._send_request('GET', path)

    def search(
        self, query, body=None, indexes=None, doc_types=None, **query_params):
        """
        Execute a search query against one or more indices and get back search
        hits.

        ``query`` must be a dictionary that will convert to ES's Query DSL.

        TODO: better api to reflect that the query can be either 'query' or
        'body' argument.
        """
        return self._query_call(
            '_search', query, body, indexes, doc_types, **query_params)

    def count(
        self, query, body=None, indexes=None, doc_types=None, **query_params):
        """Execute a query against one or more indices and get hit count."""
        return self._query_call(
            '_count', query, body, indexes, doc_types, **query_params)

    def get_mapping(self, indexes=None, doc_types=None):
        """Fetch the mapping definition for a specific index and type."""
        path = self._make_path(self._concat(indexes),
                               self._concat(doc_types),
                               '_mapping')
        return self._send_request('GET', path)

    def put_mapping(self, doc_type, mapping, indexes=None, **query_params):
        """
        Register specific mapping definition for a specific type against one or
        more indices.
        """
        path = self._make_path(self._concat(indexes), doc_type, '_mapping')
        return self._send_request('PUT', path, mapping, **query_params)

    def more_like_this(self, index, doc_type, id, fields, **query_params):
        """
        Execute a "more like this" search query against one or more fields and
        get back search hits.
        """
        path = self._make_path(index, doc_type, id, '_mlt')
        query_params['fields'] = self._concat(fields)
        return self._send_request('GET', path, querystring_args=query_params)

    ## Index Admin API

    def status(self, indexes=None):
        """
        Retrieve the status of one or more indices
        """
        path = self._make_path(self._concat(indexes), '_status')
        return self._send_request('GET', path)

    def _send_index_request(self,
                            method,
                            description,
                            index,
                            more_path=None,
                            quiet=True,
                            **kwargs):
        """
        Send a request to an index's path, and optionally trap errors.

        :arg method: The HTTP method to use
        :arg description: A human-readable label for the operation, like
            "Close" or "Delete", to be substituted into error message if quiet
            is truthy
        :arg index: The name of the index to operate on
        :arg more_path: Additional URL segments to append to the path
        :arg quiet: Whether to trap any ElasticSearchErrors that result
        :arg **kwargs: Kwargs to pass along to ``_send_request()``
        """
        more_path = more_path or []
        try:
            response = self._send_request(
                method,
                self._make_path(*([index] + more_path)),
                **kwargs)
        except ElasticSearchError, e:
            if not quiet:
                raise
            response = {'message': "%s index '%s' errored: %s" %
                        (description, index, e)}
        return response

    def create_index(self, index, settings=None, quiet=True):
        """
        Creates an index with optional settings.
        Settings must be a dictionary which will be converted to JSON.
        Elasticsearch also accepts yaml, but we are only passing JSON.
        """
        return self._send_index_request(
            'PUT', 'Create', index, body=settings, quiet=quiet)

    def delete_index(self, index, quiet=True):
        """
        Deletes an index.
        """
        return self._send_index_request(
            'DELETE', 'Delete', index, quiet=quiet)

    def close_index(self, index, quiet=True):
        """
        Close an index.
        """
        return self._send_index_request(
            'POST', 'Close', index, more_path=['_close'], quiet=quiet)

    def open_index(self, index, quiet=True):
        """
        Open an index.
        """
        return self._send_index_request(
            'POST', 'Open', index, more_path=['_open'], quiet=quiet)

    def update_settings(self, indexes, settings, quiet=True):
        """
        :arg indexes: The indexes to update, or ['_all'] to do all of them
        """
        # TODO: Have a way of saying "all indexes" that doesn't involve a magic
        # string.
        # If we implement the "update cluster settings" API, call that
        # update_cluster_settings().
        return self._send_index_request(
            'PUT',
            'Settings update on',
            self._concat(indexes),
            more_path=['_settings'],
            quiet=quiet,
            body=settings)

    def flush(self, indexes=None, refresh=None):
        """
        Flushes one or more indices (clear memory)
        """
        path = self._make_path(self._concat(indexes), '_flush')
        args = {}
        if refresh is not None:
            args['refresh'] = refresh
        return self._send_request('POST', path, querystring_args=args)

    def refresh(self, indexes=None):
        """
        Refresh one or more indices
        """
        path = self._make_path(self._concat(indexes), '_refresh')
        return self._send_request('POST', path)

    def gateway_snapshot(self, indexes=None):
        """
        Gateway snapshot one or more indices
        """
        path = self._make_path(self._concat(indexes), '_gateway', 'snapshot')
        return self._send_request('POST', path)

    def optimize(self, indexes=None, **args):
        """
        Optimize one ore more indices
        """
        path = self._make_path(self._concat(indexes), '_optimize')
        return self._send_request('POST', path, querystring_args=args)

    def health(self, indexes=None, **kwargs):
        """
        Report on the health of the cluster or certain indices.

        :arg indexes: The index or iterable of indexes to examine
        :arg kwargs: Passed through to the Cluster Health API verbatim
        """
        path = self._make_path('_cluster', 'health', self._concat(indexes))
        return self._send_request('GET', path, querystring_args=kwargs)

    @staticmethod
    def from_python(value):
        """
        Convert Python values to a form suitable for ElasticSearch's JSON.
        """
        if hasattr(value, 'strftime'):
            if hasattr(value, 'hour'):
                value = value.isoformat()
            else:
                value = '%sT00:00:00' % value.isoformat()
        elif isinstance(value, str):
            value = unicode(value, errors='replace')  # TODO: Be stricter.

        return value

    @staticmethod
    def to_python(value):
        """
        Converts values from ElasticSearch to native Python values.
        """
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
            if isinstance(converted_value, (list, tuple, set, dict, int, float, long, complex)):
                return converted_value
        except:
            # If it fails (SyntaxError or its ilk) or we don't trust it,
            # continue on.
            pass

        return value


class DateSavvyJsonEncoder(json.JSONEncoder):
    def default(self, value):
        """Convert more Python data types to ES-understandable JSON."""
        return ElasticSearch.from_python(value)


class DowntimePronePool(object):
    """
    A thread-safe bucket of things that may have downtime.

    Tries to return a "live" element from the bucket on request, retiring
    "dead" elements for a time to give them a chance to recover before offering
    them again.
    """
    def __init__(self, elements, revival_delay):
        self.live = elements
        self.dead = deque()  # [(time to reinstate, url), ...], oldest first
        self.revival_delay = revival_delay
        self.lock = Lock()  # a lock around live and dead

    def get(self):
        """
        Return a random element and a bool indicating whether it was from the
        dead list.

        We prefer to return live servers. However, if all elements are marked
        dead, return one of those in case it's come back to life earlier than
        expected. This fallback is O(n) rather than O(1), but it's all dwarfed
        by IO anyway.
        """
        with self._locking():
            # Revive any elements whose times have come:
            now = time()
            while self.dead and self.dead[0][0] >= now:
                self.live.append(self.dead.popleft()[1])

            try:
                return random.choice(self.live), False
            except IndexError:  # live is empty.
                return random.choice(self.dead)[1], True  # O(n) but rare

    def mark_dead(self, element):
        """
        Guarantee that this element won't be returned again until a period of
        time has passed, unless all elements are dead.

        If the given element is already on the dead list, do nothing. We
        wouldn't want to push its revival time farther away.
        """
        with self._locking():
            try:
                self.live.remove(element)
            except ValueError:
                # Another thread has marked this element dead since this one
                # got ahold of it, or we handed them a dead element to begin
                # with.
                pass
            else:
                self.dead.append((time() + self.revival_delay, element))

    def mark_live(self, element):
        """Move an element from the dead list to the live one if it is dead."""
        with self._locking():
            for i, (revival_time, cur_element) in enumerate(self.dead):
                if cur_element == element:
                    self.live.append(element)
                    del self.dead[i]
                    break
            # If it isn't found, it's already been revived, and that's okay.

    @contextmanager
    def _locking(self):
        self.lock.acquire()
        yield
        self.lock.release()


if __name__ == '__main__':
    import doctest
    doctest.testmod()
