# -*- coding: utf-8 -*-
"""
Unit tests for pyelasticsearch.  These require an elasticsearch server running on the default port (localhost:9200).
"""
from datetime import datetime, date
from decimal import Decimal
import unittest

from mock import patch
import requests

# Test that __all__ is sufficient:
from pyelasticsearch import *
from pyelasticsearch.client import es_kwargs


def arbitrary_response():
    response = requests.Response()
    response._content = '{"some": "json"}'
    return response


class ElasticSearchTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = ElasticSearch('http://localhost:9200/')

    def tearDown(self):
        try:
            self.conn.delete_index('test-index')
        except Exception:
            pass

    def assertResultContains(self, result, expected):
        for (key, value) in expected.items():
            self.assertEquals(value, result[key])


class IndexingTestCase(ElasticSearchTestCase):
    def testIndexingWithID(self):
        result = self.conn.index('test-index', 'test-type', {'name': 'Joe Tester'}, id=1)
        self.assertResultContains(result, {'_type': 'test-type', '_id': '1', 'ok': True, '_index': 'test-index'})

    def testQuotedCharsInID(self):
        result = self.conn.index('test-index', 'test-type', {'name': 'Joe Tester'}, id="""<>?,./`~!@#$%^&*()_+=[]\{{}|:";'""")
        self.assertResultContains(result, {'_type': 'test-type', '_id': """<>?,./`~!@#$%^&*()_+=[]\{{}|:";'""", 'ok': True, '_index': 'test-index'})

    def testIndexingWithoutID(self):
        result = self.conn.index('test-index', 'test-type', {'name': 'Joe Tester'})
        self.assertResultContains(result, {'_type': 'test-type', 'ok': True, '_index': 'test-index'})
        # should have an id of some value assigned.
        self.assertTrue('_id' in result and result['_id'])

    def testExplicitIndexCreate(self):
        result = self.conn.create_index('test-index')
        self.assertResultContains(result, {'acknowledged': True, 'ok': True})

    def testCloseIndex(self):
        """Make sure a close_index call on an open index reports success."""
        self.conn.create_index('test-index')
        result = self.conn.close_index('test-index')
        self.assertResultContains(result, {'acknowledged': True, 'ok': True})

    def testOpenIndex(self):
        """Make sure an open_index call on a closed index reports success."""
        self.conn.create_index('test-index')
        self.conn.close_index('test-index')
        result = self.conn.open_index('test-index')
        self.assertResultContains(result, {'acknowledged': True, 'ok': True})

    def testGetSettings(self):
        self.conn.create_index('test-index')
        result = self.conn.get_settings('test-index')
        self.assertTrue('test-index'in result)
        self.assertTrue('settings' in result['test-index'])

    def testUpdateSettings(self):
        """Make sure ``update_settings()`` sends the expected request."""
        with patch.object(self.conn, 'send_request') as send_request:
            self.conn.update_settings(['test-index', 'toast-index'],
                                      {'index': {'number_of_replicas': 2}})
        send_request.assert_called_once_with(
            'PUT',
            ['test-index,toast-index', '_settings'],
            body={'index': {'number_of_replicas': 2}},
            query_params={})

    def testHealth(self):
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

    def testDeleteByID(self):
        self.conn.index('test-index', 'test-type', {'name': 'Joe Tester'}, id=1)
        self.conn.refresh(['test-index'])
        result = self.conn.delete('test-index', 'test-type', 1)
        self.assertResultContains(result, {'_type': 'test-type', '_id': '1', 'ok': True, '_index': 'test-index'})

    def testDeleteByDocType(self):
        self.conn.index('test-index', 'test-type', {'name': 'Joe Tester'}, id=1)
        self.conn.refresh(["test-index"])
        result = self.conn.delete_all("test-index", "test-type")
        self.assertResultContains(result, {'ok': True})

    def testDeleteByQuery(self):
        self.conn.index('test-index', 'test-type', {'name': 'Joe Tester'}, id=1)
        self.conn.index('test-index', 'test-type', {'name': 'Bill Baloney'}, id=2)
        self.conn.index('test-index', 'test-type', {'name': 'Horace Humdinger'}, id=3)
        self.conn.refresh(['test-index'])

        self.conn.refresh(['test-index'])
        result = self.conn.count('*:*', index=['test-index'])
        self.assertResultContains(result, {'count': 3})

        result = self.conn.delete_by_query('test-index', 'test-type', {'query_string': {'query': 'name:joe OR name:bill'}})
        self.assertResultContains(result, {'ok': True})

        self.conn.refresh(['test-index'])
        result = self.conn.count('*:*', index=['test-index'])
        self.assertResultContains(result, {'count': 1})

    def testDeleteIndex(self):
        self.conn.create_index('another-index')
        result = self.conn.delete_index('another-index')
        self.assertResultContains(result, {'acknowledged': True, 'ok': True})

    def testDeleteNonexistentIndex(self):
        """
        Deleting a nonexistent index should raise ElasticHttpNotFoundError.
        """
        self.assertRaises(ElasticHttpNotFoundError,
                          self.conn.delete_index,
                          'nonexistent-index')

    def testCannotCreateExistingIndex(self):
        self.conn.create_index('another-index')
        self.assertRaises(ElasticHttpError, self.conn.create_index, 'another-index')
        self.conn.delete_index('another-index')
        self.assertRaises(ElasticHttpError, self.conn.delete_index, 'another-index')

    def testPutMapping(self):
        result = self.conn.create_index('test-index')
        result = self.conn.put_mapping('test-index', 'test-type', {'test-type': {'properties': {'name': {'type': 'string', 'store': 'yes'}}}})
        self.assertResultContains(result, {'acknowledged': True, 'ok': True})

    def testGetMapping(self):
        result = self.conn.create_index('test-index')
        mapping = {'test-type': {'properties': {'name': {'type': 'string', 'store': 'yes'}}}}
        self.conn.put_mapping('test-index', 'test-type', mapping)

        result = self.conn.get_mapping(index=['test-index'], doc_type=['test-type'])
        self.assertEqual(result, mapping)

    def testIndexStatus(self):
        self.conn.create_index('another-index')
        result = self.conn.status('another-index')
        self.conn.delete_index('another-index')
        self.assertTrue('indices' in result)
        self.assertResultContains(result, {'ok': True})

    def testIndexFlush(self):
        self.conn.create_index('another-index')
        result = self.conn.flush('another-index')
        self.conn.delete_index('another-index')
        self.assertResultContains(result, {'ok': True})

    def testIndexRefresh(self):
        self.conn.create_index('another-index')
        result = self.conn.refresh('another-index')
        self.conn.delete_index('another-index')
        self.assertResultContains(result, {'ok': True})

    def testIndexOptimize(self):
        self.conn.create_index('another-index')
        result = self.conn.optimize('another-index')
        self.conn.delete_index('another-index')
        self.assertResultContains(result, {'ok': True})

    def testBulkIndex(self):
        # Try counting the docs in a nonexistent index:
        self.assertRaises(ElasticHttpError, self.conn.count, '*:*', index=['test-index'])

        docs = [
            {'name': 'Joe Tester'},
            {'name': 'Bill Baloney', 'id': 303},
        ]
        result = self.conn.bulk_index('test-index', 'test-type', docs)
        self.assertEqual(len(result['items']), 2)
        self.assertEqual(result['items'][0]['create']['ok'], True)
        self.assertEqual(result['items'][1]['index']['ok'], True)
        self.assertEqual(result['items'][1]['index']['_id'], '303')
        self.conn.refresh()
        self.assertEqual(self.conn.count('*:*',
                                         index=['test-index'])['count'], 2)

    def testErrorHandling(self):
        # Wrong port.
        conn = ElasticSearch('http://example.com:1009200/')
        self.assertRaises(ConnectionError, conn.count, '*:*')

        # Test invalid JSON.
        self.assertRaises(ValueError, conn._encode_json, object())
        resp = requests.Response()
        resp._content = '{"busted" "json" "that": ["is] " wrong'
        self.assertRaises(InvalidJsonResponseError, conn._decode_response, resp)

    def testUpdate(self):
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
            'POST', ['some_index', 'some_type', 3],
            body={'script': SCRIPT,
                  'params': {'count': 5},
                  'lang': 'python'},
                  query_params={})


