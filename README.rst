===============
pyelasticsearch
===============

A Python client for `elasticsearch`_.

.. _`elasticsearch`: http://www.elasticsearch.org/


Usage
=====

``pyelasticsearch`` handles the low-level interactions with elasticsearch,
allowing you to use native Python datatypes to index or perform queries.

Example::

    conn = ElasticSearch('http://localhost:9200/')

    # Index some documents.
    conn.index("contacts", "person", {"name":"Joe Tester", "age": 25, "title": "QA Master"}, id=1)
    conn.index("contacts", "person", {"name":"Jessica Coder", "age": 32, "title": "Programmer"}, id=2)
    conn.index("contacts", "person", {"name":"Freddy Tester", "age": 29, "title": "Office Assistant"}, id=3)

    # Refresh the index to pick up the latest documents.
    conn.refresh("contacts")

    # Get just Jessica's document.
    jessica = conn.get("contacts", "person", 2)

    # Perform a simple search.
    results = conn.search(q="name:joe OR name:freddy")

    # Perform a search using the elasticsearch Query DSL (http://www.elasticsearch.org/guide/reference/query-dsl)
    query = {
        "query_string": {
            "query": "name:tester"
        },
        "filtered": {
            "filter": {
                "range": {
                    "age": {
                        "from": 27,
                        "to": 37,
                    },
                },
            },
        },
    }
    results = conn.search(body=query)

    # Clean up.
    conn.delete_index("contacts")

For more examples, please check out the doctests and ``tests.py``.


Connection Pooling
==================

The ElasticSearch object is thread-safe. To take best advantage of connection
pooling, create one instance, and share it among all threads. At most, the
object will hold a number of connections to each node equal to the number of
threads.


Load-balancing and Failover
===========================

An ElasticSearch object can take a list of node URLs on construction. This lets
us balance load and maintain availability when nodes go down: pyelasticsearch
will randomly choose a server URL for each request. If a node fails to respond
before a timeout period elapses, it is assumed down and not tried again for
awhile. Meanwhile, pyelasticsearch will retry the request on a different node
if ``max_retries`` was set to something greater than zero at construction.


Forward-Compatibility Kwargs
============================

All methods that correspond to ES calls take an arbitrary set of kwargs that
can be used to pass query string parameters directly to ES. Certain kwargs
(called out by the ``es_kwargs`` decorator) are explicitly recognized as being
claimed by ES and will never be trod upon by pyelasticsearch. To avoid
conflicts, kwargs not yet so recognized should have "\es_" prepended by the
caller. pyelasticsearch will strip off the "\es_" and pass the rest along to ES
unscathed. Ideally, we'll then add support for those args in a future release.

These "pass-through" kwargs are converted to text as follows:

Bools
    ``True``: "true"
    ``False``: "false"

Strings
    Passed unmolested

Ints, longs, and floats
    Converted to strings via ``str()``

Lists and tuples
    Joined with commas, e.g. ``['one-index', two-index']`` becomes
    ``one-index,two-index``

Anything else raises a TypeError.


License
=======

Licensed under the New BSD license.


Credits
=======

Used `pysolr`_ as a jumping off point - thanks guys.

.. _`pysolr`: http://github.com/jkocherhans/pysolr


Version History
===============

0.2
  Pretty much a rewrite by Erik Rose

  Backward-incompatible changes:

  * Rethink error handling:

    * Raise a more specific exception for HTTP error codes so callers can catch
      it without examining a string.
    * Catch non-JSON responses properly, and raise the more specific
      `NonJsonResponseError` instead of the generic `ElasticSearchError`.
    * Remove mentions of nonexistent exception types that would cause crashes
      in their `except` clauses.
    * Crash harder if JSON encoding happens: that always indicates a bug in
      pyelasticsearch.
    * Remove the ill-defined `ElasticSearchError`.
    * Raise `ConnectionError` rather than `ElasticSearchError` if we can't
      connect to a node (and we're out of auto-retries).
    * Raise `ValueError` rather than `ElasticSearchError` if no documents are
      passed to `bulk_index`.
    * All exceptions are now more introspectable, because they don't
      immediately mash all the context down into a string. For example, you can
      recover the unmolested response object from `ElasticHttpError`.
    * Removed `quiet` kwarg, meaning we always expose errors.
  * Rename `morelikethis` to `more_like_this` for consistency with other
    methods.
  * ``index()`` now takes ``(index, doc_type, doc)`` rather than ``(doc, index,
    doc_type)``, for consistency with ``bulk_index()`` and other methods.
  * Similarly, ``put_mapping()`` now takes ``(index, doc_type, mapping)``
    rather than ``(doc_type, mapping, index)``.
  * To prevent callers from accidentally destroying large amounts of data...

    * ``delete()`` no longerdeletes all documents of a doctype when no ID is
      specified; use ``delete_all()`` instead.
    * ``delete_index()`` no longer deletes all indexes when none are given; use
      ``delete_all_indexes()`` instead.
    * ``update_settings()`` no longer updates the settings of all indexes when
      none are specified; use ``update_all_settings()`` instead.
  * ``search()`` and ``count()`` no longer take the query-string-dwelling query
    (if any) as an arg; it now goes in the ``q`` kwarg, which mirrors how ES
    itself takes it. This means callers no longer have to pass an empty string
    as the first arg when they want to use a JSON query (a common case).
  * ``setup_logging()`` is gone. If you want to configure logging, use the
    logging module's usual ways. We still log to the "pyelasticsearch" named
    logger.

  Other changes:

  * Add load-balancing across multiple nodes.
  * Add failover in the case where a node doesn't respond.
  * Add `close_index`, `open_index`, `update_settings`, `health`.
  * Support passing arbitrary kwargs through to the ES query string. Known ones
    are taken verbatim; unanticipated ones need an "\es_" prefix to guarantee
    forward compatibility.
  * Automatically convert `datetime` objects when encoding JSON.
  * In routines that can take either one or many indexes, don't require the
    caller to wrap a single index name in a list.
  * Many other internal improvements
