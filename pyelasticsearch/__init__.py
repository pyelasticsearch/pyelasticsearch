from __future__ import absolute_import

from pyelasticsearch.client import ElasticSearch
from pyelasticsearch.utils import obj_to_query, obj_to_utf8
from pyelasticsearch.exceptions import (Timeout, ConnectionError,
                                        ElasticHttpError,
                                        InvalidJsonResponseError,
                                        ElasticHttpNotFoundError,
                                        IndexAlreadyExistsError)

__author__ = 'Robert Eanes'
__all__ = ['ElasticSearch', 'obj_to_query', 'obj_to_utf8', 'ElasticHttpError', 'InvalidJsonResponseError',
           'Timeout', 'ConnectionError', 'ElasticHttpNotFoundError',
           'IndexAlreadyExistsError']
__version__ = '0.6.1'
__version_info__ = tuple(__version__.split('.'))

get_version = lambda: __version_info__
