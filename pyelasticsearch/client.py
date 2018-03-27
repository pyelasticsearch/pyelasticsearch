# -*- coding: utf-8 -*-
from __future__ import absolute_import

from operator import itemgetter
from functools import wraps
import re
from six import (iterkeys, binary_type, text_type, string_types, integer_types,
                 iteritems, PY3)
from six.moves import xrange
from six.moves.urllib.parse import urlparse, urlencode, quote_plus

import certifi
from elasticsearch.connection_pool import RandomSelector
from elasticsearch.exceptions import (ConnectionError, ConnectionTimeout,
                                      TransportError, SerializationError)
from elasticsearch.transport import Transport
import simplejson as json  # for use_decimal

from pyelasticsearch.exceptions import (ElasticHttpError,
                                        ElasticHttpNotFoundError,
                                        IndexAlreadyExistsError,
                                        InvalidJsonResponseError,
                                        BulkError)


def _add_es_kwarg_docs(params, method):
    """
    Add stub documentation for any args in ``params`` that aren't already in
    the docstring of ``method``.

    The stubs may not tell much about each arg, but they serve the important
    purpose of letting the user know that they're safe to use--we won't be
    paving over them in the future for something pyelasticsearch-specific.
    """
    def docs_for_kwarg(p):
        return '\n        :arg %s: See the ES docs.' % p

    doc = method.__doc__
    if doc is not None:  # It's none under python -OO.
        # Handle the case where there are no :arg declarations to key off:
        if '\n        :arg' not in doc and params:
            first_param, params = params[0], params[1:]
            doc = doc.replace('\n        (Insert es_kwargs here.)',
                              docs_for_kwarg(first_param))

        for p in params:
            if ('\n        :arg %s: ' % p) not in doc:
                # Find the last documented arg so we can put our generated docs
                # after it. No need to explicitly compile this; the regex cache
                # should serve.
                insertion_point = re.search(
                    r'        :arg (.*?)(?=\n+        (?:$|[^: ]))',
                    doc,
                    re.MULTILINE | re.DOTALL).end()

                doc = ''.join([doc[:insertion_point],
                               docs_for_kwarg(p),
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
            # kwargs destined for query string params.

            # Let one @es_kwargs-wrapped function call another:
            query_params = kwargs.pop('query_params', {})

            for k in list(iterkeys(kwargs)):  # Make a copy; we mutate kwargs.
                if k.startswith('es_'):
                    query_params[k[3:]] = kwargs.pop(k)
                elif k in convertible_args:
                    query_params[k] = kwargs.pop(k)
            return func(*args, query_params=query_params, **kwargs)
        return decorate
    return decorator


class JsonEncoder(json.JSONEncoder):
    def default(self, value):
        """Convert more Python data types to ES-understandable JSON."""
        iso = _iso_datetime(value)
        if iso:
            return iso
        if not PY3 and isinstance(value, str):
            return unicode(value, errors='replace')  # TODO: Be stricter.
        if isinstance(value, set):
            return list(value)
        return super(JsonEncoder, self).default(value)


class ElasticSearch(object):
    """
    An object which manages connections to elasticsearch and acts as a
    go-between for API calls to it

    This object is thread-safe. You can create one instance and share it
    among all threads.
    """
    #: You can set this attribute on an instance to customize JSON encoding.
    #: The stock JsonEncoder class maps Python datetimes to ES-style datetimes
    #: and Python sets to ES lists. You can subclass it to add more.
    json_encoder = JsonEncoder

    def __init__(self,
                 urls='http://localhost',
                 timeout=60,
                 max_retries=0,
                 port=9200,
                 username=None,
                 password=None,
                 ca_certs=certifi.where(),
                 client_cert=None):
        """
        :arg urls: A URL or iterable of URLs of ES nodes. These can be full
            URLs with port numbers, like
            ``http://elasticsearch.example.com:9200``, or you can pass the
            port separately using the ``port`` kwarg. To do HTTP basic
            authentication, you can use RFC-2617-style URLs like
            ``http://someuser:somepassword@example.com:9200`` or the separate
            ``username`` and ``password`` kwargs below.
        :arg timeout: Number of seconds to wait for each request before raising
            Timeout
        :arg max_retries: How many other servers to try, in series, after a
            request times out or a connection fails
        :arg username: Authentication username to send via HTTP basic auth
        :arg password: Password to use in HTTP basic auth. If a username and
            password are embedded in a URL, those are favored.
        :arg port: The default port to connect on, for URLs that don't include
            an explicit port
        :arg ca_certs: A path to a bundle of CA certificates to trust. The
            default is to use Mozilla's bundle, the same one used by Firefox.
        :arg client_cert: A certificate to authenticate the client to the
            server
        """
        if isinstance(urls, string_types):
            urls = [urls]
        urls = [u.rstrip('/') for u in urls]

        # Automatic node sniffing is off for now.
        parsed_urls = (urlparse(url) for url in urls)
        auth_default = None if username is None else (username, password)
        self._transport = Transport(
            [{'host': url.hostname,
              'port': url.port or port,
              'http_auth': (url.username, url.password) if
                           url.username or url.password else auth_default,
              'use_ssl': url.scheme == 'https',
              'verify_certs': True,
              'ca_certs': ca_certs,
              'cert_file': client_cert}
             for url in parsed_urls],
            max_retries=max_retries,
            retry_on_timeout=True,
            timeout=timeout,
            selector_class=RandomSelector)

    def _concat(self, items):
        """
        Return a comma-delimited concatenation of the elements of ``items``.

        If ``items`` is a string, promote it to a 1-item list.
        """
        if items is None:
            return ''
        if isinstance(items, string_types):
            items = [items]
        return ','.join(items)

    def _to_query(self, obj):
        """
        Convert a native-Python object to a unicode or bytestring
        representation suitable for a query string.
        """
        # Quick and dirty thus far
        if isinstance(obj, string_types):
            return obj
        if isinstance(obj, bool):
            return 'true' if obj else 'false'
        if isinstance(obj, integer_types):
            return str(obj)
        if isinstance(obj, float):
            return repr(obj)  # str loses precision.
        if isinstance(obj, (list, tuple)):
            return ','.join(self._to_query(o) for o in obj)
        iso = _iso_datetime(obj)
        if iso:
            return iso
        raise TypeError("_to_query() doesn't know how to represent %r in an ES"
                        ' query string.' % obj)

    def _utf8(self, thing):
        """Convert any arbitrary ``thing`` to a utf-8 bytestring."""
        if isinstance(thing, binary_type):
            return thing
        if not isinstance(thing, text_type):
            thing = text_type(thing)
        return thing.encode('utf-8')

    def _join_path(self, path_components):
        """
        Smush together the path components, omitting '' and None ones.

        Unicodes get encoded to strings via utf-8. Incoming strings are assumed
        to be utf-8-encoded already.
        """
        path = '/'.join(quote_plus(self._utf8(p), '') for p in path_components if
                        p is not None and p != '')

        if not path.startswith('/'):
            path = '/' + path
        return path

    def send_request(self,
                     method,
                     path_components,
                     body='',
                     query_params=None):
        """
        Send an HTTP request to ES, and return the JSON-decoded response.

        This is mostly an internal method, but it also comes in handy if you
        need to use a brand new ES API that isn't yet explicitly supported by
        pyelasticsearch, while still taking advantage of our connection pooling
        and retrying.

        Retry the request on different servers if the first one is down and
        the ``max_retries`` constructor arg was > 0.

        On failure, raise an
        :class:`~pyelasticsearch.exceptions.ElasticHttpError`, a
        :class:`~pyelasticsearch.exceptions.ConnectionError`, or a
        :class:`~pyelasticsearch.exceptions.Timeout`.

        :arg method: An HTTP method, like "GET"
        :arg path_components: An iterable of path components, to be joined by
            "/"
        :arg body: A map of key/value pairs to be sent as the JSON request
            body. Alternatively, a string to be sent verbatim, without further
            JSON encoding.
        :arg query_params: A map of querystring param names to values or
            ``None``
        """
        if query_params is None:
            query_params = {}
        path = self._join_path(path_components)

        # We wrap to use pyelasticsearch's exception hierarchy for backward
        # compatibility:
        try:
            # This implicitly converts dicts to JSON. Strings are left alone:
            _, prepped_response = self._transport.perform_request(
                method,
                path,
                params=dict((k, self._utf8(self._to_query(v)))
                            for k, v in iteritems(query_params)),
                body=body)
        except SerializationError as exc:
            raise InvalidJsonResponseError(exc.args[0])
        except (ConnectionError, ConnectionTimeout) as exc:
            # Pull the urllib3-native exception out, and raise it:
            raise exc.info
        except TransportError as exc:
            status = exc.args[0]
            error_message = exc.args[1]
            self._raise_exception(status, error_message)

        return prepped_response

    def _raise_exception(self, status, error_message):
        """Raise an exception based on an error-indicating response from ES."""
        error_class = ElasticHttpError
        if status == 404:
            error_class = ElasticHttpNotFoundError
        elif (hasattr(error_message, 'startswith') and
              (error_message.startswith('IndexAlreadyExistsException') or
               error_message.startswith('index_already_exists_exception') or
               'nested: IndexAlreadyExistsException' in error_message)):
            error_class = IndexAlreadyExistsError

        raise error_class(status, error_message)

    def _encode_json(self, value):
        """
        Convert a Python value to a form suitable for ElasticSearch's JSON DSL.
        """
        return json.dumps(value, cls=self.json_encoder, use_decimal=True)

    ## REST API

    @es_kwargs('routing', 'parent', 'timestamp', 'ttl', 'percolate',
               'consistency', 'replication', 'refresh', 'timeout', 'fields')
    def index(self, index, doc_type, doc, id=None, overwrite_existing=True,
              query_params=None):
        """
        Put a typed JSON document into a specific index to make it searchable.

        :arg index: The name of the index to which to add the document
        :arg doc_type: The type of the document
        :arg doc: A Python mapping object, convertible to JSON, representing
            the document
        :arg id: The ID to give the document. Leave blank to make one up.
        :arg overwrite_existing: Whether we should overwrite existing documents
            of the same ID and doc type
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
            http://www.elastic.co/guide/en/elasticsearch/reference/current/docs-index_.html
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
        if not overwrite_existing:
            query_params['op_type'] = 'create'

        return self.send_request('POST' if id is None else 'PUT',
                                 [index, doc_type, id],
                                 doc,
                                 query_params)

    @es_kwargs('consistency', 'refresh', 'replication', 'routing', 'timeout')
    def bulk(self, actions, index=None, doc_type=None, query_params=None):
        """
        Perform multiple index, delete, create, or update actions per request.

        Used with helper routines :meth:`index_op()`, :meth:`delete_op()`, and
        :meth:`update_op()`, this provides an efficient, readable way to do
        large-scale changes. This contrived example illustrates the structure::

            es.bulk([es.index_op({'title': 'All About Cats', 'pages': 20}),
                     es.index_op({'title': 'And Rats', 'pages': 47}),
                     es.index_op({'title': 'And Bats', 'pages': 23})],
                    doc_type='book',
                    index='library')

        More often, you'll want to index (or delete or update) a larger number
        of documents. In those cases, yield your documents from a generator,
        and use :func:`~pyelasticsearch.bulk_chunks()` to divide them into
        multiple requests::

            from pyelasticsearch import bulk_chunks

            def documents():
                for book in books:
                    yield es.index_op({'title': book.title, 'pages': book.pages})
                    # index_op() also takes kwargs like index= and id= in case
                    # you want more control.
                    #
                    # You could also yield some delete_ops or update_ops here.

            # bulk_chunks() breaks your documents into smaller requests for speed:
            for chunk in bulk_chunks(documents(),
                                     docs_per_chunk=500,
                                     bytes_per_chunk=10000):
                # We specify a default index and doc type here so we don't
                # have to repeat them in every operation:
                es.bulk(chunk, doc_type='book', index='library')

        :arg actions: An iterable of bulk actions, generally the output of
            :func:`~pyelasticsearch.bulk_chunks()` but sometimes a list
            of calls to :meth:`index_op()`, :meth:`delete_op()`, and
            :meth:`update_op()` directly. Specifically, an iterable of
            JSON-encoded bytestrings that can be joined with newlines and
            sent to ES.
        :arg index: Default index to operate on
        :arg doc_type: Default type of document to operate on. Cannot be
            specified without ``index``.

        Return the decoded JSON response on success.

        Raise :class:`~pyelasticsearch.exceptions.BulkError` if any of the
        individual actions fail. The exception provides enough about the
        failed actions to identify them for retrying.

        Sometimes there is an error with the request in general, not with
        any individual actions. If there is a connection error, timeout,
        or other transport error, a more general exception will be raised, as
        with other methods; see :ref:`error-handling`.

        See `ES's bulk API`_ for more detail.

        .. _`ES's bulk API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/docs-bulk.html
        """
        # To summarize the flow: index_op() encodes a bytestring.
        #                        bulk_chunks() groups.
        #                        bulk() joins with \n.

        if doc_type is not None and index is None:
            raise ValueError(
                'Please also pass `index` if you pass `doc_type`.')

        def is_error(item):
            for op, subdict in iteritems(item):
                break
            return not 200 <= subdict.get('status', 999) < 300

        response = self.send_request('POST',
                                     [index, doc_type, '_bulk'],
                                     body='\n'.join(actions) + '\n',
                                     query_params=query_params)

        # Sometimes the request worked, but individual actions fail:
        if response.get('errors', True):  # Try a shortcut to avoid looking
                                          # at every item on success.
            errors, successes = [], []
            for item in response['items']:
                if is_error(item):
                    errors.append(item)
                else:
                    successes.append(item)
            if errors:
                raise BulkError(errors, successes)
        return response

    def index_op(self, doc, doc_type=None, overwrite_existing=True, **meta):
        """
        Return a document-indexing operation that can be passed to
        :meth:`bulk()`. (See there for examples.)

        Specifically, return a 2-line, JSON-encoded bytestring.

        :arg doc: A mapping of property names to values.
        :arg doc_type: The type of the document to index, if different from
            the one you pass to :meth:`bulk()`
        :arg overwrite_existing: Whether we should overwrite existing
            documents of the same ID and doc type. (If False, this does a
            `create` operation.)
        :arg meta: Other args controlling how the document is indexed,
            like ``id`` (most common), ``index`` (next most common),
            ``version``, and ``routing``. See `ES's bulk API`_ for details on
            these.

        .. _`ES's bulk API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/docs-bulk.html

        """
        operation = 'index' if overwrite_existing else 'create'
        return self._bulk_op(operation, doc=doc, meta=meta, doc_type=doc_type)

    def delete_op(self, doc_type=None, **meta):
        """
        Return a document-deleting operation that can be passed to
        :meth:`bulk()`. ::

            def actions():
                ...
                yield es.delete_op(id=7)
                yield es.delete_op(id=9,
                                   index='some-non-default-index',
                                   doc_type='some-non-default-type')
                ...

            es.bulk(actions(), ...)

        Specifically, return a JSON-encoded bytestring.

        :arg doc_type: The type of the document to delete, if different
            from the one passed to :meth:`bulk()`
        :arg meta: A description of what document to delete and how to do it.
            Example: ``{"index": "library", "id": 2, "version": 4}``.  See
            `ES's bulk API`_ for a list of all the options.

        .. _`ES's bulk API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/docs-bulk.html

        """
        return self._bulk_op('delete', meta=meta, doc_type=doc_type)

    def update_op(self, doc=None, doc_type=None, upsert=None,
                  doc_as_upsert=None, script=None, params=None, lang=None,
                  **meta):
        """
        Return a document-updating operation that can be passed to
        :meth:`bulk()`. ::

            def actions():
                ...
                yield es.update_op(doc={'pages': 4},
                                   id=7,
                                   version=21)
                ...

            es.bulk(actions(), ...)

        Specifically, return a JSON-encoded bytestring.

        :arg doc: A partial document to be merged into the existing document
        :arg doc_type: The type of the document to update, if different
            from the one passed to :meth:`bulk()`
        :arg upsert: The content for the new document created if the
            document does not exist
        :arg script: The script to be used to update the document
        :arg params: A dict of the params to be put in scope of the script
        :arg lang: The language of the script. Omit to use the default,
            specified by ``script.default_lang``.
        :arg meta: Other args controlling what document to update and how
            to do it, like ``id``, ``index``, and ``retry_on_conflict``,
            destined for the action line itself rather than the payload.  See
            `ES's bulk API`_ for details on these.

        .. _`ES's bulk API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/docs-bulk.html

        """
        payload = dict((k, v) for k, v in [('doc', doc), ('upsert', upsert),
                                  ('doc_as_upsert', doc_as_upsert),
                                  ('script', script), ('params', params),
                                  ('lang', lang)] if v is not None)
        return self._bulk_op('update',
                             doc=payload,
                             meta=meta,
                             doc_type=doc_type)

    def _bulk_op(self, operation, doc=None, meta=None, doc_type=None):
        """
        Return an arbitrary bulk indexing operation as a bytestring.

        :arg operation: One of 'index', 'delete', 'update', or 'create'
        :arg doc: A mapping of fields
        :arg meta: A mapping of underscore-prefixed fields with special
            meaning to ES, like ``_id`` and ``_type``
        :arg doc_type: The value that is to become the ``_type`` field of
            the action line. We go to special trouble to keep the name
            "doc_type" for consistency with other routines.
        """
        def underscore_keys(d):
            """Return a dict with every key prefixed by an underscore."""
            return dict(('_%s' % k, v) for k, v in iteritems(d))

        if meta is None:
            meta = {}
        if doc_type is not None:
            meta['type'] = doc_type

        ret = self._encode_json({operation: underscore_keys(meta)})
        if doc is not None:
            ret += '\n' + self._encode_json(doc)
        return ret

    @es_kwargs('consistency', 'refresh', 'replication', 'routing', 'timeout')
    def bulk_index(self, index, doc_type, docs, id_field='id',
                   parent_field='_parent', index_field='_index',
                   type_field='_type', query_params=None):
        """
        Index a list of documents as efficiently as possible.

        .. note::

            This is deprecated in favor of :meth:`bulk()`, which supports all
            types of bulk actions, not just indexing, is compatible with
            :func:`~pyelasticsearch.bulk_chunks()` for batching, and has a
            simpler, more flexible design.

        :arg index: The name of the index to which to add the document. Pass
            None if you will specify indices individual in each doc.
        :arg doc_type: The type of the document
        :arg docs: An iterable of Python mapping objects, convertible to JSON,
            representing documents to index
        :arg id_field: The field of each document that holds its ID. Removed
            from document before indexing.
        :arg parent_field: The field of each document that holds its parent ID,
            if any. Removed from document before indexing.
        :arg index_field: The field of each document that holds the index to
            put it into, if different from the ``index`` arg. Removed from
            document before indexing.
        :arg type_field: The field of each document that holds the doc type it
            should become, if different from the ``doc_type`` arg. Removed from
            the document before indexing.

        Raise :class:`~pyelasticsearch.exceptions.BulkError` if the request as
        a whole succeeded but some of the individual actions failed. You can
        pull enough about the failed actions out of the exception to identify
        them for retrying.

        See `ES's bulk API`_ for more detail.

        .. _`ES's bulk API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/docs-bulk.html
        """
        if not docs:
            raise ValueError('No documents provided for bulk indexing!')

        meta_fields = [(index_field, 'index'),
                       (id_field, 'id'),
                       (parent_field, 'parent')]

        def encoded_docs():
            for doc in docs:
                action = {}
                for doc_key, bulk_key in meta_fields:
                    if doc.get(doc_key) is not None:
                        action[bulk_key] = doc.pop(doc_key)
                yield self.index_op(doc,
                                    doc_type=doc.pop(type_field, None),
                                    **action)

        return self.bulk(encoded_docs(),
                         index=index,
                         doc_type=doc_type,
                         query_params=query_params)

    @es_kwargs('routing', 'parent', 'replication', 'consistency', 'refresh')
    def delete(self, index, doc_type, id, query_params=None):
        """
        Delete a typed JSON document from a specific index based on its ID.

        :arg index: The name of the index from which to delete
        :arg doc_type: The type of the document to delete
        :arg id: The (string or int) ID of the document to delete

        See `ES's delete API`_ for more detail.

        .. _`ES's delete API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/docs-delete.html
        """
        # id should never be None, and it's not particular dangerous
        # (equivalent to deleting a doc with ID "None", but it's almost
        # certainly not what the caller meant:
        if id is None or id == '':
            raise ValueError('No ID specified. To delete all documents in '
                             'an index, use delete_all().')
        return self.send_request('DELETE', [index, doc_type, id],
                                 query_params=query_params)

    @es_kwargs('routing', 'parent', 'replication', 'consistency', 'refresh')
    def delete_all(self, index, doc_type, query_params=None):
        """
        Delete all documents of the given doc type from an index.

        :arg index: The name of the index from which to delete. ES does not
            support this being empty or "_all" or a comma-delimited list of
            index names (in 0.19.9).
        :arg doc_type: The name of a document type

        See `ES's delete API`_ for more detail.

        .. _`ES's delete API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/docs-delete.html
        """
        return self.send_request('DELETE', [index, doc_type],
                                 query_params=query_params)

    @es_kwargs('q', 'df', 'analyzer', 'default_operator', 'source' 'routing',
               'replication', 'consistency')
    def delete_by_query(self, index, doc_type, query, query_params=None):
        """
        Delete typed JSON documents from a specific index based on query.

        :arg index: An index or iterable thereof from which to delete
        :arg doc_type: The type of document or iterable thereof to delete
        :arg query: A dictionary that will convert to ES's query DSL or a
            string that will serve as a textual query to be passed as the ``q``
            query string parameter. (Passing the ``q`` kwarg yourself is
            deprecated.)

        See `ES's delete-by-query API`_ for more detail.

        .. _`ES's delete-by-query API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/docs-delete-by-query.html
        """
        if isinstance(query, string_types) and 'q' not in query_params:
            query_params['q'] = query
            body = ''
        else:
            body = {'query': query}
        return self.send_request(
            'DELETE',
            [self._concat(index), self._concat(doc_type), '_query'],
            body,
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
            http://www.elastic.co/guide/en/elasticsearch/reference/current/docs-get.html
        """
        return self.send_request('GET', [index, doc_type, id],
                                 query_params=query_params)

    @es_kwargs()
    def multi_get(self, ids, index=None, doc_type=None, fields=None,
                  query_params=None):
        """
        Get multiple typed JSON documents from ES.

        :arg ids: An iterable, each element of which can be either an a dict or
            an id (int or string). IDs are taken to be document IDs. Dicts are
            passed through the Multi Get API essentially verbatim, except that
            any missing ``_type``, ``_index``, or ``fields`` keys are filled in
            from the defaults given in the ``doc_type``, ``index``, and
            ``fields`` args.
        :arg index: Default index name from which to retrieve
        :arg doc_type: Default type of document to get
        :arg fields: Default fields to return

        See `ES's Multi Get API`_ for more detail.

        .. _`ES's Multi Get API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/docs-multi-get.html
        """
        doc_template = dict(
            filter(
                itemgetter(1),
                [('_index', index), ('_type', doc_type), ('fields', fields)]))

        docs = []
        for id in ids:
            doc = doc_template.copy()
            if isinstance(id, dict):
                doc.update(id)
            else:
                doc['_id'] = id
            docs.append(doc)

        return self.send_request(
            'GET', ['_mget'], {'docs': docs}, query_params=query_params)

    @es_kwargs('routing', 'parent', 'timeout', 'replication', 'consistency',
               'percolate', 'refresh', 'retry_on_conflict', 'fields')
    def update(self, index, doc_type, id, script=None, params=None, lang=None,
               query_params=None, doc=None, upsert=None, doc_as_upsert=None):
        """
        Update an existing document. Raise ``TypeError`` if ``script``, ``doc``
        and ``upsert`` are all unspecified.

        :arg index: The name of the index containing the document
        :arg doc_type: The type of the document
        :arg id: The ID of the document
        :arg script: The script to be used to update the document
        :arg params: A dict of the params to be put in scope of the script
        :arg lang: The language of the script. Omit to use the default,
            specified by ``script.default_lang``.
        :arg doc: A partial document to be merged into the existing document
        :arg upsert: The content for the new document created if the document
            does not exist
        :arg doc_as_upsert: The provided document will be inserted if the 
            document does not already exist

        See `ES's Update API`_ for more detail.

        .. _`ES's Update API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/docs-update.html
        """
        if script is None and doc is None and upsert is None:
            raise TypeError('At least one of the script, doc, or upsert '
                            'kwargs must be provided.')

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
        if doc_as_upsert:
            body['doc_as_upsert'] = doc_as_upsert
        return self.send_request(
            'POST',
            [index, doc_type, id, '_update'],
            body=body,
            query_params=query_params)

    def _search_or_count(self, kind, query, index=None, doc_type=None,
                         query_params=None):
        if isinstance(query, string_types):
            query_params['q'] = query
            body = ''
        else:
            body = query

        return self.send_request(
            'GET',
            [self._concat(index), self._concat(doc_type), kind],
            body,
            query_params=query_params)

    @es_kwargs('routing', 'size')
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
        :arg size: Limit the number of results to ``size``. Use with ``es_from`` to
            implement paginated searching.

        See `ES's search API`_ for more detail.

        .. _`ES's search API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/_the_search_api.html
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
            http://www.elastic.co/guide/en/elasticsearch/reference/current/search-count.html
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
            http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-get-mapping.html
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
            http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-put-mapping.html
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
            http://www.elastic.co/guide/en/elasticsearch/reference/current/search-more-like-this.html
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
            http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-status.html
        """
        return self.send_request('GET', [self._concat(index), '_status'],
                                 query_params=query_params)

    @es_kwargs()
    def update_aliases(self, actions, query_params=None):
        """
        Atomically add, remove, or update aliases in bulk.

        :arg actions: A list of the actions to perform

        See `ES's indices-aliases API`_.

        .. _`ES's indices-aliases API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-aliases.html
        """
        return self.send_request('POST', ['_aliases'],
                                 body={'actions': actions},
                                 query_params=query_params)

    @es_kwargs('ignore_unavailable')
    def get_aliases(self, index=None, alias='*', query_params=None):
        """
        Retrieve a listing of aliases

        :arg index: The name of an index or an iterable of indices from which
            to fetch aliases. If omitted, look in all indices.
        :arg alias: The name of the alias to return or an iterable of them.
            Wildcard * is supported. If this arg is omitted, return all aliases.

        See `ES's indices-aliases API`_.

        .. _`ES's indices-aliases API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-aliases.html
        """
        return self.send_request(
                'GET',
                [self._concat(index), '_aliases', self._concat(alias)],
                 query_params=query_params)

    def aliases(self, *args, **kwargs):
        # Deprecated.
        return self.get_aliases(*args, **kwargs)

    @es_kwargs()
    def create_index(self, index, settings=None, query_params=None):
        """
        Create an index with optional settings.

        :arg index: The name of the index to create
        :arg settings: A dictionary of settings

        If the index already exists, raise
        :class:`~pyelasticsearch.exceptions.IndexAlreadyExistsError`.

        See `ES's create-index API`_ for more detail.

        .. _`ES's create-index API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-create-index.html
        """
        return self.send_request('PUT', [index], body=settings or {},
                                 query_params=query_params)

    @es_kwargs()
    def delete_index(self, index, query_params=None):
        """
        Delete an index.

        :arg index: An index or iterable thereof to delete

        If the index is not found, raise
        :class:`~pyelasticsearch.exceptions.ElasticHttpNotFoundError`.

        See `ES's delete-index API`_ for more detail.

        .. _`ES's delete-index API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-delete-index.html
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
            http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-open-close.html
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
            http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-open-close.html
        """
        return self.send_request('POST', [index, '_open'],
                                 query_params=query_params)

    @es_kwargs()
    def get_settings(self, index, query_params=None):
        """
        Get the settings of one or more indexes.

        :arg index: An index or iterable of indexes

        See `ES's get-settings API`_ for more detail.

        .. _`ES's get-settings API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-get-settings.html
        """
        return self.send_request('GET',
                                 [self._concat(index), '_settings'],
                                 query_params=query_params)

    @es_kwargs()
    def update_settings(self, index, settings, query_params=None):
        """
        Change the settings of one or more indexes.

        :arg index: An index or iterable of indexes
        :arg settings: A dictionary of settings

        See `ES's update-settings API`_ for more detail.

        .. _`ES's update-settings API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-update-settings.html
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
            http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-update-settings.html
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
            http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-flush.html
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
            http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-refresh.html
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
            http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-optimize.html
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
            http://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-health.html
        """
        return self.send_request(
            'GET',
            ['_cluster', 'health', self._concat(index)],
            query_params=query_params)

    @es_kwargs('local')
    def cluster_state(self, metric='_all', index='_all', query_params=None):
        """
        Return state information about the cluster.

        :arg metric: Which metric to return: one of "version", "master_node",
            "nodes", "routing_table", "meatadata", or "blocks", an iterable
            of them, or a comma-delimited string of them. Defaults to all
            metrics.
        :arg index: An index or iterable of indexes to return info about

        See `ES's cluster-state API`_ for more detail.

        .. _`ES's cluster-state API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-state.html
        """
        return self.send_request(
            'GET',
            ['_cluster', 'state', self._concat(metric), self._concat(index)],
            query_params=query_params)

    @es_kwargs('routing', 'preference', 'ignore_unavailable',
               'percolate_format')
    def percolate(self, index, doc_type, doc, query_params=None):
        """
        Run a JSON document through the registered percolator queries, and
        return which ones match.

        :arg index: The name of the index to which the document pretends to
            belong
        :arg doc_type: The type the document should be treated as if it has
        :arg doc: A Python mapping object, convertible to JSON, representing
            the document

        Use :meth:`index()` to register percolators. See `ES's percolate API`_
        for more detail.

        .. _`ES's percolate API`:
            http://www.elastic.co/guide/en/elasticsearch/reference/current/search-percolate.html#_percolate_api
        """
        return self.send_request('GET',
                                 [index, doc_type, '_percolate'],
                                 doc,
                                 query_params=query_params)


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
