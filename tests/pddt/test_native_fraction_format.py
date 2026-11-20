"""Numeric fraction output preserves mature platform, timezone and year rules."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from rstimes import Pddt


@pytest.mark.parametrize("values", [[], [None], [None, None],
                                    ["2024-01-02T03:04:05.123456789", None]])
def test_fraction_missing_output_is_float_nan_at_native_and_public_boundaries(values):
    """The private stub describes actual NaN values, not a None conversion."""
    import math
    from rstimes._native import _pddt_strftime, _strftime_prepare

    source = Pddt(values, unit="ns", name="stamp")
    context = _strftime_prepare("%f")
    assert context.modified()
    native = _pddt_strftime(source.asi8.tobytes(), source.unit, source.tz, context)
    public = source.strftime("%f")
    assert public.name == "stamp" and public.dtype == object
    assert len(native) == len(public) == len(values)
    for value, direct, wrapped in zip(values, native, public):
        if value is None:
            assert type(direct) is float and math.isnan(direct)
            assert type(wrapped) is float and math.isnan(wrapped)
        else:
            assert type(direct) is str and direct == "123456789"
            assert type(wrapped) is str and wrapped == "123456789"


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
                                  timezone(timedelta(hours=1), "\ud800"),
                                  timezone(timedelta(hours=8), "été"),
                                  timezone(timedelta(hours=8), "🌏"),
                                  timezone(timedelta(hours=8), "")])
def test_unusual_fixed_offsets_and_names_keep_mature_formatting(zone):
    source = Pddt(["2024-01-02 03:04:05.123456"], tz=zone, unit="us")
    scalar = pd.Timestamp(source.asi8[0], unit="us", tz=source.tz)
    expanded = "%Y %z %Z " + f"{scalar.microsecond:06d}"
    assert source.strftime("%Y %z %Z %f").tolist() == [scalar.strftime(expanded)]


@pytest.mark.parametrize("prefix", ["", "x" * 512])
def test_native_strings_own_each_value_across_scratch_growth_and_missing(prefix):
    source = Pddt(["1000-01-02T03:04:05.123456", None,
                   "9999-12-31T23:59:58.654321", "2000-02-29T12:00:00"], unit="us", name="stamp")
    before = source.asi8.copy()
    result = source.strftime(prefix + "%Y-%m-%d %H:%M:%S%.9f")
    assert result[0] == prefix + "1000-01-02 03:04:05.123456000"
    assert pd.isna(result[1])
    assert result[2] == prefix + "9999-12-31 23:59:58.654321000"
    assert result[3] == prefix + "2000-02-29 12:00:00.000000000"
    assert result.name == "stamp" and result.dtype == object
    np.testing.assert_array_equal(source.asi8, before)
