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

    .. automethod:: index(index, doc_type, doc, id=None, force_insert=False[, other kwargs listed below])

    .. automethod:: bulk_index(index, doc_type, docs, id_field='id'[, other kwargs listed below])

    .. automethod:: delete(index, doc_type, id[, other kwargs listed below])

    .. automethod:: delete_all(index, doc_type[, other kwargs listed below])

    .. automethod:: delete_by_query(index, doc_type, query[, other kwargs listed below])

    .. automethod:: get(index, doc_type, id[, other kwargs listed below])

    .. automethod:: search(query[, other kwargs listed below])

    .. automethod:: update(index, doc_type, id, script[, other kwargs listed below])

    .. automethod:: count(query, index, doc_type[, other kwargs listed below])

    .. automethod:: get_mapping(index=None, doc_type=None)

    .. automethod:: put_mapping(index, doc_type, mapping[, other kwargs listed below])

    .. automethod:: more_like_this(index, doc_type, id, fields, body=''[, other kwargs listed below])

    .. automethod:: status(index=None[, other kwargs listed below])

    .. automethod:: create_index(index, settings=None)

    .. automethod:: delete_index(index)

    .. automethod:: delete_all_indexes()

    .. automethod:: close_index(index)

    .. automethod:: open_index(index)

    .. automethod:: update_settings(index, settings)

    .. automethod:: update_all_settings(settings)

    .. automethod:: flush(index=None[, other kwargs listed below])

    .. automethod:: refresh(index=None)

    .. automethod:: gateway_snapshot(index=None)

    .. automethod:: optimize(index=None[, other kwargs listed below])

    .. automethod:: health(index=None[, other kwargs listed below])


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