class SearchTestCase(ElasticSearchTestCase):
    def setUp(self):
        super(SearchTestCase, self).setUp()
        self.conn.index('test-index', 'test-type', {'name': 'Joe Tester'}, id=1)
        self.conn.index('test-index', 'test-type', {'name': 'Bill Baloney'}, id=2)
        self.conn.refresh(['test-index'])

    def testGetByID(self):
        result = self.conn.get('test-index', 'test-type', 1)
        self.assertResultContains(result, {'_type': 'test-type', '_id': '1', '_source': {'name': 'Joe Tester'}, '_index': 'test-index'})

    def testGetCountBySearch(self):
        result = self.conn.count('name:joe', index='test-index')
        self.assertResultContains(result, {'count': 1})

    def testSearchByField(self):
        result = self.conn.search('name:joe', index='test-index')
        self.assertResultContains(result, {'hits': {'hits': [{'_score': 0.19178301, '_type': 'test-type', '_id': '1', '_source': {'name': 'Joe Tester'}, '_index': 'test-index'}], 'total': 1, 'max_score': 0.19178301}})

    def testSearchByDSL(self):
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
        self.assertTrue(result.get('hits').get('hits').__len__() > 0, str(result))

    def testMLT(self):
        self.conn.index('test-index', 'test-type', {'name': 'Joe Test'}, id=3)
        self.conn.refresh(['test-index'])
        result = self.conn.more_like_this('test-index', 'test-type', 1, ['name'], min_term_freq=1, min_doc_freq=1)
        self.assertResultContains(result, {'hits': {'hits': [{'_score': 0.19178301, '_type': 'test-type', '_id': '3', '_source': {'name': 'Joe Test'}, '_index': 'test-index'}], 'total': 1, 'max_score': 0.19178301}})

    def testMLTWithBody(self):
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
        self.assertResultContains(result,
                {'hits': {'hits': [{'_score': 0.19178301, '_type': 'test-type', '_id': '3', '_source': {'age': 16, 'name': 'Joe Justin'}, '_index': 'test-index'}], 'total': 1, 'max_score': 0.19178301}})

    def testMLTFields(self):
        self.conn.index('test-index', 'test-type', {'name': 'Angus', 'sport': 'football'}, id=3)
        self.conn.index('test-index', 'test-type', {'name': 'Cam', 'sport': 'football'}, id=4)
        self.conn.index('test-index', 'test-type', {'name': 'Sophia', 'sport': 'baseball'}, id=5)

        self.conn.refresh(['test-index'])

        result = self.conn.more_like_this('test-index', 'test-type', 3, ['sport'], min_term_freq=1, min_doc_freq=1)
        self.assertResultContains(result,
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
        self.assertRaises(ValueError, self.conn.delete_index, [])

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
        self.assertRaises(ValueError, self.conn.update_settings, [], {'b': 4})

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
        self.assertEqual(session_get.call_count, 2)
        calls = session_get.call_args_list
        down_server = calls[0][0]
        self.assertNotEqual(calls[1][0], down_server)

        # Assert there's one item in the live pool and one in the dead.
        # That oughta cover a fair amount.
        self.assertEqual(len(conn.servers.live), 1)
        self.assertEqual(len(conn.servers.dead), 1)

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
            for x in xrange(2):
                try:
                    conn.get('test-index', 'test-type', 7)
                except Timeout:
                    pass

            # Make sure the pools are as we expect:
            self.assertEquals(len(conn.servers.dead), 2)
            self.assertEquals(len(conn.servers.live), 0)

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
            self.assertEquals(len(conn.servers.dead), 1)
            self.assertEquals(len(conn.servers.live), 1)


class KwargsForQueryTests(unittest.TestCase):
    """Tests for the ``es_kwargs`` decorator and such"""

    def test_to_query(self):
        """Test the thing that translates objects to query string text."""
        to_query = ElasticSearch._to_query
        self.assertEqual(to_query(4), '4')
        self.assertEqual(to_query(4L), '4')
        self.assertEqual(to_query(4.5), '4.5')
        self.assertEqual(to_query(True), 'true')
        self.assertEqual(to_query(('4', 'hi', 'thomas')), '4,hi,thomas')
        self.assertEqual(to_query(datetime(2000, 1, 2, 12, 34, 56)),
                         '2000-01-02T12:34:56')
        self.assertEqual(to_query(date(2000, 1, 2)),
                         '2000-01-02T00:00:00')
        self.assertRaises(TypeError, to_query, object())

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

        self.assertEqual(index(3, refresh=True, es_timeout=7, other_kwarg=1),
                         (3, {'refresh': True, 'timeout': 7}, 1))
        self.assertEqual(index.__name__, 'index')

    def test_index(self):
        """Integration-test ``index()`` with some decorator-handled arg."""
        def valid_responder(*args, **kwargs):
            """Return an arbitrary successful Response."""
            response = requests.Response()
            response._content = '{"some": "json"}'
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
        self.assertTrue(
            url.startswith('http://example.com:9200/some_index/some_type/3?'))
        self.assertTrue('routing=boogie' in url)
        self.assertTrue('snorkfest=true' in url)
        self.assertTrue('borkfest=gerbils%3Agreat' in url)
        self.assertTrue('es_' not in url)  # We stripped the "es_" prefixes.

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

        # Make sure it adds (only) the undocumented args and preserves anything
        # that comes after the args block:
        self.assertEqual(
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

        self.assertEqual(
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
        self.assertEqual(self.conn._encode_json({'hi': Decimal(ones)}),
                         '{"hi": %s}' % ones)

    def test_set_encoding(self):
        """Make sure encountering a set doesn't raise a circular reference
        error."""
        self.assertEqual(self.conn._encode_json({'hi': set([1])}),
                         '{"hi": [1]}')

    def test_tuple_encoding(self):
        """Make sure tuples encode as lists."""
        self.assertEqual(self.conn._encode_json({'hi': (1, 2, 3)}),
                         '{"hi": [1, 2, 3]}')

    def test_encoding(self):
        """Test encoding a zillion other types."""
        self.assertEqual(self.conn.from_python('abc'), u'abc')
        self.assertEqual(self.conn.from_python(u'☃'), u'☃')
        self.assertEqual(self.conn.from_python(123), 123)
        self.assertEqual(self.conn.from_python(12.2), 12.2)
        self.assertEqual(self.conn.from_python(True), True)
        self.assertEqual(self.conn.from_python(False), False)
        self.assertEqual(self.conn.from_python(date(2011, 12, 30)), '2011-12-30T00:00:00')
        self.assertEqual(self.conn.from_python(datetime(2011, 12, 30, 11, 59, 32)), '2011-12-30T11:59:32')
        self.assertEqual(self.conn.from_python([1, 2, 3]), [1, 2, 3])
        self.assertEqual(self.conn.from_python({'a': 1, 'b': 3, 'c': 2}), {'a': 1, 'b': 3, 'c': 2})

    def test_decoding(self):
        """Test decoding a bunch of types."""
        self.assertEqual(self.conn.to_python(u'abc'), u'abc')
        self.assertEqual(self.conn.to_python(u'☃'), u'☃')
        self.assertEqual(self.conn.to_python(123), 123)
        self.assertEqual(self.conn.to_python(12.2), 12.2)
        self.assertEqual(self.conn.to_python(True), True)
        self.assertEqual(self.conn.to_python(False), False)
        self.assertEqual(self.conn.to_python('2011-12-30T00:00:00'), datetime(2011, 12, 30))
        self.assertEqual(self.conn.to_python('2011-12-30T11:59:32'), datetime(2011, 12, 30, 11, 59, 32))
        self.assertEqual(self.conn.to_python([1, 2, 3]), [1, 2, 3])
        self.assertEqual(self.conn.to_python(set(['a', 'b', 'c'])), set(['a', 'b', 'c']))
        self.assertEqual(self.conn.to_python({'a': 1, 'b': 3, 'c': 2}), {'a': 1, 'b': 3, 'c': 2})


if __name__ == '__main__':
    unittest.main()
