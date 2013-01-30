# -*- coding: utf-8 -*-
from __future__ import absolute_import

from datetime import datetime
from functools import wraps
from logging import getLogger
import re
from urllib import urlencode

import requests
import simplejson as json  # for use_decimal
from simplejson import JSONDecodeError

from pyelasticsearch.downtime import DowntimePronePool
from pyelasticsearch.exceptions import (Timeout, ConnectionError,
                                        ElasticHttpError,
                                        InvalidJsonResponseError,
                                        ElasticHttpNotFoundError)

DATETIME_REGEX = re.compile(
    r'^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})T'
    r'(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(\.\d+)?$')


def _add_es_kwarg_docs(params, method):
    """
    Add stub documentation for any args in ``params`` that aren't already in
    the docstring of ``method``.

    The stubs may not tell much about each arg, but they serve the important
    purpose of letting the user know that they're safe to use--we won't be
    paving over them in the future for something pyelasticsearch-specific.
    """
    doc = method.__doc__
    for p in params:
        if doc and ('\n        :arg %s: ' % p) not in doc:
            # Find the last documented arg so we can put our generated docs
            # after it. No need to explicitly compile this; the regex cache
            # should serve.
            insertion_point = re.search(
                r'        :arg (.*?)(?=\n+        (?:$|[^: ]))',
                doc,
                re.MULTILINE | re.DOTALL).end()

            doc = ''.join([doc[:insertion_point],
                           '\n        :arg %s: See the ES docs.' % p,
                           doc[insertion_point:]])
    method.__doc__ = doc


