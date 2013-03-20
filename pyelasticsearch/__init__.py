from __future__ import absolute_import

from pyelasticsearch.client import ElasticSearch
from pyelasticsearch.exceptions import (Timeout, ConnectionError,
                                        ElasticHttpError,
                                        InvalidJsonResponseError,
                                        ElasticHttpNotFoundError,
                                        IndexAlreadyExistsError)

__author__ = 'Robert Eanes'
__all__ = ['ElasticSearch', 'ElasticHttpError', 'InvalidJsonResponseError',
           'Timeout', 'ConnectionError', 'ElasticHttpNotFoundError',
           'IndexAlreadyExistsError']
__version__ = '0.4'
__version_info__ = tuple(__version__.split('.'))

get_version = lambda: __version_info__
