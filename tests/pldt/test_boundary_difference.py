"""J03: native boundary counts retain all units, coordinate domains and validity."""
from datetime import datetime, timezone, timedelta

import numpy as np
import polars as pl
import pytest
from rstimes import Pldt

SCALES = {"ms": 1_000_000, "us": 1000, "ns": 1}
STEPS = {"D": 86_400_000_000_000, "h": 3_600_000_000_000, "min": 60_000_000_000, "s": 1_000_000_000, "ms": 1_000_000, "us": 1000, "ns": 1}


@pytest.mark.parametrize("storage", SCALES)
@pytest.mark.parametrize("unit,step", STEPS.items())
def test_signed_fixed_boundary_counts_have_independent_integer_answers(storage, unit, step):
    values = [-86401, -1001, -1, 0, 1, 1001, 86401]
    x = Pldt(values + [None], unit=storage, name="time")
    expected = [v * SCALES[storage] // step for v in values] + [None]
    result = x.pldt.diff(np.datetime64(0, "ns"), unit)
    assert type(result) is pl.Series and result.dtype == pl.Int64 and result.name == "time"
    assert result.to_list() == expected
    expr = pl.col("time").pldt.diff(np.datetime64(0, "ns"), unit)
    assert pl.DataFrame({"time": pl.Series(x)}).select(expr)["time"].to_list() == expected
    assert x.dtype == pl.Datetime(storage)


@pytest.mark.parametrize("storage", SCALES)
@pytest.mark.parametrize("unit", ["Y", "Q", "M", "W"])
def test_calendar_boundary_counts_use_wide_signed_calendar_without_datetime(storage, unit):
    data = np.array(["0000-01-01", "-0001-12-31", "2024-02-29", "12345-05-06"] if storage != "ns" else ["1969-12-31", "1970-01-01", "2024-02-29", "2200-05-06"], dtype=f"datetime64[{storage}]")
    target = np.datetime64("1970-05-01", "us")
    def indices(array):
        if unit == "Y":
            return array.astype("datetime64[Y]").astype(np.int64)
        if unit in ("Q", "M"):
            month = array.astype("datetime64[M]").astype(np.int64)
            return month // 3 if unit == "Q" else month
        return (array.astype("datetime64[D]").astype(np.int64) + 3) // 7
    expected = (indices(data) - indices(np.array([target]))[0]).tolist()
    x = Pldt(data, name="time")
    assert x.pldt.diff(target, unit).to_list() == expected
    assert pl.DataFrame({"time": pl.Series(x)}).lazy().select(pl.col("time").pldt.diff(target, unit)).collect()["time"].to_list() == expected


@pytest.mark.parametrize("absolute", [False, True, np.bool_(True)])
@pytest.mark.parametrize("inclusive", ["one", "both", "neither"])
def test_absolute_precedes_inclusive_with_zero_neither_negative_one(absolute, inclusive):
    x = Pldt([-2, -1, 0, 1, 2, None], unit="ns", name="time")
    expected = []
    adjust = {"one": 0, "both": 1, "neither": -1}[inclusive]
    for value in [-2, -1, 0, 1, 2]:
        value = abs(value) if absolute else value
        expected.append(value + (-adjust if value < 0 else adjust))
    assert x.pldt.diff(np.datetime64(0, "ns"), "ns", absolute, inclusive).to_list() == expected + [None]


def test_full_int64_results_missing_and_final_only_overflow():
    x = Pldt([-(2**63), 2**63 - 1, None], unit="ns", name="time")
    assert x.pldt.diff(np.datetime64(0, "ns"), "ns").to_list() == [-(2**63), 2**63 - 1, None]
    with pytest.raises(OverflowError):
        x.pldt.diff(np.datetime64(0, "ns"), "ns", absolute=True)
    # A result just beyond int64 becomes legal after the requested inclusive adjustment.
    x = Pldt([2**63 - 1], unit="ns")
    assert x.pldt.diff(np.datetime64(-1, "ns"), "ns", inclusive="neither").to_list() == [2**63 - 1]
    with pytest.raises(OverflowError):
        x.pldt.diff(np.datetime64(-1, "ns"), "ns")
    assert Pldt([0, None], unit="us").pldt.diff(np.datetime64("NaT", "ns"), "ns").to_list() == [None, None]


def test_numeric_targets_mean_seconds_and_do_not_create_an_intermediate_date_column():
    x = Pldt([2_000_000, None], unit="us", name="time")
    assert x.pldt.diff(1, "s").to_list() == [1, None]
    assert x.pldt.diff(pl.Series([1, 1]), "ns").to_list() == [1_000_000_000, None]
    assert Pldt([1], unit="ns").pldt.diff(1e-9, "ns").to_list() == [0]
    # The absolute target cannot fit Datetime(ns), but the day difference can.
    target = np.datetime64(2**63 - 1, "s")
    assert Pldt([0], unit="ns").pldt.diff(target, "D").to_list() == [-((2**63 - 1) * 1_000_000_000 // STEPS["D"])]
    assert Pldt([0], unit="ns").pldt.diff(pl.Series([2**64 - 1], dtype=pl.UInt64), "D").to_list() == [-((2**64 - 1) * 1_000_000_000 // STEPS["D"])]


def test_aware_uses_utc_boundaries_and_unencodable_source_offsets_need_no_datetime():
    x = Pldt(["1970-01-01T08:00", None], unit="ns", tz="Asia/Shanghai", name="time")
    target = datetime(1970, 1, 1, 5, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert x.pldt.diff(target, "D").to_list() == [0, None]
    assert x.pldt.diff("1970-01-01T05:30+05:30", "ns").to_list() == [0, None]
    df = pl.DataFrame({"time": pl.Series(x), "target": ["1970-01-01T05:30+05:30", None]})
    assert df.select(pl.col("time").pldt.diff(pl.col("target"), "ns"))["time"].to_list() == [0, None]
    with pytest.raises(TypeError, match="naive|aware"):
        x.pldt.diff(0, "D")
    with pytest.raises(TypeError, match="naive|aware"):
        Pldt([], unit="ns", tz="UTC").pldt.diff(pl.Series([], dtype=pl.Datetime("ns")), "D")


@pytest.mark.parametrize("code", ["Y", "M", "W", "D", "h", "m", "s", "ms", "us", "ns"])
def test_numpy_target_units_multipliers_endian_and_strides(code):
    x = Pldt([0, None], unit="ns", name="time")
    values = np.array([np.datetime64(0, code), np.datetime64(0, code)], dtype=f"datetime64[{code}]")
    for target in (values, values.astype(values.dtype.newbyteorder(">")), np.repeat(values, 2)[::2]):
        assert x.pldt.diff(target, "D").to_list() == [0, None]
    multiplied = np.array([0, 1], dtype=f"datetime64[3{code}]")
    assert x.pldt.diff(multiplied, "D").to_list()[0] == 0


def test_targets_strict_pairing_options_and_external_read_once():
    x = Pldt(["2024-01-01", "2024-01-02", None], name="time")
    assert x.pldt.diff(["2024-01-01", "2024-01-01", None], "D").to_list() == [0, 1, None]
    assert x.pldt.diff((v for v in ["2024-01-01", "2024-01-01", None]), "D").to_list() == [0, 1, None]
    with pytest.raises(ValueError, match="length|scalar"):
        x.pldt.diff(["2024-01-01"], "D")
    for source in (Pldt([]), Pldt([None])):
        for bad in (True, np.bool_(True), b"2024-01-01", timedelta(days=1)):
            with pytest.raises(TypeError):
                source.pldt.diff(bad, "D")
        for bad in (1, None, "yes"):
            with pytest.raises(TypeError):
                source.pldt.diff(None, "D", absolute=bad)
        with pytest.raises(ValueError):
            source.pldt.diff(None, "invalid")
        with pytest.raises(ValueError):
            source.pldt.diff(None, "D", inclusive="invalid")
    calls = []
    class Index:
        def __index__(self):
            calls.append(1)
            return 0
    assert Pldt([0, 1], unit="us").pldt.diff(Index(), "us").to_list() == [0, 1]
    assert calls == [1]


def test_native_expr_aggregation_chunks_streaming_and_original_series_diff():
    source = pl.concat([pl.Series("time", [0, 1], dtype=pl.Datetime("us")), pl.Series("time", [2, None], dtype=pl.Datetime("us"))], rechunk=False)
    df = pl.DataFrame({"time": source, "target": [0, 0, 0, 0], "group": [1, 1, 2, 2]})
    expr = pl.col("time").pldt.diff(pl.col("target").min(), "us")
    assert df.lazy().select(expr).collect(engine="streaming")["time"].to_list() == [0, 1, 2, None]
    assert df.select(expr.over("group"))["time"].to_list() == [0, 1, 2, None]
    assert Pldt.diff is pl.Series.diff
    assert Pldt(source).diff().dtype == pl.Duration("us")


def test_eager_iterator_stops_at_first_excess_target_without_reading_its_protocol():
    seen = []
    class NeverRead:
        def __index__(self):
            raise AssertionError("the excess target value must not be decoded")
    def values():
        for item in (0, 0, NeverRead(), NeverRead()):
            seen.append(1)
            yield item
    with pytest.raises(ValueError, match="length"):
        Pldt([0, 1], unit="us").pldt.diff(values(), "us")
    assert seen == [1, 1, 1]


def test_bad_text_and_actual_external_errors_are_not_hidden_by_missing_sources():
    error = RuntimeError("real UTC offset callback failure")
    calls = []
    class Target(datetime):
        def utcoffset(self):
            calls.append(1)
            raise error
    x = Pldt([None], tz="UTC", unit="ns")
    with pytest.raises(RuntimeError) as caught:
        x.pldt.diff(Target(2024, 1, 1, tzinfo=timezone.utc), "D")
    assert caught.value is error and calls == [1]
    assert x.to_physical().to_list() == [None]
    with pytest.raises(ValueError):
        x.pldt.diff("definitely-not-a-date", "D")
    with pytest.raises(ValueError):
        x.pldt.diff(pl.Series(["definitely-not-a-date"]), "D")


def test_optional_pandas_targets_preserve_nanoseconds_timezone_and_nullable_numbers():
    pd = pytest.importorskip("pandas")
    x = Pldt([1, 2, None], unit="ns", name="time")
    target = pd.DatetimeIndex(np.array([1, 1, -(2**63)], dtype="int64").view("datetime64[ns]"))
    assert x.pldt.diff(target, "ns").to_list() == [0, 1, None]
    assert x.pldt.diff(pd.Series(target, index=[9, 8, 7]), "ns").to_list() == [0, 1, None]
    numeric = pd.Series(pd.array([0, 0, None], dtype="Int64"))
    assert x.pldt.diff(numeric, "ns").to_list() == [1, 2, None]
    aware = Pldt([1], unit="ns", tz="UTC")
    assert aware.pldt.diff(pd.DatetimeIndex([pd.Timestamp(1, unit="ns", tz="Asia/Shanghai")]), "ns").to_list() == [0]
