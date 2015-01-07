"""
Unit tests for pyelasticsearch

These require an elasticsearch server running on the default port
(localhost:9200).
"""
from functools import total_ordering
import unittest

from nose.tools import eq_

# Test that __all__ is sufficient:
from pyelasticsearch import *


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
        return True


@total_ordering
class EqualAnything(object):
    """Class for comparing favorably with everything"""
    def __eq__(self, other):
        return True

    def __lt__(self, other):
        return True


# The WHATEVER singleton is equal to everything. Use this for ignoring
# specific values which can fluctuate in results comparison tests.
WHATEVER = EqualAnything()


def eq_one_of(*tests):
    """Runs an iterable of test functions until one returns True

    Runs through an iterable of test functions executing each
    individually. If the function raises an error, then the error is
    ignored.

    If none of the test functions return True, then this raises an
    AssertionError.

    """
    for test_fun in tests:
        try:
            if test_fun():
                return True
        except Exception:
            pass
    else:
        raise AssertionError('None of %r is true' % (tests,))
