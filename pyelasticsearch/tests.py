# -*- coding: utf-8 -*-
"""
Unit tests for pyelasticsearch.  These require an elasticsearch server running on the default port (localhost:9200).
"""
import sys
from datetime import datetime, date
from decimal import Decimal
import unittest

from mock import patch
from nose import SkipTest
from nose.tools import eq_, ok_, assert_raises, assert_not_equal
import requests
import six

# Test that __all__ is sufficient:
from pyelasticsearch import *
from pyelasticsearch.client import es_kwargs


def arbitrary_response():
    response = requests.Response()
    response._content = six.b('{"some": "json"}')
    response.status_code = 200
    return response


class ElasticSearchTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = ElasticSearch('http://localhost:9200/')

    def tearDown(self):
        try:
            self.conn.delete_index('test-index')
        except Exception:
            pass

    def assert_result_contains(self, result, expected):
        for (key, value) in expected.items():
            eq_(value, result[key])


class IndexingTestCase(ElasticSearchTestCase):
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


class DowntimePoolingTests(unittest.TestCase):
    """Tests for failover, pooling, and auto-retry"""

    def test_retry(self):
        """Make sure auto-retry works at least a little."""
        first_url = []  # a mutable just so we can close over and write to it

        def get_but_fail_the_first_time(url, **kwargs):
            """
            Raise ConnectionError for the first URL passed, but return a
            plausible response for later ones.
            """
            # Monkeypatching random instead would have made too many
            # assumptions about the code under test.
            if first_url and url not in first_url:
                return arbitrary_response()
            first_url.append(url)
            raise ConnectionError

        conn = ElasticSearch(['http://one.example.com:9200/',
                              'http://two.example.com:9200/'],
                             max_retries=1)

        with patch.object(conn.session, 'get') as session_get:
            session_get.side_effect = get_but_fail_the_first_time
            # Try to request something with max_retries=1. This should make 2
            # calls to session.get():
            conn.get('test-index', 'test-type', 7)

        # Assert that one server was tried and then the other.
        eq_(session_get.call_count, 2)
        calls = session_get.call_args_list
        down_server = calls[0][0]
        assert_not_equal(calls[1][0], down_server)

        # Assert there's one item in the live pool and one in the dead.
        # That oughta cover a fair amount.
        eq_(len(conn.servers.live), 1)
        eq_(len(conn.servers.dead), 1)

    def test_death_and_rebirth(self):
        """
        If a server fails, mark it dead. If there are no remaining live
        servers, start trying dead ones. If a dead one starts working, bring it
        back to life.

        This is kind of an exploratory,
        test-as-much-as-you-can-for-the-least-effort test.
        """
        conn = ElasticSearch(['http://one.example.com:9200/',
                              'http://two.example.com:9200/'],
                             max_retries=0)

        with patch.object(conn.session, 'get') as session_get:
            session_get.side_effect = Timeout

            # This should kill off both servers:
            for x in range(2):
                try:
                    conn.get('test-index', 'test-type', 7)
                except Timeout:
                    pass

            # Make sure the pools are as we expect:
            eq_(len(conn.servers.dead), 2)
            eq_(len(conn.servers.live), 0)

            # And this should use a dead server, though the request will still
            # time out:
            try:
                conn.get('test-index', 'test-type', 7)
            except Timeout:
                pass
            else:
                raise AssertionError('That should have timed out.')

        with patch.object(conn.session, 'get') as session_get:
            session_get.return_value = arbitrary_response()

            # Then we try another dead server, but this time it works:
            conn.get('test-index', 'test-type', 7)

            # Then that server should have come back to life:
            eq_(len(conn.servers.dead), 1)
            eq_(len(conn.servers.live), 1)


