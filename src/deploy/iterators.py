import itertools


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
