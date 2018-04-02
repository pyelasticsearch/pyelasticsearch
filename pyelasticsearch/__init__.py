from __future__ import absolute_import

from pyelasticsearch.client import ElasticSearch
from pyelasticsearch.exceptions import (Timeout, ConnectionError,
                                        ElasticHttpError,
                                        ElasticHttpNotFoundError,
                                        IndexAlreadyExistsError,
                                        InvalidJsonResponseError,
                                        BulkError)
from pyelasticsearch.utils import bulk_chunks


__author__ = 'Erik Rose'
__all__ = ['ElasticSearch', 'ElasticHttpError', 'Timeout', 'ConnectionError',
           'ElasticHttpNotFoundError', 'IndexAlreadyExistsError', 'BulkError',
           'InvalidJsonResponseError', 'bulk_chunks']
__version__ = '1.4.1'
__version_info__ = tuple(__version__.split('.'))

get_version = lambda: __version_info__
