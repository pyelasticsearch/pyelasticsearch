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


ElasticSearch Class
===================

.. py:module:: pyelasticsearch

Unless otherwise indicated, methods return the JSON-decoded response sent by
elasticsearch. This way, you don't lose any part of the return value, no matter
how esoteric. But fear not: if there was an error, an exception will be raised,
so it'll be hard to miss.

.. autoclass:: ElasticSearch

    .. autoattribute:: json_encoder

Bulk Indexing Methods
---------------------

.. class:: ElasticSearch

    .. automethod:: bulk(actions, index=None, doc_type=None[, other kwargs listed below])

    .. automethod:: index_op

    .. automethod:: delete_op

    .. automethod:: update_op

    .. automethod:: bulk_index(index, doc_type, docs, id_field='id', parent_field='_parent'[, other kwargs listed below])

There's also a helper function, outside the ElasticSearch class:

.. autofunction:: bulk_chunks


Other Methods
-------------

.. class:: ElasticSearch

    .. automethod:: aliases(index=None[, other kwargs listed below])

    .. automethod:: close_index(index)

    .. automethod:: cluster_state(metric='_all', index='_all'[, other kwargs listed below])

    .. automethod:: count(query[, other kwargs listed below])

    .. automethod:: create_index(index, settings=None)

    .. automethod:: delete(index, doc_type, id[, other kwargs listed below])

    .. automethod:: delete_all_indexes()

    .. automethod:: delete_all(index, doc_type[, other kwargs listed below])

    .. automethod:: delete_by_query(index, doc_type, query[, other kwargs listed below])

    .. automethod:: delete_index(index)

    .. automethod:: flush(index=None[, other kwargs listed below])

    .. automethod:: gateway_snapshot(index=None)

    .. automethod:: get(index, doc_type, id[, other kwargs listed below])

    .. automethod:: get_mapping(index=None, doc_type=None)

    .. automethod:: get_settings(index[, other kwargs listed below])

    .. automethod:: health(index=None[, other kwargs listed below])

    .. automethod:: index(index, doc_type, doc, id=None, overwrite_existing=True[, other kwargs listed below])

    .. automethod:: more_like_this(index, doc_type, id, fields, body=''[, other kwargs listed below])

    .. automethod:: multi_get(ids, index=None, doc_type=None, fields=None[, other kwargs listed below])

    .. automethod:: open_index(index)

    .. automethod:: optimize(index=None[, other kwargs listed below])

    .. automethod:: percolate(index, doc_type, doc[, other kwargs listed below])

    .. automethod:: put_mapping(index, doc_type, mapping[, other kwargs listed below])

    .. automethod:: refresh(index=None)

    .. automethod:: scroll([, other kwargs listed below])

    .. automethod:: search(query[, other kwargs listed below])

    .. automethod:: send_request

    .. automethod:: status(index=None[, other kwargs listed below])

    .. automethod:: update(index, doc_type, id, script[, other kwargs listed below])

    .. automethod:: update_aliases(settings[, other kwargs listed below])

    .. automethod:: update_all_settings(settings)

    .. automethod:: update_settings(index, settings)


.. _error-handling:

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


Debugging
=========

pyelasticsearch logs to the ``elasticsearch.trace`` logger using the Python
logging module. If you configure that to show INFO-level messages, then it'll
show the requests in curl form and their responses. To see when a server is
marked as dead, follow the ``elasticsearch`` logger.

::

    import logging

    logging.getLogger('elasticsearch.trace').setLevel(logging.INFO)
    logging.getLogger('elasticsearch').setLevel(logging.INFO)


.. Note::

   This assumes that logging is already set up with something like this::

       import logging

       logging.basicConfig()


pyelasticsearch will log lines like::

    INFO:elasticsearch.trace: curl
    -XGET 'http://localhost:9200/fooindex/testdoc/_search' -d '{"fa
    cets": {"topics": {"terms": {"field": "topics"}}}}'


You can copy and paste the curl line, and it'll work on the command line.
