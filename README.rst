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
pooling, create one, and share it among all threads. At most, the object will
hold a number of connections to each node equal to the number of threads.


Load-balancing and Failover
===========================

An ElasticSearch object can take a list of node URLs on construction. This lets
us balance load and maintain availability when nodes go down: pyelasticsearch
will randomly choose a server URL for each request. If a node fails to respond
before a timeout period elapses, it is assumed down and not tried again for
awhile. Meanwhile, pyelasticsearch will retry the request on a different node
if ``max_retries`` was set to something greater than zero at construction

Why Not pyes?
=============
* pyes puts pointless abstractions in front of mappings. Dicts are fine, and
  its API just gives you one more thing you have to learn.
* pyes's dead-server handling just throws up its hands if all of the servers
  are marked dead. pyelasticsearch will make an effort to try a dead one if no
  live ones remain, and, if it responds, it will mark it live.


License
=======

Licensed under the New BSD license.


Credits
=======

Used `pysolr`_ as a jumping off point - thanks guys.

.. _`pysolr`: http://github.com/jkocherhans/pysolr
