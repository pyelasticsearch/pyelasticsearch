from unittest import TestCase

from six.moves import xrange

from pyelasticsearch import bulk_chunks


class BulkChunksTests(TestCase):
    """Tests for bulk_chunks()"""

    @staticmethod
    def str_xrange(top):
        return (str(x) for x in xrange(top))

    def test_under(self):
        """Make sure action iterators shorter than 1 chunk work."""
        actions = self.str_xrange(1)  # just 0
        chunks = bulk_chunks(actions, docs_per_chunk=2)
        self.assertEqual(list(chunks), [['0']])

    def test_over(self):
        """Make sure action iterators longer than 1 chunk work."""
        actions = self.str_xrange(7)
        chunks = bulk_chunks(actions, docs_per_chunk=3)
        self.assertEqual(list(chunks), [['0', '1', '2'], ['3', '4', '5'], ['6']])

    def test_on(self):
        """Make sure action iterators that end on a chunk boundary work."""
        actions = self.str_xrange(4)
        chunks = bulk_chunks(actions, docs_per_chunk=2)
        self.assertEqual(list(chunks), [['0', '1'], ['2', '3']])

    def test_none(self):
        """Make sure empty action iterators work."""
        actions = self.str_xrange(0)
        chunks = bulk_chunks(actions, docs_per_chunk=2)
        self.assertEqual(list(chunks), [])

    def test_bytes(self):
        """
        Make sure byte-based limits work.

        The last document is not allowed to overshoot the limit.
        """
        actions = ['o', 'hi', 'good', 'chimpanzees']
        chunks = bulk_chunks(actions, bytes_per_chunk=5)
        self.assertEqual(list(chunks), [['o', 'hi'], ['good'], ['chimpanzees']])

    def test_bytes_first_too_big(self):
        """
        Don't yield an empty chunk if the first item is over the byte limit on
        its own.
        """
        actions = ['chimpanzees', 'hi', 'ho']
        chunks = bulk_chunks(actions, bytes_per_chunk=6)
        self.assertEqual(list(chunks), [['chimpanzees'], ['hi', 'ho']])
