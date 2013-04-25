Changelog
=========

v0.6 (unreleased)
-----------------

.. warning::

  Note the change in behavior of ``bulk_index()`` in this release. This change
  probably brings it more in line with your expectations. But double check,
  since it now overwrites existing docs in situations where it didn't before.

  Also, we made a backward-incompatible spelling change to a little-used
  ``index()`` kwarg.

* ``bulk_index()`` now overwrites any existing doc of the same ID and doctype.
  Before, it did nothing at all if a document already existed, probably much to
  your surprise. (We removed the ``'op_type': 'create'`` pair, whose intentions
  were always mysterious.) (Gavin Carothers)
* Rename the ``force_insert`` kwarg of ``index()`` to ``only_if_absent``. The
  old name implied the opposite of what it actually did. (Gavin Carothers)


v0.5 (2013-04-20)
-----------------

* Support multiple indices and doctypes in ``delete_by_query()``. Accept both
  string and JSON queries in the ``query`` arg, just as ``search()`` does.
  Passing the ``q`` arg explicitly is now deprecated.
* Add ``multi_get``.
* Add ``percolate``. Thanks, Adam Georgiou and Joseph Rose!
* Add ability to specify the parent document in ``bulk_index()``. Thanks, Gavin
  Carothers!
* Remove the internal, undocumented ``from_python`` method. django-haystack
  users will need to upgrade to a newer version that avoids using it.
* Refactor JSON encoding machinery. Now it's clearer how to customize it: just
  plug your custom JSON encoder class into ``ElasticSearch.json_encoder``.
* Don't crash under ``python -OO``.
* Support non-ASCII URL path components (like Unicode document IDs) and query
  string param values.
* Switch to the nose testrunner.


v0.4.1 (2013-03-25)
-------------------

* Fix a bug introduced in 0.4 wherein "None" was accidentally sent to ES when
  an ID wasn't passed to ``index()``.


v0.4 (2013-03-19)
-----------------

* Support Python 3.
* Support more APIs:

  * ``cluster_state``
  * ``get_settings``
  * ``update_aliases`` and ``aliases``
  * ``update`` (existed but didn't work before)

* Support the ``size`` param of the ``search`` method. (You can now change
  ``es_size`` to ``size`` in your code if you like.)
* Support the ``fields`` param on ``index`` and ``update`` methods, new since
  ES 0.20.
* Maintain better precision of floats when passed to ES.
* Change endpoint of bulk indexing so it works on ES < 0.18.
* Support documents whose ID is 0.
* URL-escape path components, so doc IDs containing funny chars work.
* Add a dedicated ``IndexAlreadyExistsError`` exception for when you try to
  create an index that already exists. This helps you trap this situation
  unambiguously.
* Add docs about upgrading from pyes.
* Remove the undocumented and unused ``to_python`` method.


v0.3 (2013-01-10)
-----------------

* Correct the ``requests`` requirement to require a version that has everything
  we need. In fact, require requests 1.x, which has a stable API.
* Add ``update()`` method.
* Make ``send_request`` method public so you can use ES APIs we don't yet
  explicitly support.
* Handle JSON translation of Decimal class and sets.
* Make ``more_like_this()`` take an arbitrary request body so you can filter
  the returned docs.
* Replace the ``fields`` arg of ``more_like_this`` with ``mlt_fields``. This
  makes it actually work, as it's the param name ES expects.
* Make explicit our undeclared dependency on simplejson.


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

Initial release based on the work of Robert Eanes and other authors
