from __future__ import absolute_import

from pyelasticsearch.client import ElasticSearch
from pyelasticsearch.exceptions import (Timeout, ConnectionError,
                                        ElasticHttpError,
                                        ElasticHttpNotFoundError,
                                        IndexAlreadyExistsError,
                                        InvalidJsonResponseError)

__author__ = 'Erik Rose'
__all__ = ['ElasticSearch', 'ElasticHttpError', 'Timeout', 'ConnectionError',
           'ElasticHttpNotFoundError', 'IndexAlreadyExistsError']
__version__ = '0.8.0'
__version_info__ = tuple(__version__.split('.'))

get_version = lambda: __version_info__
