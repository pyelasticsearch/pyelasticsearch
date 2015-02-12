"""
Unit tests for pyelasticsearch

These require an elasticsearch server running on the default port
(localhost:9200).
"""
import unittest

from nose.tools import eq_

# Test that __all__ is sufficient:
from pyelasticsearch import *


class ElasticSearchTestCase(unittest.TestCase):
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
