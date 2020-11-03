import datetime

import pytest

from deploy.pretty_printing import pprint_date


@pytest.mark.parametrize("date_obj, now, expected_str", [
    ("2020-01-01 12:00:00", "2020-01-01 12:00:01", "just now"),
    ("2020-01-01 12:00:00", "2020-01-01 12:02:00", "just now"),
    ("2020-01-01 12:00:00", "2020-01-01 12:02:02", "today @ 12:00 (2 min ago)"),
    ("2020-01-01 12:00:00", "2020-01-01 15:00:00", "today @ 12:00"),
    ("2020-01-01 23:59:00", "2020-01-02 00:02:00", "yesterday @ 23:59 (3 min ago)"),
    ("2020-01-01 12:00:00", "2020-01-02 12:00:00", "yesterday @ 12:00"),
    ("2019-01-01 12:00:00", "2020-01-02 12:00:00", "Tue  1 January 2019 @ 12:00"),
    ("2019-01-01 01:00:00", "2020-01-02 12:00:00", "Tue  1 January 2019 @ 01:00"),
    ("2019-01-20 12:00:00", "2020-01-02 12:00:00", "Sun 20 January 2019 @ 12:00"),
])
def test_pprint_date(date_obj, now, expected_str):
    date_obj = datetime.datetime.strptime(date_obj, "%Y-%m-%d %H:%M:%S")
    now = datetime.datetime.strptime(now, "%Y-%m-%d %H:%M:%S")

    assert pprint_date(date_obj, now=now) == expected_str
