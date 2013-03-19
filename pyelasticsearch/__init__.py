from __future__ import absolute_import

from pyelasticsearch.client import ElasticSearch
from pyelasticsearch.exceptions import (Timeout, ConnectionError,
                                        ElasticHttpError,
                                        InvalidJsonResponseError,
                                        ElasticHttpNotFoundError,
                                        ElasticIndexAlreadyExistsError)

__author__ = 'Robert Eanes'
__all__ = ['ElasticSearch', 'ElasticHttpError', 'InvalidJsonResponseError',
           'Timeout', 'ConnectionError', 'ElasticHttpNotFoundError',
           'ElasticIndexAlreadyExistsError']
__version__ = '0.3'
__version_info__ = tuple(__version__.split('.'))

get_version = lambda: __version_info__
