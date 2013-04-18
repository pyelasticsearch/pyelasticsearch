import sys
import unittest

from mock import patch
from nose.tools import eq_, ok_, assert_raises, assert_not_equal
import requests
import six

# Test that __all__ is sufficient:
from pyelasticsearch import *
from pyelasticsearch.tests import ElasticSearchTestCase


class IndexingTestCase(ElasticSearchTestCase):
    def tearDown(self):
        try:
            self.conn.delete_index('another-index')
        except Exception:
            pass
        super(IndexingTestCase, self).tearDown()

    def test_indexing_with_id(self):
        result = self.conn.index('test-index', 'test-type', {'name': 'Joe Tester'}, id=1)
        self.assert_result_contains(result, {'_type': 'test-type', '_id': '1', 'ok': True, '_index': 'test-index'})

    def test_indexing_with_0_id(self):
        result = self.conn.index('test-index', 'test-type', {'name': 'Joe Tester'}, id=0)
        self.assert_result_contains(result, {'_type': 'test-type', '_id': '0', 'ok': True, '_index': 'test-index'})

    def test_quoted_chars_in_id(self):
        result = self.conn.index('test-index', 'test-type', {'name': 'Joe Tester'}, id="""<>?,./`~!@#$%^&*()_+=[]\{{}|:";'""")
        self.assert_result_contains(result, {'_type': 'test-type', '_id': """<>?,./`~!@#$%^&*()_+=[]\{{}|:";'""", 'ok': True, '_index': 'test-index'})

    def test_indexing_without_id(self):
        result = self.conn.index(
            'test-index', 'test-type', {'name': 'Joe Tester'})
        self.assert_result_contains(result,
            {'_type': 'test-type', 'ok': True, '_index': 'test-index'})
        # should have an id of some value assigned.
        ok_('_id' in result and result['_id'])
        # should not generate the same id twice
        result2 = self.conn.index(
            'test-index', 'test-type', {'name': 'Barny Tester'})
        assert_not_equal(result['_id'], result2['_id'])

    def test_explicit_index_create(self):
        result = self.conn.create_index('test-index')
        self.assert_result_contains(result, {'acknowledged': True, 'ok': True})

    def test_close_index(self):
        """Make sure a close_index call on an open index reports success."""
        self.conn.create_index('test-index')
        result = self.conn.close_index('test-index')
        self.assert_result_contains(result, {'acknowledged': True, 'ok': True})

    def test_open_index(self):
        """Make sure an open_index call on a closed index reports success."""
        self.conn.create_index('test-index')
        self.conn.close_index('test-index')
        result = self.conn.open_index('test-index')
        self.assert_result_contains(result, {'acknowledged': True, 'ok': True})

    def test_get_settings(self):
        self.conn.create_index('test-index')
        result = self.conn.get_settings('test-index')
        ok_('test-index' in result)
        ok_('settings' in result['test-index'])

    def test_update_settings(self):
        """Make sure ``update_settings()`` sends the expected request."""
        with patch.object(self.conn, 'send_request') as send_request:
            self.conn.update_settings(['test-index', 'toast-index'],
                                      {'index': {'number_of_replicas': 2}})
        send_request.assert_called_once_with(
            'PUT',
            ['test-index,toast-index', '_settings'],
            body={'index': {'number_of_replicas': 2}},
            query_params={})

    def test_health(self):
        with patch.object(self.conn, 'send_request') as send_request:
            self.conn.health(['test-index', 'toast-index'],
                             wait_for_status='yellow',
                             wait_for_nodes='>=1')
        send_request.assert_called_once_with(
            'GET',
            ['_cluster', 'health', 'test-index,toast-index'],
            query_params={'wait_for_status': 'yellow',
                          'wait_for_nodes': '>=1'})

        with patch.object(self.conn, 'send_request') as send_request:
            self.conn.health()
        send_request.assert_called_once_with(
            'GET', ['_cluster', 'health', ''], query_params={})

    def test_cluster_state(self):
        result = self.conn.cluster_state(filter_routing_table=True)
        ok_('nodes' in result)
        self.assertFalse('routing_table' in result)

    def test_delete_by_id(self):
        self.conn.index('test-index', 'test-type', {'name': 'Joe Tester'}, id=1)
        self.conn.refresh(['test-index'])
        result = self.conn.delete('test-index', 'test-type', 1)
        self.assert_result_contains(result, {'_type': 'test-type', '_id': '1', 'ok': True, '_index': 'test-index'})

    def test_delete_by_0_id(self):
        self.conn.index('test-index', 'test-type', {'name': 'Joe Tester'}, id=0)
        self.conn.refresh(['test-index'])
        result = self.conn.delete('test-index', 'test-type', 0)
        self.assert_result_contains(result, {'_type': 'test-type', '_id': '0', 'ok': True, '_index': 'test-index'})

    def test_delete_by_id_without_id(self):
        self.conn.index('test-index', 'test-type', {'name': 'Joe Tester'}, id=1)
        self.conn.refresh(['test-index'])
        assert_raises(
            ValueError, self.conn.delete, 'test-index', 'test-type', '')
        assert_raises(
            ValueError, self.conn.delete, 'test-index', 'test-type', None)

    def test_delete_by_doc_type(self):
        self.conn.index('test-index', 'test-type', {'name': 'Joe Tester'}, id=1)
        self.conn.refresh(["test-index"])
        result = self.conn.delete_all("test-index", "test-type")
        self.assert_result_contains(result, {'ok': True})

    def test_delete_by_query(self):
        self.conn.index('test-index', 'test-type', {'name': 'Joe Tester'}, id=1)
        self.conn.index('test-index', 'test-type', {'name': 'Bill Baloney'}, id=2)
        self.conn.index('test-index', 'test-type', {'name': 'Horace Humdinger'}, id=3)
        self.conn.refresh(['test-index'])

        self.conn.refresh(['test-index'])
        result = self.conn.count('*:*', index=['test-index'])
        self.assert_result_contains(result, {'count': 3})

        result = self.conn.delete_by_query('test-index', 'test-type', {'query_string': {'query': 'name:joe OR name:bill'}})
        self.assert_result_contains(result, {'ok': True})

        self.conn.refresh(['test-index'])
        result = self.conn.count('*:*', index=['test-index'])
        self.assert_result_contains(result, {'count': 1})

    def test_delete_index(self):
        self.conn.create_index('another-index')
        result = self.conn.delete_index('another-index')
        self.assert_result_contains(result, {'acknowledged': True, 'ok': True})

    def test_delete_nonexistent_index(self):
        """
        Deleting a nonexistent index should raise ElasticHttpNotFoundError.
        """
        assert_raises(ElasticHttpNotFoundError,
                          self.conn.delete_index,
                          'nonexistent-index')

    def test_cannot_create_existing_index(self):
        self.conn.create_index('another-index')
        assert_raises(
            IndexAlreadyExistsError, self.conn.create_index, 'another-index')
        self.conn.delete_index('another-index')
        assert_raises(ElasticHttpError, self.conn.delete_index, 'another-index')

    def test_put_mapping(self):
        result = self.conn.create_index('test-index')
        result = self.conn.put_mapping('test-index', 'test-type', {'test-type': {'properties': {'name': {'type': 'string', 'store': 'yes'}}}})
        self.assert_result_contains(result, {'acknowledged': True, 'ok': True})

    def test_get_mapping(self):
        result = self.conn.create_index('test-index')
        mapping = {'test-type': {'properties': {'name': {'type': 'string', 'store': 'yes'}}}}
        self.conn.put_mapping('test-index', 'test-type', mapping)

        result = self.conn.get_mapping(index=['test-index'], doc_type=['test-type'])
        eq_(result, mapping)

    def test_index_status(self):
        self.conn.create_index('another-index')
        result = self.conn.status('another-index')
        self.conn.delete_index('another-index')
        ok_('indices' in result)
        self.assert_result_contains(result, {'ok': True})

    def test_index_flush(self):
        self.conn.create_index('another-index')
        result = self.conn.flush('another-index')
        self.conn.delete_index('another-index')
        self.assert_result_contains(result, {'ok': True})

    def test_index_refresh(self):
        self.conn.create_index('another-index')
        result = self.conn.refresh('another-index')
        self.conn.delete_index('another-index')
        self.assert_result_contains(result, {'ok': True})

    def test_index_optimize(self):
        self.conn.create_index('another-index')
        result = self.conn.optimize('another-index')
        self.conn.delete_index('another-index')
        self.assert_result_contains(result, {'ok': True})

    def test_bulk_index(self):
        # Try counting the docs in a nonexistent index:
        assert_raises(ElasticHttpError, self.conn.count, '*:*', index=['test-index'])

        docs = [
            {'name': 'Joe Tester'},
            {'name': 'Bill Baloney', 'id': 303},
        ]
        result = self.conn.bulk_index('test-index', 'test-type', docs)
        eq_(len(result['items']), 2)
        eq_(result['items'][0]['create']['ok'], True)
        eq_(result['items'][1]['index']['ok'], True)
        eq_(result['items'][1]['index']['_id'], '303')
        self.conn.refresh()
        eq_(self.conn.count('*:*',
                                         index=['test-index'])['count'], 2)

    def test_error_handling(self):
        # Wrong port.
        conn = ElasticSearch('http://localhost:1009200/')
        assert_raises(ConnectionError, conn.count, '*:*')

        # Test invalid JSON.
        resp = requests.Response()
        resp._content = six.b('{"busted" "json" "that": ["is] " wrong')
        assert_raises(InvalidJsonResponseError, conn._decode_response, resp)

    def test_update(self):
        """Smoke-test the ``update()`` API."""
        SCRIPT = 'ctx._source.thing += count'
        with patch.object(self.conn, 'send_request') as send_request:
            self.conn.update('some_index',
                             'some_type',
                             3,
                             SCRIPT,
                             params={'count': 5},
                             lang='python')
        send_request.assert_called_once_with(
            'POST', ['some_index', 'some_type', 3, '_update'],
            body={'script': SCRIPT,
                  'params': {'count': 5},
                  'lang': 'python'},
                  query_params={})

    def test_alias_index(self):
        self.conn.create_index('test-index')
        settings = {
            "actions": [
                {"add": {"index": "test-index", "alias": "test-alias"}}
            ]
        }
        result = self.conn.update_aliases(settings)
        self.assert_result_contains(result, {'acknowledged': True, 'ok': True})

    def test_alias_nonexistent_index(self):
        settings = {
            "actions": [
                {"add": {"index": "test1", "alias": "alias1"}}
            ]
        }
        assert_raises(ElasticHttpNotFoundError,
                          self.conn.update_aliases,
                          settings)

    def test_list_aliases(self):
        self.conn.create_index('test-index')
        settings = {
            "actions": [
                {"add": {"index": "test-index", "alias": "test-alias"}}
            ]
        }
        self.conn.update_aliases(settings)
        result = self.conn.aliases('test-index')
        eq_(result, {u'test-index': {u'aliases': {u'test-alias': {}}}})

    def test_empty_path_segments(self):
        """'' segments passed to ``_join_path`` should be omitted."""
        # Call _join_path like get_mapping might if called with no params:
        eq_(self.conn._join_path(['', '', '_mapping']),
                         '/_mapping')

    def test_0_path_segments(self):
        """
        ``0`` segments passed to ``_join_path`` should be included.

        This is so doc IDs that are 0 work.
        """
        eq_(self.conn._join_path([0, '_mapping']),
                         '/0/_mapping')

    def test_percolate(self):
        self.conn.create_index('test-index')

        # Index a few queries in the percolator
        result = self.conn.index(
            '_percolator',
            'test-index',
            {'query': {'match': {'name': 'Joe'}}},
            id='id_1')
        result = self.conn.index(
            '_percolator',
            'test-index',
            {'query': {'match': {'name': 'not_that_guy'}}},
            id='id_2')

        # Percolate a document that should match query ID 1:
        document = {'doc': {'name': 'Joe'}}
        result = self.conn.percolate('test-index','test-type', document)
        self.assert_result_contains(result, {'matches': ['id_1'], 'ok': True})

        # Percolate a document that shouldn't match any queries
        document = { 'doc': {'name': 'blah'} }
        result = self.conn.percolate('test-index','test-type', document)
        self.assert_result_contains(result, {'matches': [], 'ok': True})


