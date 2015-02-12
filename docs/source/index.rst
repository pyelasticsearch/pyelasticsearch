pyelasticsearch
===============

pyelasticsearch is a clean, future-proof, high-scale API to elasticsearch. It
provides...

* Transparent conversion of Python data types to and from JSON, including
  datetimes and the arbitrary-precision Decimal type
* Translating HTTP failure status codes into exceptions
* Connection pooling
* HTTP authentication
* Load balancing across nodes in a cluster
* Failed-node marking to avoid downed nodes for a period
* Optional automatic retrying of failed requests
* Thread safety
* Loosely coupled design, letting you customize things like JSON encoding and
  bulk indexing

For more on our philosophy and history, see :doc:`elasticsearch-py`.


A Taste of the API
------------------

Make a pooling, balancing, all-singing, all-dancing connection object::

  >>> from pyelasticsearch import ElasticSearch
  >>> es = ElasticSearch('http://localhost:9200/')

Index a document::

  >>> es.index('contacts',
  ...          'person',
  ...          {'name': 'Joe Tester', 'age': 25, 'title': 'QA Master'},
  ...           id=1)
  {u'_type': u'person', u'_id': u'1', u'ok': True, u'_version': 1, u'_index': u'contacts'}

Index a couple more documents, this time in a single request using the
bulk-indexing API::

  >>>  docs = [{'id': 2, 'name': 'Jessica Coder', 'age': 32, 'title': 'Programmer'},
  ...          {'id': 3, 'name': 'Freddy Tester', 'age': 29, 'title': 'Office Assistant'}]
  >>>  es.bulk((es.index_op(doc, id=doc.pop('id')) for doc in docs),
  ...          index='contacts',
  ...          doc_type='person')

If we had many documents and wanted to chunk them for performance,
:func:`~pyelasticsearch.bulk_chunks()` would easily rise to the task,
dividing either at a certain number of documents per batch or, for curated
platforms like Google App Engine, at a certain number of bytes. Thanks to
the decoupled design, you can even substitute your own batching function if
you have unusual needs. Bulk indexing is the most demanding ES task in most
applications, so we provide very thorough tools for representing operations,
optimizing wire traffic, and dealing with errors. See
:meth:`~pyelasticsearch.ElasticSearch.bulk()` for more.

Refresh the index to pick up the latest::

  >>> es.refresh('contacts')
  {u'ok': True, u'_shards': {u'successful': 5, u'failed': 0, u'total': 10}}

Get just Jessica's document::

  >>> es.get('contacts', 'person', 2)
  {u'_id': u'2',
   u'_index': u'contacts',
   u'_source': {u'age': 32, u'name': u'Jessica Coder', u'title': u'Programmer'},
   u'_type': u'person',
   u'_version': 1,
   u'exists': True}

Perform a simple search::

  >>> es.search('name:joe OR name:freddy', index='contacts')
  {u'_shards': {u'failed': 0, u'successful': 42, u'total': 42},
   u'hits': {u'hits': [{u'_id': u'1',
                        u'_index': u'contacts',
                        u'_score': 0.028130024999999999,
                        u'_source': {u'age': 25,
                                     u'name': u'Joe Tester',
                                     u'title': u'QA Master'},
                        u'_type': u'person'},
                       {u'_id': u'3',
                        u'_index': u'contacts',
                        u'_score': 0.028130024999999999,
                        u'_source': {u'age': 29,
                                     u'name': u'Freddy Tester',
                                     u'title': u'Office Assistant'},
                        u'_type': u'person'}],
             u'max_score': 0.028130024999999999,
             u'total': 2},
   u'timed_out': False,
   u'took': 4}

Perform a search using the `elasticsearch query DSL`_:

.. _`elasticsearch query DSL`: http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl.html

::

  >>> query = {
  ...     'query': {
  ...         'filtered': {
  ...             'query': {
  ...                 'query_string': {'query': 'name:tester'}
  ...             },
  ...             'filter': {
  ...                 'range': {
  ...                     'age': {
  ...                         'from': 27,
  ...                         'to': 37,
  ...                     },
  ...                 },
  ...             },
  ...         },
  ...     },
  ... }
  >>> es.search(query, index='contacts')
  {u'_shards': {u'failed': 0, u'successful': 42, u'total': 42},
   u'hits': {u'hits': [{u'_id': u'3',
                        u'_index': u'contacts',
                        u'_score': 0.19178301,
                        u'_source': {u'age': 29,
                                     u'name': u'Freddy Tester',
                                     u'title': u'Office Assistant'},
                        u'_type': u'person'}],
             u'max_score': 0.19178301,
             u'total': 1},
   u'timed_out': False,
   u'took': 2}

Delete the index::

  >>> es.delete_index('contacts')
  {u'acknowledged': True, u'ok': True}

For more, see the full :doc:`api`.

Contents
--------

.. toctree::
   :maxdepth: 2

   features
   api
   elasticsearch-py
   migrate
   changelog
   dev


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
