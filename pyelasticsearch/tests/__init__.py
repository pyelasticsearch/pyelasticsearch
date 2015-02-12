"""
Unit tests for pyelasticsearch

These require a local elasticsearch server running on the default port
(localhost:9200).
"""
from time import sleep
from unittest import TestCase

from nose import SkipTest
from nose.tools import eq_
from six.moves import xrange

# Test that __all__ is sufficient:
from pyelasticsearch import *


def setUp():
    """When loading the test package, wait for ES to come up."""
    for _ in xrange(200):
        try:
            ElasticSearch().health(wait_for_status='yellow')
            return
        except ConnectionError:
            sleep(.1)
    raise SkipTest('Could not connect to the ES server.')


class ElasticSearchTestCase(TestCase):
    def setUp(self):
        self.conn = ElasticSearch()

    def tearDown(self):
        try:
            self.conn.delete_index('test-index')
        except Exception:
            pass

    def assert_result_contains(self, result, expected):
        for (key, value) in expected.items():
            eq_(value, result[key])
        return True