class SearchTestCase(ElasticSearchTestCase):
    def setUp(self):
        super(SearchTestCase, self).setUp()
        self.conn.index('test-index', 'test-type', {'name': 'Joe Tester'}, id=1)
        self.conn.index('test-index', 'test-type', {'name': 'Bill Baloney'}, id=2)
        self.conn.refresh(['test-index'])

    def test_get_by_id(self):
        result = self.conn.get('test-index', 'test-type', 1)
        self.assert_result_contains(result, {'_type': 'test-type', '_id': '1', '_source': {'name': 'Joe Tester'}, '_index': 'test-index'})

    def test_multi_get_simple(self):
        result = self.conn.multi_get([1], index='test-index', doc_type='test-type')
        self.assert_result_contains(result, {'docs': [{'_type': 'test-type', '_id': '1', '_source': {'name': 'Joe Tester'}, '_index': 'test-index', "_version": 1, "exists": True}]})

    def test_multi_get_mix(self):
        result = self.conn.multi_get([{'_type': 'test-type', '_id': 1}], index='test-index')
        self.assert_result_contains(result, {'docs': [{'_type': 'test-type', '_id': '1', '_source': {'name': 'Joe Tester'}, '_index': 'test-index', "_version": 1, "exists": True}]})

    def test_multi_get_custom(self):
        result = self.conn.multi_get([{'_type': 'test-type', '_id': 1, 'fields': ['name'], '_index': 'test-index'}])
        self.assert_result_contains(result, {'docs': [{'_type': 'test-type', '_id': '1', 'fields': {'name': 'Joe Tester'}, '_index': 'test-index', "_version": 1, "exists": True}]})

    def test_get_count_by_search(self):
        result = self.conn.count('name:joe', index='test-index')
        self.assert_result_contains(result, {'count': 1})

    def test_search_by_field(self):
        result = self.conn.search('name:joe', index='test-index')
        self.assert_result_contains(result, {'hits': {'hits': [{'_score': 0.19178301, '_type': 'test-type', '_id': '1', '_source': {'name': 'Joe Tester'}, '_index': 'test-index'}], 'total': 1, 'max_score': 0.19178301}})

    def test_search_string_paginated(self):
        with patch.object(self.conn, 'send_request') as send_request:
            self.conn.search('*:*', index='test-index', es_from=1, size=1)

        send_request.assert_called_once_with(
            'GET',
            ['test-index', '', '_search'],
            '',
            query_params={'q': '*:*', 'from': 1, 'size': 1})

    def test_search_by_dsl(self):
        self.conn.index('test-index', 'test-type', {'name': 'AgeJoe Tester', 'age': 25}, id=1)
        self.conn.index('test-index', 'test-type', {'name': 'AgeBill Baloney', 'age': 35}, id=2)
        self.conn.refresh(['test-index'])

        query = {'query': {
                    'filtered': {
                        'query': {
                            'query_string': {'query': 'name:baloney'}
                        },
                        'filter': {
                            'range': {
                                'age': {
                                    'from': 27,
                                    'to': 37,
                                },
                            },
                        },
                    },
                },
            }
        result = self.conn.search(query, index=['test-index'], doc_type=['test-type'])
        ok_(result.get('hits').get('hits').__len__() > 0, str(result))

    def test_mlt(self):
        self.conn.index('test-index', 'test-type', {'name': 'Joe Test'}, id=3)
        self.conn.refresh(['test-index'])
        result = self.conn.more_like_this('test-index', 'test-type', 1, ['name'], min_term_freq=1, min_doc_freq=1)
        self.assert_result_contains(result, {'hits': {'hits': [{'_score': 0.19178301, '_type': 'test-type', '_id': '3', '_source': {'name': 'Joe Test'}, '_index': 'test-index'}], 'total': 1, 'max_score': 0.19178301}})

    def test_mlt_with_body(self):
        self.conn.index('test-index', 'test-type', {'name': 'Joe Test', 'age': 22}, id=2)
        self.conn.index('test-index', 'test-type', {'name': 'Joe Justin', 'age': 16}, id=3)
        self.conn.refresh(['test-index'])

        body = {'filter': {
                    'fquery': {
                        'query': {
                            'range': {
                                'age': {
                                    'from': 10,
                                    'to': 20
                                },
                            },
                        }
                    }
                }
            }
        result = self.conn.more_like_this('test-index', 'test-type', 1, ['name'], body=body, min_term_freq=1, min_doc_freq=1)
        self.assert_result_contains(result,
                {'hits': {'hits': [{'_score': 0.19178301, '_type': 'test-type', '_id': '3', '_source': {'age': 16, 'name': 'Joe Justin'}, '_index': 'test-index'}], 'total': 1, 'max_score': 0.19178301}})

    def test_mlt_fields(self):
        self.conn.index('test-index', 'test-type', {'name': 'Angus', 'sport': 'football'}, id=3)
        self.conn.index('test-index', 'test-type', {'name': 'Cam', 'sport': 'football'}, id=4)
        self.conn.index('test-index', 'test-type', {'name': 'Sophia', 'sport': 'baseball'}, id=5)

        self.conn.refresh(['test-index'])

        result = self.conn.more_like_this('test-index', 'test-type', 3, ['sport'], min_term_freq=1, min_doc_freq=1)
        self.assert_result_contains(result,
                {u'hits': {u'hits': [{u'_score': 0.30685282, u'_type': u'test-type', u'_id': u'4', u'_source': {u'sport': u'football', u'name': u'Cam'}, u'_index': u'test-index'}], u'total': 1, u'max_score': 0.30685282}})


