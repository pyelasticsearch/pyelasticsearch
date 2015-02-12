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
    :arg bytes_per_chunk: The maximum number of bytes of HTTP body payload to
         put in each chunk. Leave at None to use only ``docs_per_chunk``. This
         option helps prevent timeouts when you have occasional very large
         documents. Without it, you may get unlucky: several large docs might
         land in one chunk, and ES might time out.

    Chunks are capped by ``docs_per_chunk`` or ``bytes_per_chunk``, whichever
    is reached first. Obviously, we cannot make a chunk to smaller than its
    smallest doc, but we do the best we can. If both ``docs_per_chunk`` and
    ``bytes_per_chunk`` are None, all docs end up in one big chunk (and you
    might as well not use this at all).
    """
    chunk = []
    docs = bytes = 0
    for action in actions:
        next_len = len(action) + 1  # +1 for \n
        if chunk and ((docs_per_chunk and docs >= docs_per_chunk) or
                      (bytes_per_chunk and bytes + next_len > bytes_per_chunk)):
            # If adding this action will cause us to go over a limit, spit out
            # the current chunk:
            yield chunk
            chunk = []
            docs = bytes = 0
        chunk.append(action)
        docs += 1
        bytes += next_len

    if chunk:  # Yield leftovers at the end.
        yield chunk
