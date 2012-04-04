# -*- coding: utf-8 -*-
"""
Unit tests for pyelasticsearch.  These require an elasticsearch server running on the default port (localhost:9200).
"""
import datetime
import logging
import unittest
from pyelasticsearch import ElasticSearch, ElasticSearchError


class VerboseElasticSearch(ElasticSearch):
     def setup_logging(self):
         log = super(VerboseElasticSearch, self).setup_logging()
         log.setLevel(logging.DEBUG)
         return log


class ElasticSearchTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = ElasticSearch('http://localhost:9200/')

    def tearDown(self):
        try:
            self.conn.delete_index("test-index")
        except:
            pass

    def assertResultContains(self, result, expected):
        for (key, value) in expected.items():
            self.assertEquals(value, result[key])


class IndexingTestCase(ElasticSearchTestCase):
    def testSetupLogging(self):
        log = self.conn.setup_logging()
        self.assertTrue(isinstance(log, logging.Logger))
        self.assertEqual(log.level, logging.ERROR)

    def testOverriddenSetupLogging(self):
        conn = VerboseElasticSearch('http://localhost:9200/')
        log = conn.setup_logging()
        self.assertTrue(isinstance(log, logging.Logger))
        self.assertEqual(log.level, logging.DEBUG)

    def testIndexingWithID(self):
        result = self.conn.index({"name":"Joe Tester"}, "test-index", "test-type", 1)
        self.assertResultContains(result, {'_type': 'test-type', '_id': '1', 'ok': True, '_index': 'test-index'} )

    def testIndexingWithoutID(self):
        result = self.conn.index({"name":"Joe Tester"}, "test-index", "test-type")
        self.assertResultContains(result, {'_type': 'test-type', 'ok': True, '_index': 'test-index'} )
        # should have an id of some value assigned.
        self.assertTrue(result.has_key('_id') and result['_id'])

    def testExplicitIndexCreate(self):
        result = self.conn.create_index("test-index")
        self.assertResultContains(result, {'acknowledged': True, 'ok': True})

    def testDeleteByID(self):
        self.conn.index({"name":"Joe Tester"}, "test-index", "test-type", 1)
        self.conn.refresh(["test-index"])
        result = self.conn.delete("test-index", "test-type", 1)
        self.assertResultContains(result, {'_type': 'test-type', '_id': '1', 'ok': True, '_index': 'test-index'})

    def testDeleteByDocType(self):
        self.conn.index({"name":"Joe Tester"}, "test-index", "test-type", 1)
        self.conn.refresh(["test-index"])
        result = self.conn.delete("test-index", "test-type")
        self.assertResultContains(result, {'ok': True})

    def testDeleteByQuery(self):
        self.conn.index({"name":"Joe Tester"}, "test-index", "test-type", 1)
        self.conn.index({"name":"Bill Baloney"}, "test-index", "test-type", 2)
        self.conn.index({"name":"Horace Humdinger"}, "test-index", "test-type", 3)
        self.conn.refresh(["test-index"])

        self.conn.refresh(["test-index"])
        result = self.conn.count("*:*", indexes=['test-index'])
        self.assertResultContains(result, {'count': 3})

        result = self.conn.delete_by_query("test-index", "test-type", {"query_string": {"query": "name:joe OR name:bill"}})
        self.assertResultContains(result, {'ok': True})

        self.conn.refresh(["test-index"])
        result = self.conn.count("*:*", indexes=['test-index'])
        self.assertResultContains(result, {'count': 1})

    def testDeleteIndex(self):
        self.conn.create_index("another-index")
        result = self.conn.delete_index("another-index")
        self.assertResultContains(result, {'acknowledged': True, 'ok': True})

    def testCannotCreateExistingIndex(self):
        self.conn.create_index("another-index")
        result = self.conn.create_index("another-index")
        self.conn.delete_index("another-index")
        self.assertEqual(result, {'message': "Create index 'another-index' errored: Non-OK status code returned (400) containing 'IndexAlreadyExistsException[[another-index] Already exists]'."})
        self.assertRaises(ElasticSearchError, self.conn.delete_index, "another-index", quiet=False)

    def testPutMapping(self):
        result = self.conn.create_index("test-index")
        result = self.conn.put_mapping("test-type", {"test-type" : {"properties" : {"name" : {"type" : "string", "store" : "yes"}}}}, indexes=["test-index"])
        self.assertResultContains(result, {'acknowledged': True, 'ok': True})

    def testGettMapping(self):
        result = self.conn.create_index("test-index")
        mapping = {"test-type" : {"properties" : {"name" : {"type" : "string", "store" : "yes"}}}}
        self.conn.put_mapping("test-type", mapping, indexes=["test-index"])

        result = self.conn.get_mapping(indexes=["test-index"], doc_types=["test-type"])
        self.assertEqual(result, mapping)

    def testIndexStatus(self):
        self.conn.create_index("another-index")
        result = self.conn.status(["another-index"])
        self.conn.delete_index("another-index")
        self.assertTrue(result.has_key('indices'))
        self.assertResultContains(result, {'ok': True})

    def testIndexFlush(self):
        self.conn.create_index("another-index")
        result = self.conn.flush(["another-index"])
        self.conn.delete_index("another-index")
        self.assertResultContains(result, {'ok': True})

    def testIndexRefresh(self):
        self.conn.create_index("another-index")
        result = self.conn.refresh(["another-index"])
        self.conn.delete_index("another-index")
        self.assertResultContains(result, {'ok': True})

    def testIndexOptimize(self):
        self.conn.create_index("another-index")
        result = self.conn.optimize(["another-index"])
        self.conn.delete_index("another-index")
        self.assertResultContains(result, {'ok': True})

    def testFromPython(self):
        self.assertEqual(self.conn.from_python('abc'), u'abc')
        self.assertEqual(self.conn.from_python(u'☃'), u'☃')
        self.assertEqual(self.conn.from_python(123), 123)
        self.assertEqual(self.conn.from_python(12.2), 12.2)
        self.assertEqual(self.conn.from_python(True), True)
        self.assertEqual(self.conn.from_python(False), False)
        self.assertEqual(self.conn.from_python(datetime.date(2011, 12, 30)), '2011-12-30T00:00:00')
        self.assertEqual(self.conn.from_python(datetime.datetime(2011, 12, 30, 11, 59, 32)), '2011-12-30T11:59:32')
        self.assertEqual(self.conn.from_python([1, 2, 3]), [1, 2, 3])
        self.assertEqual(self.conn.from_python(set(['a', 'b', 'c'])), set(['a', 'b', 'c']))
        self.assertEqual(self.conn.from_python({'a': 1, 'b': 3, 'c': 2}), {'a': 1, 'b': 3, 'c': 2})

    def testToPython(self):
        self.assertEqual(self.conn.to_python(u'abc'), u'abc')
        self.assertEqual(self.conn.to_python(u'☃'), u'☃')
        self.assertEqual(self.conn.to_python(123), 123)
        self.assertEqual(self.conn.to_python(12.2), 12.2)
        self.assertEqual(self.conn.to_python(True), True)
        self.assertEqual(self.conn.to_python(False), False)
        self.assertEqual(self.conn.to_python('2011-12-30T00:00:00'), datetime.datetime(2011, 12, 30))
        self.assertEqual(self.conn.to_python('2011-12-30T11:59:32'), datetime.datetime(2011, 12, 30, 11, 59, 32))
        self.assertEqual(self.conn.to_python([1, 2, 3]), [1, 2, 3])
        self.assertEqual(self.conn.to_python(set(['a', 'b', 'c'])), set(['a', 'b', 'c']))
        self.assertEqual(self.conn.to_python({'a': 1, 'b': 3, 'c': 2}), {'a': 1, 'b': 3, 'c': 2})

    def testBulkIndex(self):
        self.assertRaises(ElasticSearchError, self.conn.count, "*:*", indexes=['test-index'])
        docs = [
            {"name":"Joe Tester"},
            {"name":"Bill Baloney", "id": 303},
        ]
        result = self.conn.bulk_index("test-index", "test-type", docs)
        self.assertEqual(len(result['items']), 2)
        self.assertEqual(result['items'][0]['create']['ok'], True)
        self.assertEqual(result['items'][1]['index']['ok'], True)
        self.assertEqual(result['items'][1]['index']['_id'], '303')
        self.conn.refresh()
        self.assertEqual(self.conn.count("*:*", indexes=['test-index'])['count'], 2)

    def testErrorHandling(self):
        # Wrong port.
        conn = ElasticSearch('http://example.com:1009200/')
        self.assertRaises(ElasticSearchError, conn.count, "*:*")

        # Test invalid JSON.
        self.assertRaises(ElasticSearchError, conn._prep_request, unittest.TestCase)
        self.assertRaises(ElasticSearchError, conn._prep_response, '{"busted" "json" "that": ["is] " wrong')


