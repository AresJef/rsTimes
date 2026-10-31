"""N01/C04/E04/D04/E05/F01 approved shared changes with independent answers."""
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import polars as pl
import pytest

from rstimes import Pddt

MIN = -(2**63)
DAY_NS = 86400 * 10**9


def ticks(value):
    return value.asi8.tolist()


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
@pytest.mark.parametrize("factory", [Pddt, Pddt.parse, Pddt.fromdatetime])
def test_valid_polars_min_is_not_nat_before_final_target(factory, unit):
    source = pl.Series("dates", [MIN, None, MIN + 1, 0], dtype=pl.Datetime(unit))
    with pytest.raises(OverflowError):
        factory(source, unit=unit)
    assert source.is_null().to_list() == [False, True, False, False]
    assert source.cast(pl.Int64).to_list() == [MIN, None, MIN + 1, 0]


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
def test_real_null_is_preserved_and_bare_pandas_min_keeps_its_contract(unit):
    source = pl.Series("dates", [None, MIN + 1, 0], dtype=pl.Datetime(unit))
    out = Pddt(source)
    assert out.unit == unit
    assert ticks(out) == [MIN, MIN + 1, 0]
    assert out.isna().tolist() == [True, False, False]
    assert Pddt([MIN], unit=unit).isna().tolist() == [True]


def test_final_timezone_processing_may_rescue_valid_min_and_coarsening_must_be_exact():
    source = pl.Series("dates", [MIN, None], dtype=pl.Datetime("ns"))
    out = Pddt(source, tz=timezone(-timedelta(hours=1)))
    assert ticks(out) == [MIN + 3600 * 10**9, MIN]
    with pytest.raises(ValueError, match="preserve|precision"):
        Pddt(source, unit="us")
    aware = source.dt.replace_time_zone("UTC")
    with pytest.raises(OverflowError):
        Pddt(aware, tz=timezone(-timedelta(hours=1)))


def test_fromdate_and_combine_use_real_min_fields_before_target_capacity():
    source = pl.Series("clock", [MIN, None], dtype=pl.Datetime("ns"))
    dates = Pddt.fromdate(source, unit="us")
    assert dates[0] == pd.Timestamp("1677-09-21 00:00:00").as_unit("us")
    assert dates.isna().tolist() == [False, True]
    out = Pddt.combine(date(2024, 1, 2), source, unit="ns")
    epoch_days = (date(2024, 1, 2) - date(1970, 1, 1)).days
    assert ticks(out) == [epoch_days * DAY_NS + MIN % DAY_NS, MIN]


