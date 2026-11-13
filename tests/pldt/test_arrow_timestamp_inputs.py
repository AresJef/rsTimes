"""RV01: timestamp metadata and independent validity survive real pandas inputs."""
from datetime import date

import numpy as np
import polars as pl
import pytest

pd = pytest.importorskip("pandas")
pa = pytest.importorskip("pyarrow", reason="real Arrow-backed pandas input requires optional PyArrow")

from rstimes import Pldt


def arrow_source(values, unit, zone, form):
    dtype = pa.timestamp(unit, tz=zone)
    series = pd.Series(pa.array(values, type=dtype), dtype=pd.ArrowDtype(dtype), name="time")
    if form == "array":
        return series.array
    if form == "index":
        return pd.Index(series.array, name="time")
    return series


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
@pytest.mark.parametrize("zone", [None, "UTC", "Asia/Shanghai"])
@pytest.mark.parametrize("form", ["series", "array", "index"])
@pytest.mark.parametrize("values", [[], [None, None], [1, None, -1], [-(1 << 63), None, (1 << 63) - 1]])
def test_arrow_timestamp_construction_preserves_declared_metadata_and_validity(unit, zone, form, values):
    source = arrow_source(values, unit, zone, form)
    before = source.isna().tolist()
    for make in (Pldt, Pldt.parse):
        out = make(source)
        assert type(out) is Pldt
        assert out.dtype == pl.Datetime(unit, zone)
        assert out.to_physical().to_list() == values
        assert out.is_null().to_list() == [value is None for value in values]
        assert out.name == ("" if form == "array" else "time")
    assert source.isna().tolist() == before


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
@pytest.mark.parametrize("form", ["series", "array"])
@pytest.mark.parametrize("values", [[], [None], [1, None, -1], [-(1 << 63), None, (1 << 63) - 1]])
def test_own_arrow_export_can_reenter_constructor_and_diff_without_nat_collision(unit, form, values):
    x = Pldt(pl.Series("time", values, dtype=pl.Datetime(unit, "UTC")))
    for kwargs in ({"use_pyarrow_extension_array": True}, {"types_mapper": pd.ArrowDtype}):
        exported = x.to_pandas(**kwargs)
        source = exported.array if form == "array" else exported
        restored = Pldt(source)
        assert restored.dtype == pl.Datetime(unit, "UTC")
        assert restored.to_physical().to_list() == values
        expected = [None if value is None else 0 for value in values]
        eager = x.pldt.diff(source, unit)
        expression = pl.col("time").pldt.diff(source, unit)
        lazy = pl.DataFrame({"time": pl.Series(x)}).lazy().select(expression)
        assert lazy.collect_schema()["time"] == pl.Int64
        assert eager.dtype == pl.Int64 and eager.to_list() == expected
        assert lazy.collect()["time"].to_list() == expected
        delta = x - source
        assert delta.dtype == pl.Duration(unit)
        assert delta.to_physical().to_list() == expected


@pytest.mark.parametrize("form", ["series", "array", "index"])
@pytest.mark.parametrize("zone", [None, "UTC", "Asia/Shanghai"])
def test_arrow_datetime_and_date_factories_read_timezone_and_nanoseconds(form, zone):
    values = [1704067200123456789, None, 1704153600987654321]
    source = arrow_source(values, "ns", zone, form)
    out = Pldt.fromdatetime(source, unit="ns")
    assert out.dtype == pl.Datetime("ns", zone)
    assert out.to_physical().to_list() == values
    midnight = Pldt.fromdate(source, unit="ns")
    assert midnight.dtype == pl.Datetime("ns")
    assert midnight.to_physical().to_list() == [1704067200000000000, None, 1704153600000000000]


@pytest.mark.parametrize("form", ["series", "array"])
@pytest.mark.parametrize("values", [[], [None, None]])
def test_empty_or_null_arrow_factory_and_combine_retain_known_clock_timezone(form, values):
    source = arrow_source(values, "ns", "UTC", form)
    for factory in (Pldt.fromdatetime, Pldt.fromdate):
        out = factory(source)
        assert out.dtype == pl.Datetime("ns", "UTC" if factory == Pldt.fromdatetime else None)
        assert out.to_physical().to_list() == values
    combined = Pldt.combine([date(2024, 1, 1)] * len(values), source)
    # No actual nanosecond clock tail: combine's established default is us.
    assert combined.dtype == pl.Datetime("us", "UTC")
    assert combined.to_physical().to_list() == values


@pytest.mark.parametrize("form", ["series", "array"])
@pytest.mark.parametrize("values", [[], [None, None]])
def test_arrow_clock_timezone_reaches_series_and_expr_combine(form, values):
    clock = arrow_source(values, "ns", "UTC", form)
    dates = pl.Series("date", [date(2024, 1, 1)] * len(values), dtype=pl.Date)
    expected = pl.Datetime("us", "UTC")
    eager = dates.pldt.combine(clock)
    assert type(eager) is Pldt and eager.dtype == expected
    assert eager.to_physical().to_list() == values
    lazy = pl.DataFrame({"date": dates}).lazy().select(pl.col("date").pldt.combine(clock))
    assert lazy.collect_schema()["date"] == expected
    assert lazy.collect()["date"].to_physical().to_list() == values


@pytest.mark.parametrize("zone", ["UTC", "Asia/Shanghai"])
def test_arrow_combine_clock_and_date_role_keep_nanosecond_tail(zone):
    clock = arrow_source([1, None, 1001], "ns", zone, "array")
    out = Pldt.combine([date(2024, 1, 1)] * 3, clock, unit="ns")
    assert out.dtype == pl.Datetime("ns", zone)
    assert out.to_physical().to_list() == [1704067200000000001, None, 1704067200000001001]
    dates = arrow_source([1704067200000000000, None], "ns", zone, "series")
    midnight = Pldt.combine(dates, [np.datetime64("1970-01-01T00:00:00", "ns")] * 2, unit="ns")
    assert midnight.dtype == pl.Datetime("ns")
    assert midnight.to_physical().to_list() == [1704067200000000000, None]