class KwargsForQueryTests(unittest.TestCase):
    """Tests for the ``es_kwargs`` decorator and such"""

    def test_to_query(self):
        """Test the thing that translates objects to query string text."""
        to_query = ElasticSearch._to_query
        eq_(to_query(4), '4')
        eq_(to_query(4.5), '4.5')
        eq_(to_query(True), 'true')
        eq_(to_query(('4', 'hi', 'thomas')), '4,hi,thomas')
        eq_(to_query(datetime(2000, 1, 2, 12, 34, 56)),
                         '2000-01-02T12:34:56')
        eq_(to_query(date(2000, 1, 2)),
                         '2000-01-02T00:00:00')
        assert_raises(TypeError, to_query, object())

        # do not use unittest.skipIf because of python 2.6
        if not six.PY3:
            eq_(to_query(long(4)), '4')


    def test_es_kwargs(self):
        """
        Make sure ``es_kwargs`` bundles es_ and specifically called out kwargs
        into the ``query_params`` map and leaves other args and kwargs alone.
        """
        @es_kwargs('refresh', 'es_timeout')
        def index(doc, query_params=None, other_kwarg=None):
            """
        Hi

        :arg some_arg: Here just so es_kwargs doesn't crash
        """
            return doc, query_params, other_kwarg

        eq_(index(3, refresh=True, es_timeout=7, other_kwarg=1),
                         (3, {'refresh': True, 'timeout': 7}, 1))
        eq_(index.__name__, 'index')

    def test_index(self):
        """Integration-test ``index()`` with some decorator-handled arg."""
        def valid_responder(*args, **kwargs):
            """Return an arbitrary successful Response."""
            response = requests.Response()
            response._content = six.b('{"some": "json"}')
            response.status_code = 200
            return response

        conn = ElasticSearch('http://example.com:9200/')
        with patch.object(conn.session, 'put') as put:
            put.side_effect = valid_responder
            conn.index('some_index',
                       'some_type',
                       {'some': 'doc'},
                       id=3,
                       routing='boogie',
                       es_snorkfest=True,
                       es_borkfest='gerbils:great')

        # Make sure all the query string params got into the URL:
        url = put.call_args[0][0]
        ok_(
            url.startswith('http://example.com:9200/some_index/some_type/3?'))
        ok_('routing=boogie' in url)
        ok_('snorkfest=true' in url)
        ok_('borkfest=gerbils%3Agreat' in url)
        ok_('es_' not in url)  # We stripped the "es_" prefixes.

    def test_arg_cross_refs_with_trailing(self):
        """
        Make sure ``es_kwargs`` adds "see ES docs" cross references for any
        es_kwargs args not already documented in the decorated method's
        docstring, in cases where there is trailing material after the arg
        list.
        """
        @es_kwargs('gobble', 'degook')
        def some_method(foo, bar, query_params=None):
            """
        Do stuff.

        :arg degook: Whether to remove the gook

        It's neat.
        """

        if some_method.__doc__ is None:
            raise SkipTest("This test doesn't work under python -OO.")

        # Make sure it adds (only) the undocumented args and preserves anything
        # that comes after the args block:
        eq_(
            some_method.__doc__,
            """
        Do stuff.

        :arg degook: Whether to remove the gook
        :arg gobble: See the ES docs.

        It's neat.
        """)

    def test_arg_cross_refs_with_eof(self):
        """
        Make sure ``es_kwargs`` adds "see ES docs" cross references for any
        es_kwargs args not already documented in the decorated method's
        docstring, in cases where the docstring ends after the arg list.
        """
        @es_kwargs('gobble', 'degook')
        def some_method(foo, bar, query_params=None):
            """
        Do stuff.

        :arg degook: Whether to remove the gook
        """

        if some_method.__doc__ is None:
            raise SkipTest("This test doesn't work under python -OO.")

        eq_(
            some_method.__doc__,
            """
        Do stuff.

        :arg degook: Whether to remove the gook
        :arg gobble: See the ES docs.
        """)


class JsonTests(ElasticSearchTestCase):
    """Tests for JSON encoding and decoding"""

    def test_decimal_encoding(self):
        """Make sure we can encode ``Decimal`` objects and that they don't end
        up with quotes around them, which would suggest to ES to represent them
        as strings if inferring a mapping."""
        ones = '1.111111111111111111'
        eq_(self.conn._encode_json({'hi': Decimal(ones)}),
                         '{"hi": %s}' % ones)

    def test_set_encoding(self):
        """Make sure encountering a set doesn't raise a circular reference
        error."""
        eq_(self.conn._encode_json({'hi': set([1])}),
                         '{"hi": [1]}')

    def test_tuple_encoding(self):
        """Make sure tuples encode as lists."""
        eq_(self.conn._encode_json({'hi': (1, 2, 3)}),
                         '{"hi": [1, 2, 3]}')

    def test_unhandled_encoding(self):
        """Make sure we raise a TypeError when encoding an unsupported type."""
        assert_raises(TypeError, self.conn._encode_json, object())

    def test_encoding(self):
        """Test encoding a zillion other types."""
        eq_(self.conn._encode_json('abc'), u'"abc"')
        eq_(self.conn._encode_json(u'☃'), r'"\u2603"')
        eq_(self.conn._encode_json(123), '123')
        eq_(self.conn._encode_json(12.25), '12.25')
        eq_(self.conn._encode_json(True), 'true')
        eq_(self.conn._encode_json(False), 'false')
        eq_(self.conn._encode_json(
            date(2011, 12, 30)),
            '"2011-12-30T00:00:00"')
        eq_(self.conn._encode_json(
            datetime(2011, 12, 30, 11, 59, 32)),
            '"2011-12-30T11:59:32"')
        eq_(self.conn._encode_json([1, 2, 3]), '[1, 2, 3]')
        eq_(self.conn._encode_json({'a': 1}), '{"a": 1}')


if __name__ == '__main__':
    unittest.main()
