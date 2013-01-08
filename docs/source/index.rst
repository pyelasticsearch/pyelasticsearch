pyelasticsearch
===============

pyelasticsearch is a clean, future-proof, high-scale API to elasticsearch. It
provides features like...

* Transparent conversion of Python data types to and from JSON
* Translating HTTP status codes representing failure into exceptions
* Connection pooling
* Load balancing of requests across nodes in a cluster
* Failed-node marking to avoid downed nodes for a period
* Optional automatic retrying of failed requests


A Taste of the API
------------------

Make a pooling, balancing, all-singing, all-dancing connection object::

  >>> es = ElasticSearch('http://localhost:9200/')

Index some documents::

  >>> es.index("contacts", "person", {"name":"Joe Tester", "age": 25, "title": "QA Master"}, id=1)
  {u'_type': u'person', u'_id': u'1', u'ok': True, u'_version': 1, u'_index': u'contacts'}
  >>> es.index("contacts", "person", {"name":"Jessica Coder", "age": 32, "title": "Programmer"}, id=2)
  {u'_type': u'person', u'_id': u'2', u'ok': True, u'_version': 1, u'_index': u'contacts'}
  >>> es.index("contacts", "person", {"name":"Freddy Tester", "age": 29, "title": "Office Assistant"}, id=3)
  {u'_type': u'person', u'_id': u'3', u'ok': True, u'_version': 1, u'_index': u'contacts'}

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

.. _`elasticsearch query DSL`: http://www.elasticsearch.org/guide/reference/query-dsl

::

  >>> query = {'query': {
  ...             'filtered': {
  ...                 'query': {
  ...                     'query_string': {'query': 'name:tester'}
  ...                 },
  ...                 'filter': {
  ...                     'range': {
  ...                         'age': {
  ...                             'from': 27,
  ...                             'to': 37,
  ...                         },
  ...                     },
  ...                 },
  ...             },
  ...         },
  ...     }
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


Contents
--------

.. toctree::
   :maxdepth: 2

   features
   api
   changelog
   dev


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

