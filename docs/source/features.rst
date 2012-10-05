========
Features
========

JSON Conversion
===============

pyelasticsearch converts transparently between Python datastructures and JSON.
In request bodies, all the standard conversions are made: strings, numeric
types, nulls, etc. In addition, we convert ``datetime`` and ``date`` instances
to the format ES understands: ``2012-02-23T14:26:01``. ``date`` objects are
taken to represent midnight on their day.

A future release will convert more types, like datetimes, to Python in
responses.


Connection Pooling
==================

Connection pooling saves setting up a whole new TCP connection for each ES
request, dropping latency by an order of magnitude. The ElasticSearch object is
thread-safe; to take best advantage of connection pooling, create one instance,
and share it among all threads. At most, the object will hold a number of
connections to each node equal to the number of threads.


Load-balancing and Failover
===========================

An ElasticSearch object can take a list of node URLs on construction. This lets
us balance load and maintain availability when nodes go down: pyelasticsearch
will randomly choose a server URL for each request. If a node fails to respond
before a timeout period elapses, it is assumed down and not tried again for
awhile. Meanwhile, pyelasticsearch will retry the request on a different node
if ``max_retries`` was set to something greater than zero at construction. If
*all* nodes are marked as down, pyelasticsearch will loosen its standards and
try sending requests to them, marking them alive if they respond.


Forward-Compatibility Kwargs
============================

All methods that correspond to ES calls take an arbitrary set of kwargs that
can be used to pass query string parameters directly to ES. Certain kwargs
(called out by the ``@es_kwargs`` decorator) are explicitly recognized as being
claimed by ES and will never be trod upon by future versions of
pyelasticsearch. To avoid conflicts, kwargs not yet so recognized should have
"\es_" prepended by the caller. pyelasticsearch will strip off the "\es_" and
pass the rest along to ES unscathed. Ideally, we'll then add explicit
recognition of those args in a future release.

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

Datetimes and dates
    Datetimes are converted to ISO strings, like "2001-12-25T13:04:56". Dates
    convert to midnight: "2001-12-25T00:00:00".

Anything else raises a TypeError.
