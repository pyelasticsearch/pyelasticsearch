=================
API Documentation
=================

A Word About Forward-Compatibility Kwargs
=========================================

In the following documentation, the phrase *"other kwargs listed below"* refers
to the kwargs documented in a subsequent *Parameters* section. However, it also
implicitly includes any kwargs the caller might care to make up and have passed
to ES as query string parameters. These kwargs must start with ``es_`` for
forward compatibility and will be unprefixed and converted to strings as
discussed in :doc:`features`.


ElasticSearch API
=================

.. py:module:: pyelasticsearch

    
Unless otherwise indicated, methods return the JSON-decoded response sent by
elasticsearch.

.. autoclass:: ElasticSearch
   :members:


Error Handling
==============

Any method representing an ES API call can raise one of the following
exceptions:

.. automodule:: pyelasticsearch.exceptions
    :members:

    .. exception:: ConnectionError

        Exception raised there is a connection error and we are out of retries.
        (See the ``max_retries`` argument to :class:`ElasticSearch`.)

    .. exception:: Timeout

        Exception raised when an HTTP request times out and we are out of
        retries. (See the ``max_retries`` argument to :class:`ElasticSearch`.)