def test_arrow_explicit_unit_checks_actual_precision_and_capacity():
    source = arrow_source([1, None, -1], "s", "UTC", "series")
    result = Pldt(source)
    assert result.dtype == pl.Datetime("ms", "UTC")
    assert result.to_physical().to_list() == [1000, None, -1000]
    with pytest.raises(ValueError):
        Pldt(arrow_source([1], "ns", None, "series"), unit="us")
    with pytest.raises(OverflowError):
        Pldt(arrow_source([(1 << 63) - 1], "s", None, "series"))
    with pytest.raises(TypeError):
        Pldt.fromdatetime64(source)


def test_arrow_input_explicit_target_converts_actual_instant():
    source = arrow_source([1, None], "ns", "Asia/Shanghai", "series")
    out = Pldt(source, tz="UTC")
    assert out.dtype == pl.Datetime("ns", "UTC")
    assert out.to_physical().to_list() == [1, None]


def test_chunked_arrow_slice_preserves_owner_and_input_updates_do_not_retarget_result():
    dtype = pa.timestamp("ns", tz="UTC")
    array = pd.arrays.ArrowExtensionArray(pa.chunked_array([
        pa.array([0, -(1 << 63), None], type=dtype),
        pa.array([11, 23, None, 99], type=dtype),
    ]))
    source = pd.Series(array, name="time").iloc[1::2]
    result = Pldt(source, copy=False)
    assert result.dtype == pl.Datetime("ns", "UTC")
    assert result.to_physical().to_list() == [-(1 << 63), 11, None]
    source.iloc[0] = pd.Timestamp(7, unit="ns", tz="UTC")
    assert result.to_physical().to_list() == [-(1 << 63), 11, None]


def test_arrow_datetime_source_keeps_fold_instant_but_explicit_factory_zone_replaces_clock():
    values = [1730611800123456789, 1730615400123456789]
    source = arrow_source(values, "ns", "America/New_York", "series")
    assert Pldt(source).to_physical().to_list() == values
    assert Pldt.fromdatetime(source).to_physical().to_list() == values
    # Both source instants display 01:30 locally; explicit factory UTC keeps
    # that clock, whereas ordinary construction converts the original instant.
    result = Pldt.fromdatetime(source, tz="UTC")
    assert result.to_physical().to_list() == [1730597400123456789] * 2
    assert Pldt(source, tz="UTC").to_physical().to_list() == values


def test_arrow_naive_timestamp_localization_uses_existing_dst_policy():
    import calendar
    from datetime import datetime
    local_tick = calendar.timegm(datetime(2024, 3, 10, 2, 30).timetuple()) * 1_000_000_000 + 789
    source = arrow_source([local_tick], "ns", None, "array")
    with pytest.raises(ValueError):
        Pldt(source, tz="America/New_York")
    out = Pldt(source, tz="America/New_York", nonexistent="NaT")
    assert out.to_physical().to_list() == [None]


@pytest.mark.parametrize("tick", [-9223372036854775, 9223372036854775])
def test_arrow_seconds_at_ms_boundary_scale_exactly(tick):
    source = arrow_source([tick, None], "s", None, "array")
    assert Pldt(source).to_physical().to_list() == [tick * 1000, None]


def test_non_timestamp_arrow_dtypes_keep_their_original_roles():
    dates = pd.Series(pa.array([date(2024, 1, 1), None], type=pa.date32()),
                      dtype=pd.ArrowDtype(pa.date32()))
    assert Pldt(dates).to_physical().to_list() == [1704067200000, None]
    with pytest.raises(TypeError):
        Pldt.fromdatetime(dates)
    boolean = pd.Series([True], dtype=pd.ArrowDtype(pa.bool_()))
    with pytest.raises(TypeError):
        Pldt(boolean)


@pytest.mark.parametrize("form", ["series", "array"])
def test_arrow_targets_preserve_signed_nonzero_differences_and_positional_matching(form):
    x = Pldt(pl.Series("time", [1, None, 29], dtype=pl.Datetime("ns", "UTC")))
    target = arrow_source([11, None, -1], "ns", "UTC", "series")
    target.index = ["third", "first", "second"]
    if form == "array":
        target = target.array
    expected = [-10, None, 30]
    assert x.pldt.diff(target, "ns").to_list() == expected
    result = pl.DataFrame({"time": pl.Series(x)}).lazy().select(pl.col("time").pldt.diff(target, "ns")).collect()
    assert result["time"].to_list() == expected
    assert (x - target).to_physical().to_list() == expected
    with pytest.raises(ValueError):
        x.pldt.diff(target[:1], "ns")


def test_real_arrow_export_exception_is_preserved_and_called_once():
    original = ValueError("actual Arrow exporter")
    calls = []
    class Business(pd.arrays.ArrowExtensionArray):
        def __arrow_array__(self, *args, **kwargs):
            calls.append("export")
            raise original
    source = Business(pa.array([1], type=pa.timestamp("s")))
    with pytest.raises(ValueError) as caught:
        Pldt(source)
    assert caught.value is original
    assert calls == ["export"]


def test_arrow_export_must_match_its_real_declared_timestamp_dtype():
    class Business(pd.arrays.ArrowExtensionArray):
        def __arrow_array__(self, *args, **kwargs):
            return pa.array([1], type=pa.int64())
    with pytest.raises(TypeError, match="declared dtype"):
        Pldt(Business(pa.array([1], type=pa.timestamp("s"))))