def es_kwargs(*args_to_convert):
    """
    Mark which kwargs will become query string params in the eventual ES call.

    Return a decorator that grabs the kwargs of the given names, plus any
    beginning with "es_", subtracts them from the ordinary kwargs, and passes
    them to the decorated function through the ``query_params`` kwarg. The
    remaining kwargs and the args are passed through unscathed.

    Also, if any of the given kwargs are undocumented in the decorated method's
    docstring, add stub documentation for them.
    """
    convertible_args = set(args_to_convert)

    def decorator(func):
        # Add docs for any missing query params:
        _add_es_kwarg_docs(args_to_convert, func)

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
    """
    An object which manages connections to elasticsearch and acts as a
    go-between for API calls to it

    This object is thread-safe. You can create one instance and share it
    among all threads.
    """
    def __init__(self, urls, timeout=60, max_retries=0, revival_delay=300):
        """
        :arg urls: A URL or iterable of URLs of ES nodes. These are full URLs
            with port numbers, like ``http://elasticsearch.example.com:9200``.
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

        json_converter = self.from_python

        class JsonEncoder(json.JSONEncoder):
            def default(self, value):
                """Convert more Python data types to ES-understandable JSON."""
                return json_converter(value)
        self.json_encoder = JsonEncoder

    def _concat(self, items):
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
                        " query string." % obj)

    def send_request(self,
                     method,
                     path_components,
                     body='',
                     query_params=None,
                     encode_body=True):
        """
        Send an HTTP request to ES, and return the JSON-decoded response.

        This is mostly an internal method, but it also comes in handy if you
        need to use a brand new ES API that isn't yet explicitly supported by
        pyelasticsearch, while still taking advantage of our connection pooling
        and retrying.

        Retry the request on different servers if the first one is down and
        ``self.max_retries`` > 0.

        :arg method: An HTTP method, like "GET"
        :arg path_components: An iterable of path components, to be joined by
            "/"
        :arg body: The request body
        :arg query_params: A map of querystring param names to values or
            ``None``
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
                "Making a request equivalent to this: curl -X%s '%s' -d '%s'" %
                (method, url, kwargs.get('data', {})))

            try:
                resp = req_method(url, timeout=self.timeout, **kwargs)
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
        return json.dumps(body, cls=self.json_encoder, use_decimal=True)

    def _decode_response(self, response):
        """Return a native-Python representation of a response's JSON blob."""
        try:
            json_response = response.json()
        except JSONDecodeError:
            raise InvalidJsonResponseError(response)
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

        See `ES's index API`_ for more detail.

        .. _`ES's index API`:
            http://www.elasticsearch.org/guide/reference/api/index_.html
        """
        # :arg query_params: A map of other querystring params to pass along to
        # ES. This lets you use future ES features without waiting for an
        # update to pyelasticsearch. If we just used **kwargs for this, ES
        # could start using a querystring param that we already used as a
        # kwarg, and we'd shadow it. Name these params according to the names
        # they have in ES's REST API, but prepend "\es_": for example,
        # ``es_version=2``.

        # TODO: Support version along with associated "preference" and
        # "version_type" params.
        if force_insert:
            query_params['op_type'] = 'create'

        return self.send_request('POST' if id is None else 'PUT',
                                  [index, doc_type, id],
                                  doc,
                                  query_params)

    @es_kwargs('consistency', 'refresh')
    def bulk_index(self, index, doc_type, docs, id_field='id',
                   query_params=None):
        """
        Index a list of documents as efficiently as possible.

        :arg index: The name of the index to which to add the document
        :arg doc_type: The type of the document
        :arg docs: An iterable of mappings, convertible to JSON, representing
            documents to index
        :arg id_field: The field of each document that holds its ID

        See `ES's bulk API`_ for more detail.

        .. _`ES's bulk API`:
            http://www.elasticsearch.org/guide/reference/api/bulk.html
        """
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
        return self.send_request('POST',
                                  [index, '_bulk'],
                                  body,
                                  encode_body=False,
                                  query_params=query_params)

    @es_kwargs('routing', 'parent', 'replication', 'consistency', 'refresh')
    def delete(self, index, doc_type, id, query_params=None):
        """
        Delete a typed JSON document from a specific index based on its ID.

        :arg index: The name of the index from which to delete
        :arg doc_type: The type of the document to delete
        :arg id: The ID of the document to delete

        See `ES's delete API`_ for more detail.

        .. _`ES's delete API`:
            http://www.elasticsearch.org/guide/reference/api/delete.html
        """
        # TODO: Raise ValueError if id boils down to a 0-length string.
        return self.send_request('DELETE', [index, doc_type, id],
                                  query_params=query_params)

    @es_kwargs('routing', 'parent', 'replication', 'consistency', 'refresh')
    def delete_all(self, index, doc_type, query_params=None):
        """
        Delete all documents of the given doctype from an index.

        :arg index: The name of the index from which to delete. ES does not
            support this being empty or "_all" or a comma-delimited list of
            index names (in 0.19.9).
        :arg doc_type: The name of a document type

        See `ES's delete API`_ for more detail.

        .. _`ES's delete API`:
            http://www.elasticsearch.org/guide/reference/api/delete.html
        """
        return self.send_request('DELETE', [index, doc_type],
                                  query_params=query_params)

    @es_kwargs('q', 'df', 'analyzer', 'default_operator', 'source' 'routing',
               'replication', 'consistency')
    def delete_by_query(self, index, doc_type, query, query_params=None):
        """
        Delete typed JSON documents from a specific index based on query.

        :arg index: The name of the index from which to delete
        :arg doc_type: The type of document to delete
        :arg query: A dict of query DSL selecting the documents to delete

        See `ES's delete-by-query API`_ for more detail.

        .. _`ES's delete-by-query API`:
            http://www.elasticsearch.org/guide/reference/api/delete-by-query.html
        """
        return self.send_request('DELETE', [index, doc_type, '_query'], query,
                                  query_params=query_params)

    @es_kwargs('realtime', 'fields', 'routing', 'preference', 'refresh')
    def get(self, index, doc_type, id, query_params=None):
        """
        Get a typed JSON document from an index by ID.

        :arg index: The name of the index from which to retrieve
        :arg doc_type: The type of document to get
        :arg id: The ID of the document to retrieve

        See `ES's get API`_ for more detail.

        .. _`ES's get API`:
            http://www.elasticsearch.org/guide/reference/api/get.html
        """
        return self.send_request('GET', [index, doc_type, id],
                                  query_params=query_params)


    @es_kwargs('routing', 'parent', 'timeout', 'replication', 'consistency',
               'percolate', 'refresh', 'retry_on_conflict')
    def update(self, index, doc_type, id, script=None, params=None, lang=None,
               query_params=None, doc=None, upsert=None):
        """
        Update an existing document. Raises `TypeError` if all of *script*, *doc* and *upsert*
        evaluate as ``False``.

        :arg index: The name of the index containing the document
        :arg doc_type: The type of the document
        :arg id: The ID of the document
        :arg script: The script to be used to update the document
        :arg params: A dict of the params to be put in scope of the script
        :arg lang: The language of the script. Omit to use the default,
            specified by ``script.default_lang``.
        :arg doc: A partial document to be merged into the existing document
        :arg upsert: Update/insert doc with params specified here
        """
        if not any((script, doc, upsert)):
            raise TypeError("'script', 'doc' and 'upsert' cannot all evaluate as False, at least one must evaluate as True.")

        body = {}
        if script:
            body['script'] = script
        if lang and script:
            body['lang'] = lang
        if doc:
            body['doc'] = doc
        if upsert:
            body['upsert'] = upsert
        if params:
            body['params'] = params
        return self.send_request('POST', [index, doc_type, id, '_update'], body=body, query_params=query_params)

    def _search_or_count(self, kind, query, index=None, doc_type=None,
                         query_params=None):
        if isinstance(query, basestring):
            query_params['q'] = query
            body = ''
        else:
            body = query

        return self.send_request(
            'GET',
            [self._concat(index), self._concat(doc_type), kind],
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
        :arg index: An index or iterable of indexes to search. Omit to search
            all.
        :arg doc_type: A document type or iterable thereof to search. Omit to
            search all.

        See `ES's search API`_ for more detail.

        .. _`ES's search API`:
            http://www.elasticsearch.org/guide/reference/api/search/
        """
        return self._search_or_count('_search', query, **kwargs)

    @es_kwargs('df', 'analyzer', 'default_operator', 'source', 'routing')
    def count(self, query, **kwargs):
        """
        Execute a query against one or more indices and get hit count.

        :arg query: A dictionary that will convert to ES's query DSL or a
            string that will serve as a textual query to be passed as the ``q``
            query string parameter
        :arg index: An index or iterable of indexes to search. Omit to search
            all.
        :arg doc_type: A document type or iterable thereof to search. Omit to
            search all.

        See `ES's count API`_ for more detail.

        .. _`ES's count API`:
            http://www.elasticsearch.org/guide/reference/api/count.html
        """
        return self._search_or_count('_count', query, **kwargs)

    @es_kwargs()
    def get_mapping(self, index=None, doc_type=None, query_params=None):
        """
        Fetch the mapping definition for a specific index and type.

        :arg index: An index or iterable thereof
        :arg doc_type: A document type or iterable thereof

        Omit both arguments to get mappings for all types and indexes.

        See `ES's get-mapping API`_ for more detail.

        .. _`ES's get-mapping API`:
            http://www.elasticsearch.org/guide/reference/api/admin-indices-get-mapping.html
        """
        # TODO: Think about turning index=None into _all if doc_type is non-
        # None, per the ES doc page.
        return self.send_request(
            'GET',
            [self._concat(index), self._concat(doc_type), '_mapping'],
            query_params=query_params)

    @es_kwargs('ignore_conflicts')
    def put_mapping(self, index, doc_type, mapping, query_params=None):
        """
        Register specific mapping definition for a specific type against one or
        more indices.

        :arg index: An index or iterable thereof
        :arg doc_type: The document type to set the mapping of
        :arg mapping: A dict representing the mapping to install. For example,
            this dict can have top-level keys that are the names of doc types.

        See `ES's put-mapping API`_ for more detail.

        .. _`ES's put-mapping API`:
            http://www.elasticsearch.org/guide/reference/api/admin-indices-put-mapping.html
        """
        # TODO: Perhaps add a put_all_mappings() for consistency and so we
        # don't need to expose the "_all" magic string. We haven't done it yet
        # since this routine is not dangerous: ES makes you explicily pass
        # "_all" to update all mappings.
        return self.send_request(
            'PUT',
            [self._concat(index), doc_type, '_mapping'],
            mapping,
            query_params=query_params)

    @es_kwargs('search_type', 'search_indices', 'search_types',
               'search_scroll', 'search_size', 'search_from',
               'like_text', 'percent_terms_to_match', 'min_term_freq',
               'max_query_terms', 'stop_words', 'min_doc_freq', 'max_doc_freq',
               'min_word_len', 'max_word_len', 'boost_terms', 'boost',
               'analyzer')
    def more_like_this(self, index, doc_type, id, mlt_fields, body='', query_params=None):
        """
        Execute a "more like this" search query against one or more fields and
        get back search hits.

        :arg index: The index to search and where the document for comparison
            lives
        :arg doc_type: The type of document to find others like
        :arg id: The ID of the document to find others like
        :arg mlt_fields: The list of fields to compare on
        :arg body: A dictionary that will convert to ES's query DSL and be
            passed as the request body

        See `ES's more-like-this API`_ for more detail.

        .. _`ES's more-like-this API`:
            http://www.elasticsearch.org/guide/reference/api/more-like-this.html
        """
        query_params['mlt_fields'] = self._concat(mlt_fields)
        return self.send_request('GET',
                                 [index, doc_type, id, '_mlt'],
                                 body=body,
                                 query_params=query_params)

    ## Index Admin API

    @es_kwargs('recovery', 'snapshot')
    def status(self, index=None, query_params=None):
        """
        Retrieve the status of one or more indices

        :arg index: An index or iterable thereof

        See `ES's index-status API`_ for more detail.

        .. _`ES's index-status API`:
            http://www.elasticsearch.org/guide/reference/api/admin-indices-status.html
        """
        return self.send_request('GET', [self._concat(index), '_status'],
                                  query_params=query_params)

    @es_kwargs()
    def create_index(self, index, settings=None, query_params=None):
        """
        Create an index with optional settings.

        :arg index: The name of the index to create
        :arg settings: A dictionary of settings

        See `ES's create-index API`_ for more detail.

        .. _`ES's create-index API`:
            http://www.elasticsearch.org/guide/reference/api/admin-indices-create-index.html
        """
        return self.send_request('PUT', [index], body=settings,
                                  query_params=query_params)

    @es_kwargs()
    def delete_index(self, index, query_params=None):
        """
        Delete an index.

        :arg index: An index or iterable thereof to delete

        See `ES's delete-index API`_ for more detail.

        .. _`ES's delete-index API`:
            http://www.elasticsearch.org/guide/reference/api/admin-indices-delete-index.html
        """
        if not index:
            raise ValueError('No indexes specified. To delete all indexes, use'
                             ' delete_all_indexes().')
        return self.send_request('DELETE', [self._concat(index)],
                                  query_params=query_params)

    def delete_all_indexes(self, **kwargs):
        """Delete all indexes."""
        return self.delete_index('_all', **kwargs)

    @es_kwargs()
    def close_index(self, index, query_params=None):
        """
        Close an index.

        :arg index: The index to close

        See `ES's close-index API`_ for more detail.

        .. _`ES's close-index API`:
            http://www.elasticsearch.org/guide/reference/api/admin-indices-open-close.html
        """
        return self.send_request('POST', [index, '_close'],
                                  query_params=query_params)

    @es_kwargs()
    def open_index(self, index, query_params=None):
        """
        Open an index.

        :arg index: The index to open

        See `ES's open-index API`_ for more detail.

        .. _`ES's open-index API`:
            http://www.elasticsearch.org/guide/reference/api/admin-indices-open-close.html
        """
        return self.send_request('POST', [index, '_open'],
                                  query_params=query_params)

    @es_kwargs()
    def update_settings(self, index, settings, query_params=None):
        """
        Change the settings of one or more indexes.

        :arg index: An index or iterable of indexes
        :arg settings: A dictionary of settings

        See `ES's update-settings API`_ for more detail.

        .. _`ES's update-settings API`:
            http://www.elasticsearch.org/guide/reference/api/admin-indices-update-settings.html
        """
        if not index:
            raise ValueError('No indexes specified. To update all indexes, use'
                             ' update_all_settings().')
        # If we implement the "update cluster settings" API, call that
        # update_cluster_settings().
        return self.send_request('PUT',
                                  [self._concat(index), '_settings'],
                                  body=settings,
                                  query_params=query_params)

    @es_kwargs()
    def update_all_settings(self, settings, query_params=None):
        """
        Update the settings of all indexes.

        :arg settings: A dictionary of settings

        See `ES's update-settings API`_ for more detail.

        .. _`ES's update-settings API`:
            http://www.elasticsearch.org/guide/reference/api/admin-indices-update-settings.html
        """
        return self.send_request('PUT', ['_settings'], body=settings,
                                  query_params=query_params)

    @es_kwargs('refresh')
    def flush(self, index=None, query_params=None):
        """
        Flush one or more indices (clear memory).

        :arg index: An index or iterable of indexes

        See `ES's flush API`_ for more detail.

        .. _`ES's flush API`:
            http://www.elasticsearch.org/guide/reference/api/admin-indices-flush.html
        """
        return self.send_request('POST',
                                  [self._concat(index), '_flush'],
                                  query_params=query_params)

    @es_kwargs()
    def refresh(self, index=None, query_params=None):
        """
        Refresh one or more indices.

        :arg index: An index or iterable of indexes

        See `ES's refresh API`_ for more detail.

        .. _`ES's refresh API`:
            http://www.elasticsearch.org/guide/reference/api/admin-indices-refresh.html
        """
        return self.send_request('POST', [self._concat(index), '_refresh'],
                                  query_params=query_params)

    @es_kwargs()
    def gateway_snapshot(self, index=None, query_params=None):
        """
        Gateway snapshot one or more indices.

        :arg index: An index or iterable of indexes

        See `ES's gateway-snapshot API`_ for more detail.

        .. _`ES's gateway-snapshot API`:
            http://www.elasticsearch.org/guide/reference/api/admin-indices-gateway-snapshot.html
        """
        return self.send_request(
            'POST',
            [self._concat(index), '_gateway', 'snapshot'],
            query_params=query_params)

    @es_kwargs('max_num_segments', 'only_expunge_deletes', 'refresh', 'flush',
               'wait_for_merge')
    def optimize(self, index=None, query_params=None):
        """
        Optimize one or more indices.

        :arg index: An index or iterable of indexes

        See `ES's optimize API`_ for more detail.

        .. _`ES's optimize API`:
            http://www.elasticsearch.org/guide/reference/api/admin-indices-optimize.html
        """
        return self.send_request('POST',
                                  [self._concat(index), '_optimize'],
                                  query_params=query_params)

    @es_kwargs('level', 'wait_for_status', 'wait_for_relocating_shards',
               'wait_for_nodes', 'timeout')
    def health(self, index=None, query_params=None):
        """
        Report on the health of the cluster or certain indices.

        :arg index: The index or iterable of indexes to examine

        See `ES's cluster-health API`_ for more detail.

        .. _`ES's cluster-health API`:
            http://www.elasticsearch.org/guide/reference/api/admin-cluster-health.html
        """
        return self.send_request(
            'GET',
            ['_cluster', 'health', self._concat(index)],
            query_params=query_params)

    def from_python(self, value):
        """
        Convert Python values to a form suitable for ElasticSearch's JSON.
        """
        iso = _iso_datetime(value)
        if iso:
            return iso
        if isinstance(value, str):
            return unicode(value, errors='replace')  # TODO: Be stricter.
        if isinstance(value, set):
            return list(value)

        return value

    def to_python(self, value):
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
