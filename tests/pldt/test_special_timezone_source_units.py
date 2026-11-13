"""A source unit is metadata, not a reason to rebuild its real wall clock."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
import pytest

pd = pytest.importorskip("pandas", reason="pandas source unit integration requires optional pandas")
from rstimes import Pldt
from test_timezone_origin_and_roles import file_zone, PassiveZone


def source_at_noon(unit, kind=ZoneInfo, year=2024):
    # Attach the real source metadata to already defined UTC ticks, avoiding
    # pandas' from_file scalar-construction/boxing behavior as an oracle.
    instant = datetime(year, 1, 1, 10) - datetime(1970, 1, 1)
    nanos = instant // timedelta(microseconds=1) * 1000
    divisor = {"s": 1_000_000_000, "ms": 1_000_000, "us": 1000, "ns": 1}[unit]
    ticks = nanos // divisor
    index = pd.DatetimeIndex(np.array([ticks], dtype=f"datetime64[{unit}]"))
    result = index.tz_localize(timezone.utc).tz_convert(file_zone(kind))
    assert result.unit == unit and result.asi8.tolist() == [ticks]
    return result


@pytest.mark.parametrize("kind", [ZoneInfo, PassiveZone])
@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_nonempty_source_unit_never_reboxes_real_wall_fields(kind, unit):
    source = source_at_noon(unit, kind)
    out = Pldt.fromdatetime(source, tz="UTC")
    chosen = "ms" if unit == "s" else unit
    divisor = {"ms": 1_000_000, "us": 1000, "ns": 1}[chosen]
    assert out.dtype == pl.Datetime(chosen, "UTC")
    assert out.to_physical().to_list() == [1704110400000000000 // divisor]
    clock = Pldt.combine([datetime(2024, 1, 2)], source, tz="UTC", unit=chosen)
    assert clock.to_physical().to_list() == [1704196800000000000 // divisor]


@pytest.mark.parametrize("unit", ["s", "ms", "us"])
def test_real_source_adapter_keeps_supported_wide_year(unit):
    source = source_at_noon(unit, year=2500)
    out = Pldt.fromdatetime(source, tz="UTC")
    chosen = "ms" if unit == "s" else unit
    microseconds = (datetime(2500, 1, 1, 12) - datetime(1970, 1, 1)) // timedelta(microseconds=1)
    assert out.dtype == pl.Datetime(chosen, "UTC")
    assert out.to_physical().to_list() == [microseconds // (1000 if chosen == "ms" else 1)]


@pytest.mark.parametrize("offset_us", [-1, 1])
@pytest.mark.parametrize("tick", [-7, 7])
@pytest.mark.parametrize("factory", ["fromdatetime", "fromdate", "combine"])
def test_real_source_protocol_receives_full_fraction_and_preserves_day(offset_us, tick, factory):
    calls = []
    offset = timedelta(microseconds=offset_us)

    class FractionalZone(ZoneInfo):
        def utcoffset(self, value):
            return offset

        def dst(self, value):
            return timedelta(0)

        def fromutc(self, value):
            assert value.tzinfo is self
            calls.append(value.microsecond)
            return datetime.__add__(value, offset)

    zone = FractionalZone.no_cache("UTC")
    source = pd.DatetimeIndex(np.array([tick, np.iinfo("int64").min], dtype="datetime64[ns]"))
    source = source.tz_localize(timezone.utc).tz_convert(zone)
    calls.clear()
    local_ns = tick + offset_us * 1000
    day_ns = 86_400_000_000_000
    if factory == "combine":
        out = Pldt.combine([datetime(1970, 1, 2), None], source, tz="UTC", unit="ns")
        expected = day_ns + local_ns % day_ns
    else:
        out = getattr(Pldt, factory)(source, tz="UTC", unit="ns")
        expected = local_ns if factory == "fromdatetime" else local_ns // day_ns * day_ns
    assert out.to_physical().to_list() == [expected, None]
    assert calls == [(tick % 1_000_000_000) // 1000]
