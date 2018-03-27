"""
Unit tests for pyelasticsearch

These require a local elasticsearch server running on the default port
(localhost:9200).
"""
from time import sleep
from unittest import TestCase, SkipTest

from six.moves import xrange

# Test that __all__ is sufficient:
from pyelasticsearch import *


class ElasticSearchTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        """When loading the test package, wait for ES to come up."""
        cls.conn = ElasticSearch()

        try:
            cls.conn.health(wait_for_status='yellow', timeout=10)
        except ConnectionError:
            raise SkipTest('Could not connect to the ES server.')

    def tearDown(self):
        try:
            self.conn.delete_index('test-index')
        except Exception:
            pass

    def assert_result_contains(self, result, expected):
        for (key, value) in expected.items():
            self.assertEqual(value, result[key])
        return True
