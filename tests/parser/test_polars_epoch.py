"""Native Polars validity and wide epoch coordinates (N02, decision D01)."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pytest

pl = pytest.importorskip("polars")
from rstimes import parse, parse_to_epoch

MIN = -(1 << 63)
MAX = (1 << 63) - 1
SCALE = {"ms": 1_000_000, "us": 1000, "ns": 1}


@pytest.mark.parametrize("unit", ("ms", "us", "ns"))
@pytest.mark.parametrize("tick", (MIN, MIN + 1, 0, MAX))
@pytest.mark.parametrize("ignoretz", (False, True))
def test_native_valid_ticks_use_independent_validity(unit: str, tick: int, ignoretz: bool) -> None:
    source = pl.Series("time", [tick], dtype=pl.Datetime(unit))
    assert parse_to_epoch(source, "ns", ignoretz=ignoretz) == tick * SCALE[unit]


@pytest.mark.parametrize("unit", ("ms", "us", "ns"))
@pytest.mark.parametrize("tick", (MIN, MAX))
@pytest.mark.parametrize("zone,offset", (("Etc/GMT-8", 28800), ("Etc/GMT+8", -28800)))
def test_fixed_wall_coordinate_is_wide_before_projection(unit: str, tick: int, zone: str, offset: int) -> None:
    source = pl.Series("time", [tick], dtype=pl.Datetime(unit, zone))
    expected = tick * SCALE[unit] + offset * 1_000_000_000
    assert parse_to_epoch(source, "ns", ignoretz=True) == expected
    assert parse_to_epoch(source, "ns") == tick * SCALE[unit]


@pytest.mark.parametrize("tick,zone", ((MAX, "Asia/Shanghai"), (MIN, "America/New_York")))
def test_regional_wall_offset_uses_integer_epoch(tick: int, zone: str) -> None:
    source = pl.Series("time", [tick], dtype=pl.Datetime("ns", zone))
    instant = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=tick // 1_000_000_000)
    offset = instant.astimezone(ZoneInfo(zone)).utcoffset()
    assert offset is not None
    seconds = offset.days * 86400 + offset.seconds
    expected = tick + seconds * 1_000_000_000
    assert parse_to_epoch(source, "ns", ignoretz=True) == expected


@pytest.mark.parametrize("unit", ("ms", "us"))
@pytest.mark.parametrize("year,days", ((10000, 2932897), (12000, 3663382), (25000, 8411535)))
def test_regional_wall_keeps_polars_wide_year_capacity(unit: str, year: int, days: int) -> None:
    # Days since1970 are independent proleptic Gregorian answers, not values
    # produced by either parser. January in New York has a five-hour offset.
    tick = days * 86_400_000_000_000 // SCALE[unit]
    source = pl.Series("time", [tick], dtype=pl.Datetime(unit, "America/New_York"))
    assert parse_to_epoch(source, "ns", ignoretz=True) == tick * SCALE[unit] - 18_000_000_000_000
    assert parse_to_epoch(source, "ns") == tick * SCALE[unit]


@pytest.mark.parametrize("unit", ("ms", "us", "ns"))
def test_true_polars_null_still_has_no_epoch(unit: str) -> None:
    source = pl.Series("time", [None], dtype=pl.Datetime(unit))
    with pytest.raises(ValueError, match="null"):
        parse_to_epoch(source, "ns")


@pytest.mark.parametrize("unit", ("ms", "us", "ns"))
def test_numpy_min_remains_nat(unit: str) -> None:
    with pytest.raises(ValueError, match="NaT"):
        parse_to_epoch(np.datetime64(MIN, unit), "ns")


@pytest.mark.parametrize("size", (0, 2))
def test_polars_epoch_requires_one_value(size: int) -> None:
    source = pl.Series("time", [0] * size, dtype=pl.Datetime("ns"))
    with pytest.raises(ValueError, match="one value"):
        parse_to_epoch(source, "ns")


@pytest.mark.parametrize("source", (pl.Series("n", [1]), pl.Series("text", ["2024-01-01"])))
def test_non_datetime_series_is_rejected(source: object) -> None:
    with pytest.raises(TypeError, match="Datetime"):
        parse_to_epoch(source, "ns")


class ExportedDates(pl.Series):
    calls = 0

    def to_numpy(self, *args: object, **kwargs: object) -> np.ndarray:
        self.calls += 1
        return np.array([123], dtype="datetime64[ns]")


def test_native_input_reads_stored_column_instead_of_export_override() -> None:
    source = ExportedDates("time", [0], dtype=pl.Datetime("ns"))
    assert parse_to_epoch(source, "ns") == 0
    assert source.calls == 0


def test_explicit_export_still_selects_its_actual_value() -> None:
    source = ExportedDates("time", [0], dtype=pl.Datetime("ns"))
    exported = source.to_numpy()[0]
    assert parse_to_epoch(exported, "ns") == 123
    assert source.calls == 1


def test_native_value_does_not_prepare_unused_default() -> None:
    source = pl.Series("time", [0], dtype=pl.Datetime("ns"))
    assert parse_to_epoch(source, "ns", default=object()) == 0


def test_shared_reader_does_not_widen_parse_input_contract() -> None:
    source = pl.Series("time", [0], dtype=pl.Datetime("ns"))
    with pytest.raises(TypeError):
        parse(source)
