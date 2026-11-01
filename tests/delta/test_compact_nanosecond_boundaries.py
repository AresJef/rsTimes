"""Public independent field answers for the proposed compact value change.

No assertion depends on private packing, object size, or a native implementation.
"""
import copy
import pickle

import pytest

from rstimes import Delta


RELATIVE = ("years", "months", "days", "hours", "minutes", "seconds", "microseconds", "nanoseconds")
ABSOLUTE = ("year", "month", "day", "weekday", "hour", "minute", "second", "microsecond", "nanosecond")
DAY_NS = 86_400_000_000_000


def public_core(value):
    return tuple(getattr(value, field) for field in RELATIVE) + tuple(
        -1 if getattr(value, field) is None else getattr(value, field)
        for field in ABSOLUTE
    )


@pytest.mark.parametrize("years", [-(2**63), -1, 0, 2**63-1])
@pytest.mark.parametrize("days", [-(2**63), -1, 0, 2**63-1])
@pytest.mark.parametrize("months", [0, 11])
@pytest.mark.parametrize("clock,expected_clock", [
    (0, (0, 0, 0, 0, 0)),
    (DAY_NS-1, (23, 59, 59, 999999, 999)),
])
def test_signed_groups_and_maximum_bounded_clock_are_independent(years, days, months, clock, expected_clock):
    value = Delta(years=years, months=months, days=days, nanoseconds=clock)
    expected = (years, months, days, *expected_clock, *([-1]*9))
    assert public_core(value) == expected
    assert value.__getstate__()[2] == expected
    assert hash(value) == hash(expected)


@pytest.mark.parametrize("microsecond", [None, 0, 999999])
@pytest.mark.parametrize("nanosecond", [None, 0, 999])
def test_absolute_presence_does_not_overwrite_relative_month_or_clock(microsecond, nanosecond):
    value = Delta(months=11, nanoseconds=DAY_NS-1, year=9999, month=12,
                  day=31, weekday=6, hour=23, minute=59, second=59,
                  microsecond=microsecond, nanosecond=nanosecond)
    expected = (0, 11, 0, 23, 59, 59, 999999, 999,
                9999, 12, 31, 6, 23, 59, 59,
                -1 if microsecond is None else microsecond,
                -1 if nanosecond is None else nanosecond)
    assert public_core(value) == expected
    assert public_core(abs(value)) == expected
    assert public_core(copy.copy(value)) == expected
    assert public_core(copy.deepcopy(value)) == expected
    assert public_core(pickle.loads(pickle.dumps(value))) == expected


def test_separate_absolute_ns_merge_preserves_every_relative_bit():
    left = Delta(months=11, nanoseconds=DAY_NS-1, microsecond=999999)
    right = Delta(nanosecond=0)
    added = left + right
    subtracted = left - right
    assert public_core(added) == (0, 11, 0, 23, 59, 59, 999999, 999,
                                  -1, -1, -1, -1, -1, -1, -1, 999999, 0)
    assert public_core(subtracted) == public_core(added)
    assert public_core(left) == (0, 11, 0, 23, 59, 59, 999999, 999,
                                 -1, -1, -1, -1, -1, -1, -1, 999999, -1)


@pytest.mark.parametrize("month,ns", [(0, 0), (11, 0), (0, 999), (11, 999)])
def test_changing_only_absolute_ns_does_not_change_a_relative_boundary(month, ns):
    value = Delta(months=month, nanoseconds=DAY_NS-1)
    changed = value + Delta(nanosecond=ns)
    assert public_core(changed)[:8] == (0, month, 0, 23, 59, 59, 999999, 999)
    assert changed.nanosecond == ns
    assert value.nanosecond is None
