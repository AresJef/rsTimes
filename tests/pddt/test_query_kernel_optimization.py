"""Public query contracts for per-row targets and live timezone conversion."""
from datetime import timedelta, tzinfo

import pytest

from rstimes import Pddt


@pytest.mark.parametrize("unit", ["s", "ns"])
@pytest.mark.parametrize("method,targets", [
    ("is_year", [2024, 2025, 2024, 2024, 2024]),
    ("is_month", [5, 6, 5, 5, 5]),
    ("is_weekday", [1, 2, 1, 2, 1]),
    ("is_day", [7, 8, 7, 8, 7]),
])
def test_shared_wall_day_keeps_independent_row_targets(unit, method, targets):
    values = Pddt(["2024-05-07 00:00", "2024-05-07 23:59", None,
                   "2024-05-08", "2024-05-07"], unit=unit)
    assert getattr(values, method)(targets).tolist() == [True, False, False, True, True]


@pytest.mark.parametrize("method", ["isoyear", "isocalendar", "days_in_year"])
def test_queries_keep_each_valid_rows_dynamic_timezone_callback(method):
    class CountingZero(tzinfo):
        def __init__(self):
            self.calls = 0

        def utcoffset(self, value):
            return timedelta(0)

        def dst(self, value):
            return timedelta(0)

        def tzname(self, value):
            return "zero"

        def fromutc(self, value):
            self.calls += 1
            return value

    zone = CountingZero()
    values = Pddt(["2024-05-07 00:00", "2024-05-07 01:00", None,
                   "2024-05-08", "2024-05-07"], tz="UTC").tz_convert(zone)
    zone.calls = 0
    getattr(values, method)()
    assert zone.calls == 4
