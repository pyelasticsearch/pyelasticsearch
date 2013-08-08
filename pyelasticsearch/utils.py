from datetime import datetime
from six import (iterkeys, binary_type, text_type, string_types, integer_types)
try:
    # PY3
    from urllib.parse import urlencode, quote_plus
except ImportError:
    # PY2
    from urllib import urlencode, quote_plus


def iso_datetime(value):
    """
    If value appears to be something datetime-like, return it in ISO format.

    Otherwise, return None.
    """
    if hasattr(value, 'strftime'):
        if hasattr(value, 'hour'):
            return value.isoformat()
        else:
            return '%sT00:00:00' % value.isoformat()

def obj_to_query(obj):
    """
    Convert a native-Python object to a unicode or bytestring
    representation suitable for a query string.
    """
    # Quick and dirty thus far
    if isinstance(obj, string_types):
        return obj
    if isinstance(obj, bool):
        return 'true' if obj else 'false'
    if isinstance(obj, integer_types):
        return str(obj)
    if isinstance(obj, float):
        return repr(obj)  # str loses precision.
    if isinstance(obj, (list, tuple)):
        return ','.join(obj_to_query(o) for o in obj)
    iso = iso_datetime(obj)
    if iso:
        return iso
    raise TypeError("obj_to_query() doesn't know how to represent %r in an ES"
                    ' query string.' % obj)

def obj_to_utf8(thing):
    """Convert any arbitrary ``thing`` to a utf-8 bytestring."""
    if isinstance(thing, binary_type):
        return thing
    if not isinstance(thing, text_type):
        thing = text_type(thing)
    return thing.encode('utf-8')


def concat(items):
    """
    Return a comma-delimited concatenation of the elements of ``items``,
    with any occurrences of "_all" omitted.

    If ``items`` is a string, promote it to a 1-item list.
    """
    # TODO: Why strip out _all?
    if items is None:
        return ''
    if isinstance(items, string_types):
        items = [items]
    return ','.join(i for i in items if i != '_all')

def join_path(path_components):
    """
    Smush together the path components, omitting '' and None ones.

    Unicodes get encoded to strings via utf-8. Incoming strings are assumed
    to be utf-8-encoded already.
    """
    path = '/'.join(quote_plus(obj_to_utf8(p), '') for p in path_components if
                    p is not None and p != '')

    if not path.startswith('/'):
        path = '/' + path
    return path

