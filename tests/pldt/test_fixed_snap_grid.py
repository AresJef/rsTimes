"""Independent candidate enumeration for the regular native Snap lattice."""
from datetime import date, timedelta, timezone

import numpy as np
import polars as pl
import pytest

from rstimes import Pldt
from rstimes._optional import PANDAS


QUANTUM = {"s": 10**9, "ms": 10**6, "us": 1000, "ns": 1}
DAY = 86_400 * 10**9


def nearest_candidates(tick, unit, period, offset_ns):
    if tick is None:
        return None
    anchor, step = {
        "h": (0, 3600 * 10**9), "D": (0, DAY), "W": (-3 * DAY, 7 * DAY),
        "Monday": (-3 * DAY, 7 * DAY), "ms": (0, 10**6),
    }[period]
    quantum = QUANTUM[unit]
    wall = tick * quantum + offset_ns
    n = (wall - anchor) // step
    candidates = [-( -(anchor + k * step - offset_ns) // quantum) for k in range(n - 1, n + 3)]
    return min(candidates, key=lambda value: (abs(value - tick), -value))


def pddt_source(ticks, unit, zone):
    from rstimes import Pddt
    raw = np.array([-(2**63) if value is None else value for value in ticks], dtype="i8")
    result = Pddt(raw.view("datetime64[" + unit + "]"), name="time")
    return result if zone is None else result.tz_localize(timezone.utc).tz_convert(zone)


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
@pytest.mark.parametrize("period", ["h", "D", "W", "Monday", "ms"])
@pytest.mark.parametrize("zone, key, offset_ns", [
    (None, None, 0), (timezone.utc, "UTC", 0),
    (timezone(timedelta(hours=8)), "Etc/GMT-8", 28_800_000_000_000),
])
def test_regular_grid_matches_enumerated_starts_in_each_native_unit(unit, period, zone, key, offset_ns):
    day = DAY // QUANTUM[unit]
    raw = [-4 * day - 1, -1, 0, day // 2, 3 * day + day // 2, None]
    expected = [nearest_candidates(value, unit, period, offset_ns) for value in raw]
    source = pl.Series("time", raw, dtype=pl.Datetime(unit, key))
    before = source.to_physical().to_list()
    eager = Pldt(source).snap(period)
    expr = pl.DataFrame({"time": source}).lazy().select(pl.col("time").pldt.snap(period)).collect()["time"]
    assert type(eager) is Pldt and type(expr) is pl.Series
    for result in [eager, expr]:
        assert result.dtype == source.dtype and result.name == "time"
        assert result.to_physical().to_list() == expected
    assert source.to_physical().to_list() == before
    if PANDAS is not None:
        pandas = pddt_source(raw, unit, zone)
        result = pandas.snap(period)
        assert result.unit == unit and result.name == "time"
        assert [None if value == -(2**63) else value for value in result.asi8.tolist()] == expected
        assert pandas.asi8.tolist() == [-(2**63) if value is None else value for value in raw]


def test_pddt_seconds_and_fractional_fixed_offset_keep_the_existing_lattice():
    if PANDAS is None:
        pytest.skip("Pddt seconds/fractional-offset case needs optional pandas")
    raw = [-86_400, -1, 0, 43_200, None]
    for period in ["h", "D", "Monday", "ms"]:
        zone = timezone(timedelta(microseconds=1))
        source = pddt_source(raw, "s", zone)
        expected = [nearest_candidates(value, "s", period, 1000) for value in raw]
        assert [None if value == -(2**63) else value for value in source.snap(period).asi8.tolist()] == expected


def test_native_date_source_promotes_once_to_the_expected_millisecond_dates():
    source = pl.Series("time", [date(1969, 12, 31), date(1970, 1, 1), date(1970, 1, 4), None], dtype=pl.Date)
    expected = [-259_200_000, -259_200_000, 345_600_000, None]
    for result in [source.pldt.snap("Monday"),
                   pl.DataFrame({"time": source}).lazy().select(pl.col("time").pldt.snap("Monday")).collect()["time"]]:
        assert result.dtype == pl.Datetime("ms")
        assert result.to_physical().to_list() == expected


def test_nearest_outside_capacity_is_not_clipped_and_valid_min_is_not_missing():
    for tick in [-(2**63), 2**63 - 1]:
        source = Pldt(pl.Series("time", [tick], dtype=pl.Datetime("ns")))
        assert source.snap("ns").to_physical().to_list() == [tick]
        with pytest.raises(OverflowError, match="unit|capacity|range"):
            source.snap("s")
        with pytest.raises(pl.exceptions.ComputeError, match="unit|capacity|range"):
            pl.DataFrame({"time": source}).select(pl.col("time").pldt.snap("s"))
    assert Pldt([None], unit="ns").snap("Monday").to_physical().to_list() == [None]
    if PANDAS is not None:
        source = pddt_source([None], "ns", None)
        assert source.snap("s").isna().tolist() == [True]
