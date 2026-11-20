"""PR-001/007: wide intermediates preserve final calendar and capacity rules."""
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pytest
from rstimes import Pldt
import polars as pl


def values(result):
    return result.to_list()

def january_ordinal(year):
    before = year - 1
    return 365 * before + before // 4 - before // 100 + before // 400 + 1


def calendar_bucket(seconds, unit):
    # Independent Python integers and a year bisection, not the Rust decoder.
    ordinal = seconds // 86400 + 719163
    low = min(ordinal // 365, ordinal // 366) - 4
    high = max(ordinal // 365, ordinal // 366) + 4
    while low + 1 < high:
        mid = (low + high) // 2
        if january_ordinal(mid) <= ordinal:
            low = mid
        else:
            high = mid
    year = low
    day = ordinal - january_ordinal(year)
    lengths = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
               31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    month = 1
    for length in lengths:
        if day < length:
            break
        day -= length
        month += 1
    if unit == "Y":
        return year - 1970
    return (year - 1970) * (4 if unit == "Q" else 12) + ((month - 1) // 3 if unit == "Q" else month - 1)


def expected_difference(target, unit, absolute, inclusive):
    result = -calendar_bucket(target, unit)
    if absolute:
        result = abs(result)
    adjustment = {"one": 0, "both": 1, "neither": -1}[inclusive]
    return result + (-adjustment if result < 0 else adjustment)


@pytest.mark.parametrize("unit", ("ms", "us", "ns"))
@pytest.mark.parametrize("n", (-10**14, -1, 1, 10**14))
@pytest.mark.parametrize("field", ("years", "months"))
@pytest.mark.parametrize("subtract", (False, True))
@pytest.mark.parametrize("expression", (False, True))
def test_four_century_cycles_cancel_before_final_capacity(unit, n, field, subtract, expression):
    text = {"s": "2024-01-31T12:34:56", "ms": "2024-01-31T12:34:56.123",
            "us": "2024-01-31T12:34:56.123456", "ns": "2024-01-31T12:34:56.123456789"}[unit]
    source = Pldt([text, None], unit=unit, name="clock")
    fields = {field: (400 if field == "years" else 4800) * n, "weeks": -20871 * n}
    method = "sub" if subtract else "add"
    if expression:
        expr = getattr(pl.col("clock").pldt, method)(**fields)
        result = pl.DataFrame({"clock": source}).lazy().select(expr).collect().to_series()
    else:
        result = getattr(source, method)(**fields)
    assert result.to_physical().to_list() == source.to_physical().to_list()
    assert result.name == "clock" and result.dtype.time_unit == unit


@pytest.mark.parametrize("zone", (None, timezone.utc, timezone(timedelta(hours=8)), ZoneInfo("America/New_York")))
def test_wide_calendar_cancellation_retains_actual_timezone(zone):
    source = Pldt(["2024-02-29T12:34:56.123456", None], tz=zone, unit="us")
    result = source.add(years=400 * 10**14, weeks=-20871 * 10**14)
    assert result.to_physical().to_list() == source.to_physical().to_list() and result.dtype == source.dtype


def test_zero_year_calendar_and_large_cycles_still_cancel():
    source = Pldt(["0000-02-29T12:34:56.123456"], unit="us")
    assert source.add(years=400 * 10**14, weeks=-20871 * 10**14).to_physical().to_list() == source.to_physical().to_list()


def test_true_final_calendar_overflow_and_signed_year_boundary_remain():
    source = Pldt(["2024-01-31"], unit="ns")
    with pytest.raises(OverflowError):
        source.add(years=400 * 10**14)
    with pytest.raises(OverflowError):
        source.add(years=2**63 - 1)
    with pytest.raises(OverflowError):
        Pldt([np.datetime64(2**63 - 1, "M")], unit="us")


@pytest.mark.parametrize("target", (-2**80, 2**80, -2**60, 2**60))
@pytest.mark.parametrize("unit", ("Y", "Q", "M"))
@pytest.mark.parametrize("absolute", (False, True))
@pytest.mark.parametrize("inclusive", ("one", "both", "neither"))
@pytest.mark.parametrize("expression", (False, True))
def test_wide_calendar_difference_uses_independent_integer_bucket(target, unit, absolute, inclusive, expression):
    source = Pldt([0, 0], unit="us", name="clock")
    if expression:
        expr = pl.col("clock").pldt.diff(target, unit, absolute=absolute, inclusive=inclusive)
        result = pl.DataFrame({"clock": source}).lazy().select(expr).collect().to_series()
    else:
        result = source.pldt.diff(target, unit, absolute=absolute, inclusive=inclusive)
    assert result.to_list() == [expected_difference(target, unit, absolute, inclusive)] * 2


def test_wide_difference_missing_targets_and_sources_stay_missing():
    source = Pldt([0, 0, 0, None], unit="us")
    result = source.pldt.diff([-2**80, 2**80, None, 0], "M")
    assert result.to_list()[:2] == [expected_difference(-2**80, "M", False, "one"), expected_difference(2**80, "M", False, "one")]
    assert result.is_null().to_list() == [False, False, True, True]


def test_wide_difference_checks_only_final_int64_capacity():
    source = Pldt([0], unit="us")
    assert values(source.pldt.diff(-2**80, "Y")) == [38309334171900670]
    for target in (-2**80, 2**80):
        assert values(source.pldt.diff(target, "W")) == [-((target // 86400 + 3) // 7)]
        with pytest.raises(OverflowError):
            source.pldt.diff(target, "D")
    with pytest.raises(OverflowError):
        source.pldt.diff(2**85, "M")
    assert values(source.pldt.diff(2**85, "Y")) == [expected_difference(2**85, "Y", False, "one")]
