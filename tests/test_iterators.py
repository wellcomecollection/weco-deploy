from deploy.iterators import chunked_iterable


def test_chunked_iterable():
    numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    print(list(chunked_iterable(numbers, size=3)))
    assert list(chunked_iterable(numbers, size=3)) == [
        (1, 2, 3),
        (4, 5, 6),
        (7, 8, 9),
        (10,),
    ]

    assert list(chunked_iterable(numbers, size=5)) == [
        (1, 2, 3, 4, 5),
        (6, 7, 8, 9, 10),
    ]
