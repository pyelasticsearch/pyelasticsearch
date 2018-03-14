from datetime import datetime, date
import unittest

from six import PY3, b

if PY3:
    from unittest.mock import patch
else:
    from mock import patch

# Test that __all__ is sufficient:
from pyelasticsearch import *
from pyelasticsearch.client import es_kwargs


class KwargsForQueryTests(unittest.TestCase):
    """Tests for the ``es_kwargs`` decorator and such"""

    def test_to_query(self):
        """Test the thing that translates objects to query string text."""
        to_query = ElasticSearch('http://localhost:9200/')._to_query
        self.assertEqual(to_query(4), '4')
        self.assertEqual(to_query(4.5), '4.5')
        self.assertEqual(to_query(True), 'true')
        self.assertEqual(to_query(('4', 'hi', 'thomas')), '4,hi,thomas')
        self.assertEqual(to_query(datetime(2000, 1, 2, 12, 34, 56)),
                         '2000-01-02T12:34:56')
        self.assertEqual(to_query(date(2000, 1, 2)),
                         '2000-01-02T00:00:00')
        with self.assertRaises(TypeError):
            to_query(object())

        # do not use unittest.skipIf because of python 2.6
        if not PY3:
            self.assertEqual(to_query(long(4)), '4')

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
            return 200, {'some': 'json'}

        conn = ElasticSearch('http://example.com:9200/')
        with patch.object(conn._transport, 'perform_request') as perform:
            perform.side_effect = valid_responder
            conn.index('some_index',
                       'some_type',
                       {'some': 'doc'},
                       id=3,
                       routing='boogie',
                       es_snorkfest=True,
                       es_borkfest='gerbils:great')

        ((_, url), kwargs) = perform.call_args

        self.assertEqual(url, '/some_index/some_type/3')

        # Make sure stringification happened, url encoding didn't, and es_
        # prefixes got stripped:
        self.assertEqual(kwargs['params'], {'routing': b('boogie'),
                                            'snorkfest': b('true'),  # We must do stringifying.
                                            'borkfest': b('gerbils:great')})  # Urllib3HttpConnection does url escaping.

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
            raise unittest.SkipTest("This test doesn't work under python -OO.")

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

        if some_method.__doc__ is None:
            raise unittest.SkipTest("This test doesn't work under python -OO.")

        self.assertEqual(
            some_method.__doc__,
            """
        Do stuff.

        :arg degook: Whether to remove the gook
        :arg gobble: See the ES docs.
        """)
