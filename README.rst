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
    conn.index({"name":"Joe Tester", "age": 25, "title": "QA Master"}, "contacts", "person", 1)
    conn.index({"name":"Jessica Coder", "age": 32, "title": "Programmer"}, "contacts", "person", 2)
    conn.index({"name":"Freddy Tester", "age": 29, "title": "Office Assistant"}, "contacts", "person", 3)

    # Refresh the index to pick up the latest documents.
    conn.refresh("contacts")

    # Get just Jessica's document.
    jessica = conn.get("contacts", "person", 2)

    # Perform a simple search.
    results = conn.search("name:joe OR name:freddy")

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
    results = conn.search(query)

    # Clean up.
    conn.delete_index("contacts")

For more examples, please check out the doctests & ``tests.py``.


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


Why Not pyes?
=============
* pyes puts pointless abstractions in front of mappings. Dicts are fine, and
  its API just gives you one more thing you have to learn.
* pyes's dead-server handling just throws up its hands if all of the servers
  are marked dead. pyelasticsearch will make an effort to try a dead one if no
  live ones remain, and, if it responds, it will mark it live.
* There are a lot of weirdnesses in the code, like monkeypatching and uses of
  setattr with constant args.


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

  Other changes:

  * Add load-balancing across multiple nodes.
  * Add failover in the case where a node doesn't respond.
  * Add `close_index`, `open_index`, `update_settings`, `health`.
  * Automatically convert `datetime` objects when encoding JSON.
  * In routines that can take either one or many indexes, don't require the
    caller to wrap a single index name in a list.
  * Many other internal improvements
