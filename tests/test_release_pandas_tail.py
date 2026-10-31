"""Preserve real Timestamp sub-microsecond data across pandas2 and pandas3."""
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from rstimes import Delta, Pddt, Pldt, Pydt, parse_to_epoch


class HiddenTail(pd.Timestamp):
    """Hide Python properties without changing the actual Timestamp value."""

    @property
    def nanosecond(self):
        return 0


@pytest.mark.parametrize("year", [1970, 1972, 2024])
@pytest.mark.parametrize("direction", ["left", "right", "many"])
def test_relative_delta_retains_real_tail(year, direction):
    value = pd.Timestamp(f"{year}-01-02 03:04:05.000001123")
    value.__class__ = HiddenTail
    expected = value + timedelta(microseconds=1)
    delta = Delta(microseconds=1)
    result = delta + value if direction == "left" else value + delta if direction == "right" else delta.apply_many([value])[0]
    assert result == expected
    assert pd.Timestamp.nanosecond.__get__(result) == 123


@pytest.mark.parametrize("unit", ["s", "ms", "us"])
def test_zero_tail_does_not_narrow_wide_timestamp(unit):
    value = pd.Timestamp(np.datetime64("12024-01-01", unit))
    result = value + Delta(days=1)
    assert result.year == 12024 and result.day == 2
    assert result.asm8.dtype == value.asm8.dtype


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("tail", [1, 500, 999])
@pytest.mark.parametrize("before_epoch", [False, True])
def test_coarse_timestamp_replacement_tail_is_shared_by_all_native_readers(unit, tail, before_epoch):
    # In pandas2 asm8 can still be coarse after replace. The public base field
    # is real; ns asm8 already includes it. Use a literal epoch expectation,
    # never Timestamp subtraction/equality as the precision oracle.
    text = "1969-12-31 23:59:59" if before_epoch else "1970-01-01 00:00:01"
    value = pd.Timestamp(text).as_unit(unit).replace(nanosecond=tail)
    value.__class__ = HiddenTail
    expected = (-1_000_000_000 if before_epoch else 1_000_000_000) + tail
    assert pd.Timestamp.nanosecond.__get__(value) == tail
    assert parse_to_epoch(value, unit="ns") == expected
    assert Pddt([value], unit="ns").asi8.tolist() == [expected]
    assert Pldt([value], unit="ns").to_physical().to_list() == [expected]
    quotient, remainder = divmod(-expected, 1000)
    expected_us = quotient + (remainder > 500 or (remainder == 500 and quotient % 2 != 0))
    assert Pydt(1970, 1, 1) - value == timedelta(microseconds=expected_us)


@pytest.mark.parametrize("constructor", [Pddt, Pldt])
def test_timestamp_actual_tail_participates_in_default_column_resolution(constructor):
    value = pd.Timestamp("1970-01-01 00:00:01").as_unit("us").replace(nanosecond=500)
    result = constructor([value])
    ticks = result.asi8.tolist() if isinstance(result, Pddt) else result.to_physical().to_list()
    assert ticks == [1_000_000_500]
    assert result.unit == "ns" if isinstance(result, Pddt) else result.dtype.time_unit == "ns"
    with pytest.raises(ValueError):
        constructor([value], unit="us")


def test_coarse_wide_timestamp_tail_does_not_force_an_int64_ns_intermediate():
    scalar = np.datetime64("12024-01-01", "us")
    expected = int(scalar.astype("int64")) * 1000 + 500
    try:
        value = pd.Timestamp(scalar).replace(nanosecond=500)
    except pd.errors.OutOfBoundsDatetime:
        # pandas3 promotes its replacement to ns and rejects this source
        # itself; no such input reaches our adapter. pandas2 can represent it
        # as coarse storage plus its real tail and must use the wide Rust path.
        assert expected > np.iinfo(np.int64).max
        return
    assert parse_to_epoch(value, unit="ns") == expected


@pytest.mark.parametrize("change,expected_us", [(500, 0), (1500, 2), (2500, 2), (-1500, -2)])
def test_timestamp_span_rounding_keeps_new_tail_until_standard_timedelta(change, expected_us):
    source = pd.Timestamp("2024-01-01 00:00:00.000001")
    assert Delta(nanoseconds=change).to_timedelta(source) == timedelta(microseconds=expected_us)
