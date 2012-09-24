===============
Version History
===============

0.3
  Backward-incompatible changes:

  * Tweak ``search()`` and ``count()`` APIs. Now each simply takes either a
    textual or a dict query as its first argument. There's no more silliness
    about needing to use either a ``q`` or a ``body`` kwarg.
  * Standardize on the singular for the names of kwargs. It's not always
    obvious whether an ES API allows for multiple indexes. This was leading me
    to have to look aside to the docs to determine whether the kwarg was called
    ``index`` or ``indexes``. Using the singular everywhere will result in
    fewer doc lookups, especially for the common case of a single index.

  Other changes:
  
  * Add beginnings of Sphinx documentation.

0.2.1
  * Recognize and convert datetimes and dates in pass-through kwargs. This is
    useful for ``timeout``.

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
    * Crash harder if JSON encoding fails: that always indicates a bug in
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
