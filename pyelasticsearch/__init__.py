from __future__ import absolute_import

from pyelasticsearch.client import ElasticSearch
from pyelasticsearch.exceptions import (Timeout, ConnectionError,
                                        ElasticHttpError,
                                        InvalidJsonResponseError,
                                        ElasticHttpNotFoundError)

__author__ = 'Robert Eanes'
__all__ = ['ElasticSearch', 'ElasticHttpError', 'InvalidJsonResponseError',
           'Timeout', 'ConnectionError', 'ElasticHttpNotFoundError']
__version__ = '0.2-a'
__version_info__ = tuple(__version__.split('.'))

get_version = lambda: __version_info__