class DangerousOperationTests(ElasticSearchTestCase):
    """
    Tests that confirm callers can't do dangerous operations by accident and
    that the substitute routines work
    """
    def test_delete_all(self):
        """Make sure ``delete_all()`` sends the right request."""
        with patch.object(self.conn, 'send_request') as send_request:
            self.conn.delete_all('test-index', 'tweet')
        send_request.assert_called_once_with(
            'DELETE',
            ['test-index', 'tweet'],
            query_params={})

    def delete_index_no_args(self):
        """
        ``delete_index()`` should raise ValueError if no indexes are given.
        """
        assert_raises(ValueError, self.conn.delete_index, [])

    def test_delete_all_indexes(self):
        """Make sure ``delete_all_indexes()`` sends the right request."""
        with patch.object(self.conn, 'send_request') as send_request:
            self.conn.delete_all_indexes()
        send_request.assert_called_once_with('DELETE', [''], query_params={})

    def update_settings_no_args(self):
        """
        ``update_settings()`` should refuse to update *all* indexes when none
        are given.
        """
        assert_raises(ValueError, self.conn.update_settings, [], {'b': 4})

    def update_all_settings(self):
        """Make sure ``update_all_settings()`` sends the right request."""
        with patch.object(self.conn, 'send_request') as send_request:
            self.conn.update_all_settings({'joe': 'bob'})
        send_request.assert_called_once_with(
            'PUT', ['_settings'], body={'joe': 'bob'})
