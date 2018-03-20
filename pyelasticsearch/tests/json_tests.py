# -*- coding: utf-8 -*-
from datetime import datetime, date
from decimal import Decimal

from pyelasticsearch.tests import ElasticSearchTestCase


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

    def test_unhandled_encoding(self):
        """Make sure we raise a TypeError when encoding an unsupported type."""
        with self.assertRaises(TypeError):
            self.conn._encode_json(object())

    def test_encoding(self):
        """Test encoding a zillion other types."""
        self.assertEqual(self.conn._encode_json('abc'), u'"abc"')
        self.assertEqual(self.conn._encode_json(u'☃'), r'"\u2603"')
        self.assertEqual(self.conn._encode_json(123), '123')
        self.assertEqual(self.conn._encode_json(12.25), '12.25')
        self.assertEqual(self.conn._encode_json(True), 'true')
        self.assertEqual(self.conn._encode_json(False), 'false')
        self.assertEqual(self.conn._encode_json(
            date(2011, 12, 30)),
            '"2011-12-30T00:00:00"')
        self.assertEqual(self.conn._encode_json(
            datetime(2011, 12, 30, 11, 59, 32)),
            '"2011-12-30T11:59:32"')
        self.assertEqual(self.conn._encode_json([1, 2, 3]), '[1, 2, 3]')
        self.assertEqual(self.conn._encode_json({'a': 1}), '{"a": 1}')
