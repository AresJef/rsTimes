"""Numeric fraction output preserves mature platform, timezone and year rules."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from rstimes import Pddt


ZONES = [None, timezone.utc, timezone(timedelta(hours=8), "east%name"),
         timezone(-timedelta(hours=5, seconds=30)), ZoneInfo("UTC"),
         ZoneInfo("America/New_York")]


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("zone", ZONES)
@pytest.mark.parametrize("form", ["ordinary", "calendar", "escaped"])
def test_fraction_numeric_output_matches_independent_standard_fields(unit, zone, form):
    fraction = {"s": "", "ms": ".123", "us": ".123456", "ns": ".123456789"}[unit]
    nanos = {"s": "000000000", "ms": "123000000", "us": "123456000", "ns": "123456789"}[unit]
    micros = int(nanos[:6])
    inputs = ["2024-01-02 03:04:05" + fraction, "2024-07-08 23:59:58" + fraction, None]
    source = Pddt(inputs, unit=unit, tz=zone, name="stamp")
    before = source.asi8.copy()
    dates = [datetime(2024, 1, 2, 3, 4, 5, micros, tzinfo=zone),
             datetime(2024, 7, 8, 23, 59, 58, micros, tzinfo=zone)]
    if form == "ordinary":
        fmt = "%Y-%m-%d %H:%M:%S.%f"
        digits = nanos if unit == "ns" else nanos[:6]
        expected = [value.strftime("%Y-%m-%d %H:%M:%S.") + digits for value in dates]
    elif form == "calendar":
        fmt = "%Y%y %m %d %H %I %M %S %j %w %U %W %z %Z%.0f"
        expected = [value.strftime(fmt[:-4]) for value in dates]
    else:
        fmt = "%%f|%%.3f|%.3f|%.9f|%.0f"
        expected = ["%f|%.3f|." + nanos[:3] + "|." + nanos + "|"] * 2
    result = source.strftime(fmt)
    assert result.name == "stamp" and result.dtype == object
    assert result[:2].tolist() == expected
    assert pd.isna(result[2])
    np.testing.assert_array_equal(source.asi8, before)


@pytest.mark.parametrize("year", [0, 1, 999, 1000, 9999, 10000, -1])
def test_small_and_wide_years_keep_the_mature_result_or_original_error(year):
    spelling = f"{year:04d}" if year >= 0 else "-0001"
    value = np.datetime64(spelling + "-01-02T03:04:05.123456", "us")
    source = Pddt(np.array([value]))
    scalar = pd.Timestamp(value)
    try:
        expected = scalar.strftime("%Y|123456|.123|.123456000")
    except Exception as original:
        with pytest.raises(type(original)):
            source.strftime("%Y|%f|%.3f|%.9f")
    else:
        assert source.strftime("%Y|%f|%.3f|%.9f").tolist() == [expected]


@pytest.mark.parametrize("fmt, expanded", [
    ("%A %B %p %f", "%A %B %p 123456"),
    ("%G %V %u %.9f", "%G %V %u .123456000"),
    ("%_d %-m %f", "%_d %-m 123456"),
    ("日期 %Y %f", "日期 %Y 123456"),
    ("a\0%Y %f", "a\0%Y 123456"),
])
def test_non_numeric_and_platform_forms_keep_the_full_mature_call(fmt, expanded):
    scalar = pd.Timestamp("2024-01-02 03:04:05.123456")
    source = Pddt([scalar], unit="us")
    try:
        expected = scalar.strftime(expanded)
    except Exception as original:
        with pytest.raises(type(original)):
            source.strftime(fmt)
    else:
        assert source.strftime(fmt).tolist() == [expected]


@pytest.mark.parametrize("zone", [timezone(timedelta(microseconds=1)),
                                  timezone(timedelta(hours=8), "时区"),
                                  timezone(timedelta(hours=8), "a\0b"),
                                  timezone(timedelta(hours=1), "\ud800")])
def test_unusual_fixed_offsets_and_names_keep_mature_formatting(zone):
    source = Pddt(["2024-01-02 03:04:05.123456"], tz=zone, unit="us")
    scalar = pd.Timestamp(source.asi8[0], unit="us", tz=source.tz)
    expanded = "%Y %z %Z " + f"{scalar.microsecond:06d}"
    assert source.strftime("%Y %z %Z %f").tolist() == [scalar.strftime(expanded)]
