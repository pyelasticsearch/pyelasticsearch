Changelog
=========

v0.2 (2012-10-06)
-----------------

Many thanks to Erik Rose for almost completely rewriting the API to follow
best practices, improve the API user experience, and make pyelasticsearch
future-proof.

.. warning::

  This release is **backward-incompatible** in numerous ways, please
  read the following section carefully. If in doubt, you can easily stick
  with pyelasticsearch 0.1.

Backward-incompatible changes:

* Simplify ``search()`` and ``count()`` calling conventions. Each now supports
  either a textual or a dict-based query as its first argument. There's no
  longer a need to, for example, pass an empty string as the first arg in order
  to use a JSON query (a common case).

* Standardize on the singular for the names of the ``index`` and ``doc_type``
  kwargs. It's not always obvious whether an ES API allows for multiple
  indexes. This was leading me to have to look aside to the docs to determine
  whether the kwarg was called ``index`` or ``indexes``. Using the singular
  everywhere will result in fewer doc lookups, especially for the common case
  of a single index.

* Rename ``morelikethis`` to ``more_like_this`` for consistency with other
  methods.

* ``index()`` now takes ``(index, doc_type, doc)`` rather than ``(doc, index,
  doc_type)``, for consistency with ``bulk_index()`` and other methods.

* Similarly, ``put_mapping()`` now takes ``(index, doc_type, mapping)``
  rather than ``(doc_type, mapping, index)``.

* To prevent callers from accidentally destroying large amounts of data...

  * ``delete()`` no longer deletes all documents of a doctype when no ID is
    specified; use ``delete_all()`` instead.
  * ``delete_index()`` no longer deletes all indexes when none are given; use
    ``delete_all_indexes()`` instead.
  * ``update_settings()`` no longer updates the settings of all indexes when
    none are specified; use ``update_all_settings()`` instead.

* ``setup_logging()`` is gone. If you want to configure logging, use the
  logging module's usual facilities. We still log to the "pyelasticsearch"
  named logger.

* Rethink error handling:

  * Raise a more specific exception for HTTP error codes so callers can catch
    it without examining a string.
  * Catch non-JSON responses properly, and raise the more specific
    ``NonJsonResponseError`` instead of the generic ``ElasticSearchError``.
  * Remove mentions of nonexistent exception types that would cause crashes
    in their ``except`` clauses.
  * Crash harder if JSON encoding fails: that always indicates a bug in
    pyelasticsearch.
  * Remove the ill-defined ``ElasticSearchError``.
  * Raise ``ConnectionError`` rather than ``ElasticSearchError`` if we can't
    connect to a node (and we're out of auto-retries).
  * Raise ``ValueError`` rather than ``ElasticSearchError`` if no documents
    are passed to ``bulk_index``.
  * All exceptions are now more introspectable, because they don't
    immediately mash all the context down into a string. For example, you can
    recover the unmolested response object from ``ElasticHttpError``.
  * Removed ``quiet`` kwarg, meaning we always expose errors.

Other changes:

* Add Sphinx documentation.
* Add load-balancing across multiple nodes.
* Add failover in the case where a node doesn't respond.
* Add ``close_index``, ``open_index``, ``update_settings``, ``health``.
* Support passing arbitrary kwargs through to the ES query string. Known ones
  are taken verbatim; unanticipated ones need an "\es_" prefix to guarantee
  forward compatibility.
* Automatically convert ``datetime`` objects when encoding JSON.
* Recognize and convert datetimes and dates in pass-through kwargs. This is
  useful for ``timeout``.
* In routines that can take either one or many indexes, don't require the
  caller to wrap a single index name in a list.
* Many other internal improvements

v0.1 (2012-08-30)
-----------------

Initial release based on the work of Robert Eanes and other the other authors.
