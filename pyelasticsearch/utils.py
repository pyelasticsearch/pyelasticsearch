def bulk_chunks(actions, docs_per_chunk=300, bytes_per_chunk=None):
    """
    Return groups of bulk-indexing operations to send to
    :meth:`~pyelasticsearch.ElasticSearch.bulk()`.

    Return an iterable of chunks, each of which is a JSON-encoded line or pair
    of lines in the format understood by ES's bulk API.

    :arg actions: An iterable of bulk actions, JSON-encoded. The best idea is
        to pass me a list of the outputs from
        :meth:`~pyelasticsearch.ElasticSearch.index_op()`,
        :meth:`~pyelasticsearch.ElasticSearch.delete_op()`, and
        :meth:`~pyelasticsearch.ElasticSearch.update_op()`.
    :arg docs_per_chunk: The number of documents (or, more technically,
        actions) to put in each chunk. Set to None to use only
        ``bytes_per_chunk``.
    :arg bytes_per_chunk: The approximate number of bytes of HTTP body payload
         to put in each chunk. Leave at None to use only ``docs_per_chunk``.
         This option helps prevent timeouts when you have occasional very
         large documents. Without it, you may get unlucky: several large docs
         might land in one chunk, and ES might time out.

    Chunks are capped by ``docs_per_chunk`` or ``bytes_per_chunk``, whichever
    is reached first. Obviously, we cannot make a chunk to smaller than its
    smallest doc, but we do stop adding docs after that. If both
    ``docs_per_chunk`` and ``bytes_per_chunk`` are None, all docs end up in
    one big chunk (and you might as well not use this at all).
    """
    class Limiter(object):
        def __init__(self):
            self.reset()

        def next_is_under_limit(self, encoded_action):
            self.doc_count += 1
            self.byte_count += len(encoded_action) + 1  # +1 for \n
            return self.under_limit()

        def under_limit(self):
            if (docs_per_chunk is not None and
                self.doc_count >= docs_per_chunk):
                    return False
            if (bytes_per_chunk is not None and
                self.byte_count >= bytes_per_chunk):
                    return False
            return True

        def reset(self):
            self.doc_count = self.byte_count = 0

    def take_while_plus(predicate, iterable):
        """
        Like itertools.takewhile(), except include the item that made us
        stop.

        That way, we can call this repeatedly on the same iterable without
        dropping things on the floor.
        """
        # take_while_plus(lambda x: x<5, [1,4,6,4,1]) --> 1 4 6
        for x in iterable:
            yield x
            if not predicate(x):
                break

    it = iter(actions)
    limiter = Limiter()
    while True:
        # Yield one chunk:
        chunk = list(take_while_plus(limiter.next_is_under_limit, it))
        if chunk:  # Don't yield an empty chunk at the end.
            yield chunk
        else:  # We ran out of actions.
            break
        limiter.reset()
