Migrating From ``pyes``
=======================

Moving your project from ``pyes`` to ``pyelasticsearch`` is an easy process,
particularly for most simple use cases. This page lists a couple code changes
that may be necessary to complete your upgrade.

* ``pyelasticsearch`` requires ``requests`` to be version 1.x. Breaking
  changes were introduced into ``requests``, so if your project was
  previously using 0.x, you may need to update your code (most likely change
  ``response.json`` to ``response.json()``)

* Instantiating the client should be as simple as changing the invocation::

    pyes.ES(host, **kwargs)

  to::

    pyelasticsearch.ElasticSearch(host, **kwargs)

* ``pyelasticsearch`` has no method ``create_index_if_missing``. Instead,
  you'll need catch the exception manually::

    try:
        connection.create_index(index='already_existing_index')
    except pyelasticsearch.IndexAlreadyExistsError as ex:
        print 'Index already exists, moving on...'

* Instead of using ``pyes``'s ``_send_request``, you'll want to use
  :py:meth:`pyelasticsearch.ElasticSearch.send_request`. This also requires the
  path to be passed as an iterable instead of a string. For example::

    es._send_request('POST', 'my_index/my_doc_type', body)

  would become::

    connection.send_request('POST', ['my_index', 'my_doc_type'], body)

* If using the ``indices`` keyword argument in ``pyes``, the
  ``pyelasticsearch`` analog is the ``index`` keyword argument.

* If using the ``doc_types`` keyword argument in ``pyes``, the
  ``pyelasticsearch`` analog is the ``doc_type`` keyword argument.

* :py:meth:`pyelasticsearch.ElasticSearch.get` will raise a
  :class:`pyelasticsearch.exceptions.ElasticHttpNotFoundError` exception if
  no results are found.

* ``pyes`` expects arguments to ``index`` to be in a
  different order than :py:meth:`pyelasticsearch.ElasticSearch.index`. The
  document to be indexed needs to be moved from the first positional argument
  to the third.

* :py:meth:`pyelasticsearch.ElasticSearch.send_request` will raise an error if
  no JSON content can be parsed from the response. In the event that you expect
  the response to not contain any JSON content, you will need to catch the
  exception and inspect the status code. For example::

    try:
        # Check for the existence of the "pycon" index
        connection.send_request('HEAD', ['pycon'])
    except Exception as ex:
        if ex.response.status_code == 200:
            print 'The index exists!'

* If using ``search_raw`` from ``pyes``, you can use
  :py:meth:`pyelasticsearch.ElasticSearch.search` and, if necessary, rename
  the keyword arguments.
