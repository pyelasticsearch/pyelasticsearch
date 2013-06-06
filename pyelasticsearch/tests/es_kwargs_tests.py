from datetime import datetime, date
import unittest

from mock import patch
from nose import SkipTest
from nose.tools import eq_, ok_, assert_raises
import requests
import six

# Test that __all__ is sufficient:
from pyelasticsearch import *
from pyelasticsearch.client import es_kwargs


class KwargsForQueryTests(unittest.TestCase):
    """Tests for the ``es_kwargs`` decorator and such"""

    def test_to_query(self):
        """Test the thing that translates objects to query string text."""
        to_query = ElasticSearch([])._to_query
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
