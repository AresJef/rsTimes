"""Independent outcomes for canonical span and exact NumPy adapter shortcuts."""

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from rstimes import Delta


@pytest.mark.parametrize(
    "start,changes,target",
    [
        (datetime(2024, 5, 7, 15, 30, 1, 123456),
         dict(months=1, days=3, hours=2), datetime(2024, 6, 10, 17, 30, 1, 123456)),
        (datetime(2024, 1, 1), dict(microseconds=-1), datetime(2023, 12, 31, 23, 59, 59, 999999)),
        (datetime(2024, 1, 1, 0, 0, 0, 999999), dict(microseconds=1), datetime(2024, 1, 1, 0, 0, 1)),
        (datetime(2024, 1, 1, 23, 59, 59, 999999), dict(microseconds=1), datetime(2024, 1, 2)),
        (datetime(2024, 1, 2), dict(hours=-1, microseconds=-1), datetime(2024, 1, 1, 22, 59, 59, 999999)),
        (datetime(2024, 1, 1, microsecond=1), dict(nanoseconds=500), datetime(2024, 1, 1, microsecond=2)),
        (datetime(2024, 1, 1, microsecond=1), dict(nanoseconds=-500), datetime(2024, 1, 1)),
        (datetime(2024, 1, 1), dict(nanoseconds=-500), datetime(2024, 1, 1)),
        (date(2024, 1, 31), dict(months=1), date(2024, 2, 29)),
        (date(2024, 3, 31), dict(months=-1), date(2024, 2, 29)),
        (datetime.min, dict(year=9999, month=12, day=31), datetime(9999, 12, 31)),
        (datetime.max, dict(year=1, month=1, day=1), datetime(1, 1, 1, 23, 59, 59, 999999)),
    ],
)
def test_builtin_anchor_difference_is_canonical(start, changes, target):
    result = Delta(**changes).to_timedelta(start)
    assert type(result) is timedelta
    assert result == target - start
    assert 0 <= result.seconds < 86400
    assert 0 <= result.microseconds < 1000000


def test_builtin_aware_anchor_keeps_wall_span_across_negative_borrow():
    start = datetime(2024, 1, 1, tzinfo=timezone(timedelta(hours=8)))
    assert Delta(microseconds=-1).to_timedelta(start) == timedelta(microseconds=-1)


_NS = {
    "Y": 31556952 * 1000000000,
    "M": 2629746 * 1000000000,
    "W": 7 * 86400 * 1000000000,
    "D": 86400 * 1000000000,
    "h": 3600 * 1000000000,
    "m": 60 * 1000000000,
    "s": 1000000000,
    "ms": 1000000,
    "us": 1000,
    "ns": 1,
}


def _fixed_ns(value):
    return (
        ((value.days * 24 + value.hours) * 60 + value.minutes) * 60 + value.seconds
    ) * 1000000000 + value.microseconds * 1000 + value.nanoseconds


@pytest.mark.parametrize("unit", _NS)
@pytest.mark.parametrize("ticks,multiplier", [(1, 1), (-1, 1), (1500, 3)])
def test_exact_numpy_duration_addition_keeps_units_and_absolute_presence(unit, ticks, multiplier):
    source = np.asarray(ticks, dtype=f"timedelta64[{multiplier}{unit}]")[()]
    delta = Delta(months=1, nanoseconds=1, microsecond=0, nanosecond=5)
    expected = 1 + ticks * multiplier * _NS[unit]
    for result in (delta + source, delta.__radd__(source)):
        assert type(result) is Delta
        assert (result.years, result.months) == (0, 1)
        assert _fixed_ns(result) == expected
        assert result.microsecond == 0
        assert result.nanosecond == 5


@pytest.mark.parametrize("left,right", [(-(2**63), 2**63 - 1), (2**63 - 1, -(2**63) + 1)])
def test_numpy_day_cancellation_checks_only_the_final_day_group(left, right):
    result = Delta(days=left, nanoseconds=1) + np.timedelta64(right, "D")
    assert result.days == left + right
    assert result.nanoseconds == 1


def test_numpy_duration_final_capacity_and_nat_still_fail():
    with pytest.raises(OverflowError):
        Delta(days=2**63 - 1) + np.timedelta64(1, "D")
    with pytest.raises(ValueError):
        Delta() + np.timedelta64("NaT", "ns")


def test_exact_numpy_date_and_foreign_type_boundary():
    result = Delta(months=1, days=3, hours=2) + np.datetime64("2024-05-07T15:30:01", "us")
    assert type(result) is datetime
    assert result == datetime(2024, 6, 10, 17, 30, 1)

    class datetime64:
        __module__ = "numpy"

    assert Delta().__add__(datetime64()) is NotImplemented


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({}, (0,) * 8 + (-1,) * 9),
        (dict(nanosecond=0), (0,) * 8 + (-1,) * 8 + (0,)),
        (dict(microsecond=0), (0,) * 8 + (-1,) * 7 + (0, -1)),
        (dict(days=-1, nanoseconds=1), (0, 0, -1, 0, 0, 0, 0, 1) + (-1,) * 9),
    ],
)
def test_state_shortcut_preserves_all_seventeen_fields_and_explicit_zero(changes, expected):
    state = Delta(**changes).__getstate__()
    assert state[:3] == ("rstimes.delta", 2, expected)
    assert all(type(field) is int for field in state[2])


def test_empty_absolute_state_still_captures_real_child_business_metadata():
    class Child(Delta):
        pass

    value = Child(days=1)
    value.note = "business"
    state = value.__getstate__()
    assert state[2] == (0, 0, 1, 0, 0, 0, 0, 0) + (-1,) * 9
    assert state[3] == {"note": "business"}


def test_repeated_present_zero_state_keeps_live_metadata_and_independent_snapshots():
    class Child(Delta):
        pass

    value = Child(nanoseconds=1, nanosecond=0)
    value.note = "first"
    first = value.__getstate__()
    value.note = "second"
    second = value.__getstate__()
    fields = (0, 0, 0, 0, 0, 0, 0, 1) + (-1,) * 8 + (0,)
    assert first[:3] == ("rstimes.delta", 2, fields)
    assert second[:3] == ("rstimes.delta", 2, fields)
    assert first[3] == {"note": "first"}
    assert second[3] == {"note": "second"}
    first[3]["extra"] = "not live"
    assert value.__dict__ == {"note": "second"}
    assert second[3] == {"note": "second"}
