"""Native shortcuts retain real input roles, callback qualification and capacity."""
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from rstimes import Pydt, parse_to_epoch


@pytest.mark.parametrize("year", [1, 1969, 1970, 2024, 9999])
@pytest.mark.parametrize("unit,scale", [("s", 10**9), ("ms", 10**6), ("us", 1000), ("ns", 1)])
def test_exact_builtin_utc_epoch_matches_integer_calendar(year, unit, scale):
    value = datetime(year, 5, 7, 12, 34, 56, 123456, tzinfo=timezone.utc)
    span = value.replace(tzinfo=None) - datetime(1970, 1, 1)
    nanos = ((span.days * 86400 + span.seconds) * 10**6 + span.microseconds) * 1000
    assert parse_to_epoch(value, unit=unit, ignoretz=False) == nanos // scale


def test_utc_datetime_subclass_still_calls_its_actual_offset():
    calls = []

    class Child(datetime):
        def utcoffset(self):
            calls.append(self)
            return timedelta(hours=2)

    value = Child(1970, 1, 1, 2, tzinfo=timezone.utc)
    assert parse_to_epoch(value, unit="ns", ignoretz=False) == 0
    assert calls == [value]


@pytest.mark.parametrize("year", [-1, 0, 12000])
def test_wide_default_keeps_true_year_and_only_supplies_ymd(year):
    text = f"{year:04d}-05-07" if year >= 0 else "-0001-05-07"
    fallback = pd.Timestamp(np.datetime64(text, "us"))
    expected = np.datetime64(text + "T12:30:00", "us").astype("i8").item()
    assert parse_to_epoch("12:30", unit="us", default=fallback) == expected


@pytest.mark.parametrize("year", [1, 1969, 2024, 9999])
def test_naive_pydt_minus_date_remains_standard_timedelta(year):
    value = Pydt(year, 5, 7, 12, 34, 56, 123456)
    target = date(year, 5, 6)
    result = value - target
    expected = datetime(year, 5, 7, 12, 34, 56, 123456) - datetime(year, 5, 6)
    assert type(result) is timedelta and result == expected


@pytest.mark.parametrize("unit", ["D", "s", "ms", "us", "ns"])
def test_naive_pydt_minus_numpy_date_keeps_microsecond_rule(unit):
    value = Pydt(1970, 1, 1, 0, 0, 1, 123456)
    target = np.datetime64(-1, unit)
    microseconds = target.astype("datetime64[us]").astype("i8").item()
    result = value - target
    assert type(result) is timedelta
    assert result == timedelta(microseconds=1_123456 - microseconds)


@pytest.mark.parametrize("text", ["0000-01-01", "10000-01-01"])
def test_numpy_subtraction_does_not_expand_its_existing_source_capacity(text):
    with pytest.raises(OverflowError):
        Pydt(2024, 1, 1) - np.datetime64(text, "us")


def test_aware_pydt_minus_naive_date_still_rejects_domain_mix():
    value = Pydt(2024, 5, 7, tzinfo=timezone.utc)
    with pytest.raises(TypeError):
        value - date(2024, 5, 6)
    with pytest.raises(TypeError):
        value - np.datetime64("2024-05-06", "us")
