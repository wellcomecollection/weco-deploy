import collections
import itertools

from .exceptions import ConfigError


def chunked_iterable(iterable, *, size):
    """
    Generate the entries in ``iterable`` in chunks of size ``size``.

    e.g. chunked_iterable([1, 2, 3, 4, 5], 2) -> [1, 2], [3, 4], [5]

    Taken from https://alexwlchan.net/2018/12/iterating-in-fixed-size-chunks/
    """
    it = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(it, size))
        if not chunk:
            break
        yield chunk


def convert_identified_list_to_dict(values):
    """
    Given a list of objects with a .id parameter, convert them to a dict
    keyed with the .id.
    """
    id_counts = collections.Counter(v.id for v in values)
    duplicate_ids = {id for id, count in id_counts.items() if count > 1}
    if duplicate_ids:
        raise ConfigError("Duplicate IDs: %s" % ", ".join(duplicate_ids))

    return {v.id: v for v in values}
