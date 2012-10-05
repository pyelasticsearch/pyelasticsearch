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

    .. automethod:: ElasticSearch.index(index, doc_type, doc, id=None, force_insert=False[, other kwargs listed below])

    .. automethod:: ElasticSearch.bulk_index(index, doc_type, docs, id_field='id'[, other kwargs listed below])

    .. automethod:: ElasticSearch.delete(index, doc_type, id[, other kwargs listed below])

    .. automethod:: ElasticSearch.delete_all(index, doc_type[, other kwargs listed below])

    .. automethod:: ElasticSearch.delete_by_query(index, doc_type, query[, other kwargs listed below])

    .. automethod:: ElasticSearch.get(index, doc_type, id[, other kwargs listed below])

    .. automethod:: ElasticSearch.search(query, index, doc_type[, other kwargs listed below])

    .. automethod:: ElasticSearch.count(query, index, doc_type[, other kwargs listed below])

    .. automethod:: ElasticSearch.get_mapping(index=None, doc_type=None)

    .. automethod:: ElasticSearch.put_mapping(index, doc_type, mapping[, other kwargs listed below])

    .. automethod:: ElasticSearch.more_like_this(index, doc_type, id, fields[, other kwargs listed below])

    .. automethod:: ElasticSearch.status(index=None[, other kwargs listed below])

    .. automethod:: ElasticSearch.create_index(index, settings=None)

    .. automethod:: ElasticSearch.delete_index(index)

    .. automethod:: ElasticSearch.delete_all_indexes()

    .. automethod:: ElasticSearch.close_index(index)

    .. automethod:: ElasticSearch.open_index(index)

    .. automethod:: ElasticSearch.update_settings(index, settings)

    .. automethod:: ElasticSearch.update_all_settings(settings)

    .. automethod:: ElasticSearch.flush(index=None[, other kwargs listed below])

    .. automethod:: ElasticSearch.refresh(index=None)

    .. automethod:: ElasticSearch.gateway_snapshot(index=None)

    .. automethod:: ElasticSearch.optimize(index=None[, other kwargs listed below])

    .. automethod:: ElasticSearch.health(index=None[, other kwargs listed below])


Error Handling
==============

Any method representing an ES API call can raise one of the following
exceptions:

.. automodule:: pyelasticsearch.exceptions
    :members:

    .. class:: ConnectionError

        Exception raised there is a connection error and we are out of retries.
        (See the ``max_retries`` argument to :class:`ElasticSearch`.)

    .. class:: Timeout

        Exception raised when an HTTP request times out and we are out of
        retries. (See the ``max_retries`` argument to :class:`ElasticSearch`.)