class SearchTestCase(ElasticSearchTestCase):
    def setUp(self):
        super(SearchTestCase, self).setUp()
        self.conn.index({"name":"Joe Tester"}, "test-index", "test-type", 1)
        self.conn.index({"name":"Bill Baloney"}, "test-index", "test-type", 2)
        self.conn.refresh(["test-index"])

    def testGetByID(self):
        result = self.conn.get("test-index", "test-type", 1)
        self.assertResultContains(result, {'_type': 'test-type', '_id': '1', '_source': {'name': 'Joe Tester'}, '_index': 'test-index'})

    def testGetCountBySearch(self):
        result = self.conn.count("name:joe")
        self.assertResultContains(result, {'count': 1})

    def testSearchByField(self):
        result = self.conn.search("name:joe")
        self.assertResultContains(result, {'hits': {'hits': [{'_score': 0.19178301, '_type': 'test-type', '_id': '1', '_source': {'name': 'Joe Tester'}, '_index': 'test-index'}], 'total': 1, 'max_score': 0.19178301}})

    def testSearchByDSL(self):
        import simplejson as json
        self.conn.index({"name":"AgeJoe Tester", "age":25}, "test-index", "test-type", 1)
        self.conn.index({"name":"AgeBill Baloney", "age":35}, "test-index", "test-type", 2)
        self.conn.refresh(["test-index"])

        query = {   "query": { 
                        "query_string": { "query": "name:age" }, 
                        "filtered": {
                            "filter": {
                                "range": {
                                    "age": {
                                        "from": 27,
                                        "to": 37,
                                    },
                                },
                            },
                        },
                    },
                }

        result = self.conn.search("", body=json.dumps(query), indexes=['test-index'], doc_types=['test-type'])
        self.assertTrue(result.get('hits').get('hits').__len__() > 0, str(result))

    def testMLT(self):
        self.conn.index({"name":"Joe Test"}, "test-index", "test-type", 3)
        self.conn.refresh(["test-index"])
        result = self.conn.morelikethis("test-index", "test-type", 1, ['name'], min_term_freq=1, min_doc_freq=1)
        self.assertResultContains(result, {'hits': {'hits': [{'_score': 0.19178301,'_type': 'test-type', '_id': '3', '_source': {'name': 'Joe Test'}, '_index': 'test-index'}], 'total': 1, 'max_score': 0.19178301}})


if __name__ == "__main__":
    unittest.main()
