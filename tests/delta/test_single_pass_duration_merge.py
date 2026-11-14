"""Independent integer oracle for a single final day/clock normalization."""
import numpy as np
import pytest

from rstimes import Delta

DAY = 86_400_000_000_000


@pytest.mark.parametrize("days,clock", [(-(2**63), 0), (-(2**63), DAY-1), (2**63-1, 0), (2**63-1, DAY-1), (-1, 1), (0, DAY-1)])
@pytest.mark.parametrize("unit,scale", [("us", 1000), ("ns", 1), ("2D", 2*DAY)])
@pytest.mark.parametrize("ticks", [-1, 1])
@pytest.mark.parametrize("operation", ["add", "sub", "radd", "rsub"])
def test_numpy_duration_normalizes_once_at_final_signed_day_boundary(days, clock, unit, scale, ticks, operation):
    left = Delta(days=days, nanoseconds=clock, nanosecond=2)
    right = np.timedelta64(ticks, unit)
    total = days * DAY + clock
    expected = (total + ticks*scale if operation in ("add", "radd")
                else total - ticks*scale if operation == "sub" else ticks*scale - total)
    expected_day, expected_clock = divmod(expected, DAY)

    def calculate():
        if operation == "add":
            return left + right
        if operation == "sub":
            return left - right
        if operation == "radd":
            return right + left
        return right - left

    if not -(2**63) <= expected_day < 2**63:
        with pytest.raises(OverflowError):
            calculate()
    else:
        result = calculate()
        actual_clock = ((result.hours*60 + result.minutes)*60 + result.seconds)*1_000_000_000 + result.microseconds*1000 + result.nanoseconds
        assert (result.days, actual_clock) == (expected_day, expected_clock)
        assert result.nanosecond == 2
    assert left.days == days and left.nanosecond == 2

# PR-005: standard canonical fields feed the existing day/clock completion.
from datetime import timedelta


class PassiveDuration(timedelta):
    pass


@pytest.mark.parametrize("days,clock", [(-2**63, 0), (-2**63, DAY - 1),
    (2**63 - 1, 0), (2**63 - 1, DAY - 1), (-1, 1), (0, DAY - 1)])
@pytest.mark.parametrize("duration", [timedelta.min, timedelta.max, timedelta(), timedelta(days=1),
    timedelta(microseconds=-1), timedelta(microseconds=1), timedelta(days=-2, seconds=71, microseconds=123)])
@pytest.mark.parametrize("subclass", (False, True))
@pytest.mark.parametrize("operation", ("add", "sub", "radd", "rsub"))
def test_canonical_standard_duration_preserves_full_value_and_final_bounds(days, clock, duration, subclass, operation):
    right = PassiveDuration(days=duration.days, seconds=duration.seconds, microseconds=duration.microseconds) if subclass else duration
    left = Delta(years=1, months=2, days=days, nanoseconds=clock, month=2, day=29,
                 microsecond=123456, nanosecond=789)
    source = days * DAY + clock
    span = (duration.days * 86400 + duration.seconds) * 1_000_000_000 + duration.microseconds * 1000
    total = source + span if operation in ("add", "radd") else source - span if operation == "sub" else span - source
    target_day, target_clock = divmod(total, DAY)
    def calculate():
        if operation == "add":
            return left + right
        if operation == "sub":
            return left - right
        if operation == "radd":
            return right + left
        return right - left
    if not -2**63 <= target_day < 2**63:
        with pytest.raises(OverflowError):
            calculate()
    else:
        result = calculate()
        actual_clock = ((result.hours * 60 + result.minutes) * 60 + result.seconds) * 1_000_000_000 + result.microseconds * 1000 + result.nanoseconds
        assert type(result) is Delta
        assert (result.days, actual_clock) == (target_day, target_clock)
        assert result.years * 12 + result.months == (-14 if operation == "rsub" else 14)
        assert (result.month, result.day, result.microsecond, result.nanosecond) == (2, 29, 123456, 789)
    assert left.days == days and left.month == 2 and left.nanosecond == 789


def test_standard_duration_bulk_prefix_mixture_and_business_result_remain():
    calls = []
    marker = object()
    class Business(timedelta):
        def __add__(self, other):
            calls.append(other)
            return marker
    value = Delta(nanoseconds=1, nanosecond=789)
    inputs = [timedelta(), timedelta(microseconds=-1), np.timedelta64(2, "ns"), Delta(nanoseconds=3), Business()]
    results = value.apply_many(inputs)
    assert [x.days * DAY + ((x.hours * 60 + x.minutes) * 60 + x.seconds) * 1_000_000_000 + x.microseconds * 1000 + x.nanoseconds for x in results[:-1]] == [1, -999, 3, 4]
    assert all(x.nanosecond == 789 for x in results[:-1])
    assert results[-1] is marker and calls == [value]


def test_standard_duration_bulk_stops_at_first_real_capacity_failure():
    calls = []
    class Later:
        def __add__(self, other):
            calls.append(other)
            return object()
    inputs = [timedelta(), timedelta(days=1), Later()]
    original = tuple(inputs)
    with pytest.raises(OverflowError):
        Delta(days=2**63 - 1).apply_many(inputs)
    assert tuple(inputs) == original and calls == []
