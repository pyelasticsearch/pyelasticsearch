import unittest

from mock import patch
from nose.tools import eq_, assert_not_equal
import requests
import six

# Test that __all__ is sufficient:
from pyelasticsearch import *


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


def arbitrary_response():
    response = requests.Response()
    response._content = six.b('{"some": "json"}')
    response.status_code = 200
    return response
