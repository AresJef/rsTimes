"""Independent public answers for native physical tick traversal and exits."""
import pytest

pl = pytest.importorskip("polars")
from rstimes import Pldt


def ticks(value):
    return pl.Series(value).cast(pl.Int64).to_list()


def column(unit, values, chunks, zone=None):
    raw = pl.Series("time", values, dtype=pl.Int64).cast(pl.Datetime(unit, zone))
    if chunks:
        raw = pl.concat([raw.head(3), raw.slice(3)], rechunk=False)
    return raw


@pytest.mark.parametrize("unit", ["us", "ns"])
@pytest.mark.parametrize("chunks", [False, True])
@pytest.mark.parametrize("missing", [False, True])
@pytest.mark.parametrize("utc", [False, True])
@pytest.mark.parametrize("zone", [None, "UTC"])
def test_integer_microseconds_preserve_signed_ticks_nulls_and_name(unit, chunks, missing, utc, zone):
    values = [-(2**63), -(2**63)+1, -1001, -1000, -999, -1, 0, 1, 999, 1000, 1001, 2**63-1]
    if missing:
        values[3] = None
    raw = column(unit, values, chunks, zone)
    x = Pldt(raw)
    divisor = 1000 if unit == "ns" else 1
    expected = [None if value is None else value // divisor for value in values]
    actual = x.tomicroseconds(utc=utc)
    assert type(actual) is pl.Series
    assert actual.dtype == pl.Int64
    assert actual.name == "time"
    assert actual.to_list() == expected
    expression = raw.to_frame().lazy().select(pl.col("time").pldt.tomicroseconds(utc=utc)).collect().to_series()
    assert expression.to_list() == expected
    assert ticks(raw) == values


@pytest.mark.parametrize("unit,precision,factor", [("ms", 0, 1000), ("us", 3, 1000), ("ns", 3, 1_000_000), ("ns", 6, 1000)])
@pytest.mark.parametrize("chunks", [False, True])
@pytest.mark.parametrize("missing", [False, True])
def test_fsp_uses_negative_floor_and_current_tick_unit(unit, precision, factor, chunks, missing):
    values = [-1001*factor-1, -factor-1, -factor, -1, 0, 1, factor-1, factor, factor+1, 123456789]
    if missing:
        values[3] = None
    raw = column(unit, values, chunks)
    expected = [None if value is None else (value // factor) * factor for value in values]
    result = Pldt(raw).fsp(precision)
    assert isinstance(result, Pldt)
    assert result.dtype == raw.dtype
    assert result.name == raw.name
    assert ticks(result) == expected
    expression = raw.to_frame().lazy().select(pl.col("time").pldt.fsp(precision)).collect().to_series()
    assert ticks(expression) == expected
    assert ticks(raw) == values


@pytest.mark.parametrize("unit,precision", [("ms", 0), ("us", 3), ("ns", 3)])
def test_fsp_rejects_actual_floor_below_minimum_without_wrapping(unit, precision):
    raw = column(unit, [None, -(2**63), 0], False)
    with pytest.raises(OverflowError):
        Pldt(raw).fsp(precision)
    assert ticks(raw) == [None, -(2**63), 0]


@pytest.mark.parametrize("chunks", [False, True])
def test_date_days_remain_calendar_days_when_native_traversal_uses_ms(chunks):
    raw = pl.Series("time", [-1, 0, 1, None, 365], dtype=pl.Int32).cast(pl.Date)
    if chunks:
        raw = pl.concat([raw.head(2), raw.slice(2)], rechunk=False)
    assert raw.pldt.year.to_list() == [1969, 1970, 1970, None, 1971]
    assert raw.pldt.weekday.to_list() == [2, 3, 4, None, 4]
    assert raw.pldt.tomicroseconds().to_list() == [-86_400_000_000, 0, 86_400_000_000, None, 31_536_000_000_000]
