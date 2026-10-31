"""Preserve real Timestamp sub-microsecond data across pandas2 and pandas3."""
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

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


@pytest.mark.parametrize("unit", ["s", "us", "ns"])
@pytest.mark.parametrize("change", [1, 500, 1500])
@pytest.mark.parametrize("direction", ["left", "right", "subtract", "many"])
def test_timestamp_delta_result_has_coherent_public_ticks_and_comparison(unit, change, direction):
    source = pd.Timestamp("1970-01-02 00:00:01").as_unit(unit)
    delta = Delta(nanoseconds=change)
    result = (delta + source if direction == "left" else source + delta if direction == "right"
              else source - delta if direction == "subtract" else delta.apply_many([source])[0])
    expected_ticks = 86_401_000_000_000 + (-change if direction == "subtract" else change)
    assert type(result) is pd.Timestamp
    assert result.value == expected_ticks
    assert result == pd.Timestamp(expected_ticks, unit="ns")
    assert int(result.asm8.astype("int64")) == expected_ticks and str(result.asm8.dtype) == "datetime64[ns]"


@pytest.mark.parametrize("zone", [None, timezone.utc, ZoneInfo("America/New_York")])
@pytest.mark.parametrize("fold", [0, 1])
def test_timestamp_result_keeps_zone_and_fold_when_coarse_storage_gains_a_tail(zone, fold):
    source = pd.Timestamp(year=2024, month=11, day=3, hour=1, minute=30, tzinfo=zone, fold=fold).as_unit("us")
    result = source + Delta(nanoseconds=500)
    expected = pd.Timestamp(year=2024, month=11, day=3, hour=1, minute=30,
                            nanosecond=500, tzinfo=zone, fold=fold)
    assert result.value == expected.value and result == expected
    assert result.tzinfo is source.tzinfo and result.fold == fold


def test_inherited_timestamp_native_replace_returns_a_coherent_base_result():
    source = pd.Timestamp("1970-01-01").as_unit("us")
    source.__class__ = HiddenTail
    result = Delta(nanoseconds=1) + source
    assert type(result) is pd.Timestamp and result.value == 1


def test_custom_timestamp_replace_still_controls_its_exact_return_and_error():
    calls = []
    marker = object()
    class Custom(pd.Timestamp):
        def replace(self, **kwargs):
            calls.append(kwargs)
            return marker
    source = pd.Timestamp("1970-01-01").as_unit("us")
    source.__class__ = Custom
    assert Delta(nanoseconds=1) + source is marker
    assert len(calls) == 1 and calls[0]["nanosecond"] == 1
    error = ValueError("external replace failure")
    class Broken(pd.Timestamp):
        def replace(self, **kwargs):
            raise error
    source.__class__ = Broken
    with pytest.raises(ValueError) as caught:
        Delta(nanoseconds=1) + source
    assert caught.value is error


def test_dynamic_timestamp_attribute_binding_keeps_the_original_protocol():
    calls = []
    marker = object()
    class Dynamic(pd.Timestamp):
        def __getattribute__(self, name):
            if name == "replace":
                def replacement(**kwargs):
                    calls.append(kwargs)
                    return marker
                return replacement
            return super().__getattribute__(name)
    source = pd.Timestamp("1970-01-01").as_unit("us")
    source.__class__ = Dynamic
    assert Delta(nanoseconds=1) + source is marker
    assert len(calls) == 1


def test_timestamp_nanosecond_borrow_has_coherent_negative_epoch_ticks():
    source = pd.Timestamp("1970-01-01").as_unit("us")
    result = source - Delta(nanoseconds=1)
    assert result.value == -1 and result == pd.Timestamp(-1, unit="ns")


def test_wide_timestamp_final_capacity_is_checked_after_absolute_year_change():
    source = pd.Timestamp(np.datetime64("12024-01-01", "us"))
    result = source + Delta(year=2024, nanoseconds=1)
    assert result == pd.Timestamp("2024-01-01 00:00:00.000000001")
    assert result.unit == "ns"
    with pytest.raises((OverflowError, pd.errors.OutOfBoundsDatetime)):
        source + Delta(nanoseconds=1)