def test_diff_and_datetime_subtraction_do_not_swallow_valid_polars_min():
    source = pl.Series("target", [MIN, None], dtype=pl.Datetime("ns"))
    left = Pddt([MIN + 1, 0], unit="ns")
    difference = left - source
    assert difference.asi8.tolist() == [1, MIN]
    result = Pddt([0, 0], unit="ns").diff(source, "us")
    assert result[0] == -(MIN // 1000)
    assert pd.isna(result[1])


@pytest.mark.parametrize("values", [[], [None], [None, None]])
@pytest.mark.parametrize("zone", ["UTC", "Asia/Shanghai"])
def test_combine_preserves_known_clock_zone_when_empty_or_all_null(values, zone):
    clocks = pl.Series("clock", values, dtype=pl.Datetime("ns", zone))
    out = Pddt.combine(date(2024, 1, 2), clocks)
    assert out.unit == "us"
    assert str(out.tz) == zone
    assert out.name == "clock"
    assert out.isna().tolist() == [True] * len(values)
    override = Pddt.combine(date(2024, 1, 2), clocks, tz="Europe/Paris")
    assert str(override.tz) == "Europe/Paris"


@pytest.mark.parametrize("kind", ["iso", "format"])
def test_text_factories_accept_target_tz_and_preserve_real_instants(kind):
    if kind == "iso":
        out = Pddt.fromisoformat(["2024-01-02T12:30+08:00", "2024-01-02T13:30+09:00"], tz="UTC", unit="us")
    else:
        out = Pddt.strptime(["2024-01-02 12:30+0800", "2024-01-02 13:30+0900"], "%Y-%m-%d %H:%M%z", tz="UTC", unit="us")
    expected = pd.Timestamp("2024-01-02T04:30Z").as_unit("us").value // 1000
    assert ticks(out) == [expected, expected]
    assert str(out.tz) == "UTC"


@pytest.mark.parametrize("kind", ["iso", "format"])
def test_text_factory_target_localization_uses_explicit_dst_policy(kind):
    if kind == "iso":
        call = lambda **kw: Pddt.fromisoformat("2024-03-10T02:30", size=1, tz="America/New_York", **kw)
    else:
        call = lambda **kw: Pddt.strptime("2024-03-10 02:30", "%Y-%m-%d %H:%M", size=1, tz="America/New_York", **kw)
    with pytest.raises(ValueError):
        call()
    out = call(nonexistent="shift_forward")
    assert (out[0].hour, out[0].minute) == (3, 0)


def test_only_pddt_instance_exposes_field_namespace_and_native_replace_is_inherited():
    x = Pddt(["2024-01-31 12:34:56.123456789"], unit="ns")
    assert not hasattr(pd.DatetimeIndex([]), "pddt")
    with pytest.raises(ValueError):
        x.pddt.replace(month=2)
    out = x.pddt.replace(month=2, day=29)
    assert isinstance(out, Pddt)
    assert out[0] == pd.Timestamp("2024-02-29 12:34:56.123456789")
    assert x.pddt.replace() is x
    assert "replace" not in Pddt.__dict__
    assert hasattr(Pddt, "replace") == hasattr(pd.DatetimeIndex, "replace")
    assert "2024-01-31" in str(x[0])


def test_approved_range_target_and_offset_endpoint_contract_remains():
    out = Pddt.date_range("2024-01-02T12:00+08:00", periods=2, freq="h", tz="UTC")
    assert out[0] == pd.Timestamp("2024-01-02T04:00Z")
    assert out[1] == pd.Timestamp("2024-01-02T05:00Z")


@pytest.mark.parametrize("layout", ["slice", "chunks"])
def test_validity_is_positional_across_bitmap_offsets_and_chunks(layout):
    if layout == "slice":
        source = pl.Series("source", [123, None, MIN, MIN + 1, 0, 456], dtype=pl.Datetime("ns")).slice(1, 4)
    else:
        source = pl.concat([
            pl.Series("source", [None, MIN], dtype=pl.Datetime("ns")),
            pl.Series("source", [MIN + 1, 0], dtype=pl.Datetime("ns")),
        ], rechunk=False)
    assert source.cast(pl.Int64).to_list() == [None, MIN, MIN + 1, 0]
    with pytest.raises(OverflowError):
        Pddt(source)
    out = Pddt(source, tz=timezone(-timedelta(hours=1)))
    assert ticks(out) == [MIN, MIN + 3600 * 10**9, MIN + 1 + 3600 * 10**9, 3600 * 10**9]
    assert source.cast(pl.Int64).to_list() == [None, MIN, MIN + 1, 0]


def test_final_target_collision_is_checked_even_when_source_is_not_min():
    source = pl.Series("source", [MIN + 3600 * 10**9], dtype=pl.Datetime("ns"))
    with pytest.raises(OverflowError):
        Pddt(source, tz=timezone(timedelta(hours=1)))


def test_fromdatetime_reinterprets_aware_wall_fields_before_capacity():
    source = pl.Series("source", [MIN, None], dtype=pl.Datetime("ns", "UTC"))
    out = Pddt.fromdatetime(source, tz=timezone(-timedelta(hours=1)), unit="ns")
    assert ticks(out) == [MIN + 3600 * 10**9, MIN]


@pytest.mark.parametrize("unit", ["ms", "us"])
def test_strptime_target_finishes_before_negative_epoch_precision_reduction(unit):
    out = Pddt.strptime("1969-12-31 23:59:59.9999999999+0000", "%Y-%m-%d %H:%M:%S.%f%z", size=1, tz="UTC", unit=unit)
    assert ticks(out) == [-1]
    assert out.unit == unit
    with pytest.raises(ValueError):
        Pddt.fromisoformat("1969-12-31T23:59:59.999999999Z", size=1, tz="UTC", unit=unit)


def test_iso_zero_year_target_and_empty_policy_are_not_datetime_bounded():
    out = Pddt.fromisoformat("0000-01-01", size=1, tz="UTC", unit="us")
    assert ticks(out) == [-62167219200000000]
    with pytest.raises(ValueError):
        Pddt.fromisoformat([], ambiguous=[True])


@pytest.mark.parametrize("factory", [Pddt.fromseconds, Pddt.frommicroseconds])
def test_native_date_storage_is_not_numeric_factory_input_even_at_min(factory):
    source = pl.Series("date", [MIN, None], dtype=pl.Datetime("ns"))
    with pytest.raises(TypeError):
        factory(source)


def test_pandas_native_whole_value_replace_is_unmodified_when_available():
    if not hasattr(pd.DatetimeIndex, "replace"):
        # pandas2.3/3.0 deliberately have no native whole-value method.
        assert not hasattr(Pddt, "replace")
        return
    data = ["2024-01-01", None, "2024-01-02"]
    x = Pddt(data, unit="ns", name="dates")
    parent = pd.DatetimeIndex(x)
    old, new = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")
    actual = x.replace(old, new)
    expected = parent.replace(old, new)
    assert type(Pddt.replace) is type(pd.DatetimeIndex.replace)
    assert Pddt.replace is pd.DatetimeIndex.replace
    assert actual.equals(expected)
    assert actual.dtype == expected.dtype
    assert actual.asi8.tolist() == expected.asi8.tolist()
    assert actual.name == expected.name
    for value in (x, parent):
        with pytest.raises(TypeError):
            value.replace(day=2)


@pytest.mark.parametrize("as_pldt", [False, True])
def test_internal_date_import_does_not_call_public_guarded_numpy_export(as_pldt):
    class Guarded(pl.Series):
        def to_numpy(self, *args, **kwargs):
            raise AssertionError("public export must not run before target processing")
    data = pl.Series("source", [MIN, None], dtype=pl.Datetime("ns"))
    if as_pldt:
        from rstimes import Pldt
        source = Pldt(data)
    else:
        source = Guarded(data)
    out = Pddt(source, tz=timezone(-timedelta(hours=1)))
    assert ticks(out) == [MIN + 3600 * 10**9, MIN]
    assert source.cast(pl.Int64).to_list() == [MIN, None]
