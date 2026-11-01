"""Whole-hour calendar shifts preserve source fractions and final capacity."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from rstimes import Delta, Pddt


@pytest.mark.parametrize("unit,fraction", [("s", ""), ("ms", ".123"), ("us", ".123456"), ("ns", ".123456789")])
@pytest.mark.parametrize("zone", [None, timezone.utc, timezone(timedelta(hours=8)), timezone(timedelta(seconds=1, microseconds=500000))])
@pytest.mark.parametrize("subtract,fields,start,end", [
    (False, {"months": 1, "hours": 1}, "2024-01-31T23:34:56", "2024-03-01T00:34:56"),
    (True, {"months": 1, "hours": 1}, "2024-03-31T00:34:56", "2024-02-28T23:34:56"),
    (False, {"month": 2, "day": 29, "hours": 1}, "2024-01-01T23:34:56", "2024-03-01T00:34:56"),
    (False, {"weekday": 0, "hours": 1}, "2024-01-02T23:34:56", "2024-01-01T00:34:56"),
    (False, {"days": -2, "hours": 1}, "2024-01-02T23:34:56", "2024-01-01T00:34:56"),
])
def test_fixed_zone_calendar_shift_keeps_exact_lower_ticks(unit, fraction, zone, subtract, fields, start, end):
    # Derive UTC ticks with integer arithmetic. pandas' Timestamp constructor
    # itself truncates fractional fixed offsets on this supported version.
    offset = timedelta(0) if zone is None else zone.utcoffset(None)
    offset_ns = (offset.days * 86400 + offset.seconds) * 1_000_000_000 + offset.microseconds * 1000
    fraction_ns = int(fraction[1:].ljust(9, "0")) if fraction else 0
    if unit == "s" and offset.microseconds:
        fraction_ns = offset.microseconds * 1000
    scale = {"s": 1_000_000_000, "ms": 1_000_000, "us": 1000, "ns": 1}[unit]

    def native_tick(text):
        delta = datetime.fromisoformat(text) - datetime(1970, 1, 1)
        value = (delta.days * 86400 + delta.seconds) * 1_000_000_000 + fraction_ns - offset_ns
        assert value % scale == 0
        return value // scale

    source, expected = native_tick(start), native_tick(end)
    dates = np.array([source, -(2**63), source], dtype="i8").view(f"datetime64[{unit}]")
    native = pd.DatetimeIndex(dates)
    if zone is not None:
        native = native.tz_localize(timezone.utc).tz_convert(zone)
    x = Pddt(native, unit=unit, name="time")
    before = x.asi8.copy()
    delta = Delta(**fields)
    result = x - delta if subtract else x + delta
    assert isinstance(result, Pddt)
    assert result.unit == unit and result.name == "time" and result.tz == zone
    assert result.asi8.tolist() == [expected, -(2**63), expected]
    np.testing.assert_array_equal(x.asi8, before)


@pytest.mark.parametrize("unit,hour", [("s", 3600), ("ms", 3_600_000), ("us", 3_600_000_000), ("ns", 3_600_000_000_000)])
@pytest.mark.parametrize("upper", [False, True])
def test_fixed_hour_result_checks_final_capacity_and_nat_collision(unit, hour, upper):
    edge = 2**63 - 1 if upper else -(2**63) + 1
    start = edge - hour if upper else edge + hour
    x = Pddt(np.array([start, -(2**63)], dtype="i8"), unit=unit)
    delta = Delta(hours=1)
    actual = x + delta if upper else x - delta
    assert actual.asi8.tolist() == [edge, -(2**63)]
    bad = Pddt(np.array([edge], dtype="i8"), unit=unit)
    with pytest.raises(OverflowError, match="unit|range|coarser"):
        bad + delta if upper else bad - delta
    assert bad.asi8.tolist() == [edge]


def test_fixed_hour_result_rejects_real_pandas_nat_tick():
    x = Pddt(np.array([-(2**63) + 3_600_000_000_000], dtype="i8"), unit="ns")
    with pytest.raises(OverflowError):
        x - Delta(hours=1)
