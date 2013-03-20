Migrating From ``pyes``
=======================

Moving your project from ``pyes`` to ``pyelasticsearch`` is easy, especially
for simple use cases. Here are some code changes that will aid your porting.

* ``pyelasticsearch`` requires ``requests`` 1.x. Breaking changes were
  introduced in ``requests`` 1.0, so if your project was using a previous
  version, you may need to update your code. Most likely, you just need to
  change ``response.json`` to ``response.json()``.

* Instantiating the client should be as simple as changing the invocation... ::

    pyes.ES(host, **kwargs)

  ...to... ::

    pyelasticsearch.ElasticSearch(host, **kwargs)

* ``pyelasticsearch`` has no method ``create_index_if_missing``. Instead,
  you'll need catch the exception manually::

    try:
        connection.create_index(index='already_existing_index')
    except pyelasticsearch.IndexAlreadyExistsError as ex:
        print 'Index already exists, moving on...'

* Instead of using ``pyes``'s ``_send_request``, use
  :py:meth:`~pyelasticsearch.ElasticSearch.send_request`. This also requires the
  path to be passed as an iterable instead of a string. For example... ::

    es._send_request('POST', 'my_index/my_doc_type', body)

  ...becomes... ::

    connection.send_request('POST', ['my_index', 'my_doc_type'], body)

* The ``indices`` keyword argument in ``pyes`` turns to ``index`` in
  ``pyelasticsearch``, whether the method takes multiple indices or not.

* The ``doc_types`` keyword argument in ``pyes`` turns to ``doc_type`` in
  ``pyelasticsearch``.

* :py:meth:`~pyelasticsearch.ElasticSearch.get` will raise
  :class:`~pyelasticsearch.exceptions.ElasticHttpNotFoundError` if
  the requested documents are not found.

* ``pyes`` expects arguments to ``index`` to be in a
  different order than our :py:meth:`~pyelasticsearch.ElasticSearch.index`. The
  document to be indexed needs to be moved from the first positional argument
  to the third.

* :py:meth:`~pyelasticsearch.ElasticSearch.send_request` will raise an error if
  the response can't be converted to JSON. If you expect that a response will
  not be JSON, catch the exception and inspect the status code. For example...
  ::

    connection = ElasticSearch(host)
    try:
        # Check for the existence of the "pycon" index:
        connection.send_request('HEAD', ['pycon'])
    except InvalidJsonResponseError as exc:
        if exc.response.status_code == 200:
            print 'The index exists!'

* If using ``search_raw`` from ``pyes``, you can use
  :py:meth:`~pyelasticsearch.ElasticSearch.search` and, if necessary, rename
  the keyword arguments.
