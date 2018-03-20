from urllib3.exceptions import TimeoutError as Timeout

try:
    from urllib3.exceptions import NewConnectionError as ConnectionError
except ImportError:
    from urllib3.exceptions import ConnectionError


class ElasticHttpError(Exception):
    """Exception raised when ES returns a non-OK (>=400) HTTP status code"""
    # We can't just split this into separate subclasses for 4xx and 5xx errors.
    # ES, as of 0.19.9, returns 500s on trivial things like JSON parse errors
    # (which it does recognize), so it wouldn't be good to rely on its idea of
    # what's a client error and what's a server error. We have to test the
    # string for what kind of error it is and choose an exception class
    # accordingly.

    # This @property technique allows the exception to be pickled (like by
    # Sentry or celery) without having to write our own serialization stuff.
    @property
    def status_code(self):
        """The HTTP status code of the response that precipitated the error"""
        return self.args[0]

    @property
    def error(self):
        """A string error message"""
        return self.args[1]

    def __unicode__(self):
        return u'Non-OK response returned (%d): %r' % (self.status_code,
                                                       self.error)


class ElasticHttpNotFoundError(ElasticHttpError):
    """Exception raised when a request to ES returns a 404"""


class IndexAlreadyExistsError(ElasticHttpError):
    """Exception raised on an attempt to create an index that already exists"""


class BulkError(Exception):
    """
    Exception raised when one or more bulk actions fail

    You can extract document IDs from these to retry them.
    """
    @property
    def errors(self):
        """
        Return a list of actions that failed, in the format emitted by ES::

            {"index" : {
                "_index" : "test",
                "_type" : "type1",
                "_id" : "1",
                "status" : 409,
                "error" : "VersionConflictEngineException[[test][2] [type1][1]: version conflict, current [3], provided [2]]"
              }
            },
            {"update" : {
                "_index" : "index1",
                "_type" : "type1",
                "_id" : "1",
                "status" : 404,
                "error" : "DocumentMissingException[[index1][-1] [type1][1]: document missing]"
              }
            },
            ...

        """
        return self.args[0]

    @property
    def successes(self):
        """
        Return a list of actions that succeeded, in the same format as
        :meth:`errors`.
        """
        return self.args[1]

    def __unicode__(self):
        return u'%s of %s bulk actions failed.' % (len(self.errors),
                                                   len(self.errors) +
                                                        len(self.successes))


class InvalidJsonResponseError(Exception):
    """
    Exception raised in the unlikely event that ES returns a non-JSON response
    """
    @property
    def input(self):
        """Return the data we attempted to convert to JSON."""
        return self.args[0]

    def __unicode__(self):
        return u'Invalid JSON returned from ES: %r' % (self.input,)
