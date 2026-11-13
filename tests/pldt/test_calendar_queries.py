"""J01/J02/J04: independent query results, dtypes, pairing and clock snapshots."""
from datetime import date
import os
import subprocess
import sys

import numpy as np
import polars as pl
import pytest
from rstimes import Pldt


def tick(value, unit="ns"):
    return int(np.datetime64(value, unit).astype(np.int64))


PROPERTIES = {
    "year": 2024, "month": 2, "day": 29, "hour": 12, "minute": 34,
    "second": 56, "millisecond": 123, "microsecond": 123456,
    "nanosecond": 789, "weekday": 3, "quarter": 1,
    "day_of_year": 60, "days_in_month": 29,
}
METHODS = {
    "isoyear": 2024, "isoweek": 9, "isoweekday": 4, "days_in_year": 366,
    "days_bf_year": date(2024, 1, 1).toordinal() - 1,
    "days_in_quarter": 91, "days_bf_quarter": 0, "day_of_quarter": 60,
    "days_bf_month": 31, "day_of_month": 29,
}


@pytest.mark.parametrize("expr", [False, True])
@pytest.mark.parametrize("name,expected", list(PROPERTIES.items()) + list(METHODS.items()))
def test_each_integer_query_has_independent_value_and_int64_null(expr, name, expected):
    x = Pldt(["2024-02-29T12:34:56.123456789", None], name="time", unit="ns")
    owner = pl.col("time").pldt if expr else x
    got = getattr(owner, name)
    if name in METHODS:
        got = got()
    if expr:
        assert isinstance(got, pl.Expr)
        got = pl.DataFrame({"time": pl.Series(x)}).select(got)["time"]
    assert type(got) is pl.Series
    assert got.dtype == pl.Int64 and got.name == "time"
    assert got.to_list() == [expected, None]
    assert x.to_physical().to_list() == [tick("2024-02-29T12:34:56.123456789"), None]


@pytest.mark.parametrize("method,target,expected", [
    ("is_year", 2024, True), ("is_quarter", 1, True), ("is_month", "February", True),
    ("is_weekday", "Thursday", True), ("is_day", 29, True),
    ("is_month", 13, False), ("is_quarter", -1, False), ("is_weekday", 7, False),
    ("is_day", 0, False), ("is_year", -123, False),
])
def test_condition_target_scalar_and_expression_have_matching_false_null(method, target, expected):
    x = Pldt(["2024-02-29", None], name="time")
    got = getattr(x, method)(target)
    assert got.dtype == pl.Boolean and got.to_list() == [expected, False]
    expr = getattr(pl.col("time").pldt, method)(target)
    assert pl.DataFrame({"time": pl.Series(x)}).select(expr)["time"].to_list() == [expected, False]


@pytest.mark.parametrize("method", ["is_year", "is_quarter", "is_month", "is_weekday", "is_day", "leap_bt_year"])
@pytest.mark.parametrize("source", [[], [None]])
def test_query_targets_are_required_real_integers_even_for_missing_source(method, source):
    x = Pldt(source)
    for invalid in (None, True, np.bool_(False), 1.0, float("nan"), np.datetime64("NaT")):
        with pytest.raises(TypeError):
            getattr(x, method)(invalid)
    if method in ("is_month", "is_weekday"):
        for invalid in ("", "unknown", "oCt"):
            with pytest.raises(ValueError):
                getattr(x, method)(invalid)
    if source:
        with pytest.raises(TypeError):
            getattr(x, method)(pl.Series([None] * len(source), dtype=pl.Int64))
    else:
        assert getattr(x, method)(pl.Series([], dtype=pl.Int64)).to_list() == []


def test_positional_targets_strict_shape_native_null_and_integer_protocol_once():
    x = Pldt(["2024-01-01", "2024-02-02", None], name="time")
    assert x.is_month([1, 2, 3]).to_list() == [True, True, False]
    assert x.is_month(pl.Series(["January", "February", "March"])).to_list() == [True, True, False]
    with pytest.raises(ValueError, match="length|scalar"):
        x.is_month([1])
    with pytest.raises(TypeError):
        x.is_month([1, 2, None])
    calls = []
    class Once:
        def __index__(self):
            calls.append(1)
            return 1
    assert x.is_month(Once()).to_list() == [True, False, False]
    assert calls == [1]
    assert x.is_month((v for v in [1, 2, 3])).to_list() == [True, True, False]
    df = pl.DataFrame({"time": pl.Series(x), "month": [1, 2, 3]})
    assert df.select(pl.col("time").pldt.is_month(pl.col("month")))["time"].to_list() == [True, True, False]
    assert df.select(pl.col("time").pldt.is_month(pl.col("month").min()))["time"].to_list() == [True, False, False]


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
def test_full_valid_min_and_negative_fraction_queries_are_not_missing(unit):
    minimum = -(2**63)
    x = Pldt([minimum, -1, None], unit=unit)
    day = {"ms": 86_400_000, "us": 86_400_000_000, "ns": 86_400_000_000_000}[unit]
    assert x.weekday.to_list() == [(minimum // day + 3) % 7, 2, None]
    assert x.nanosecond.to_list() == [minimum % 1000 if unit == "ns" else 0, 999 if unit == "ns" else 0, None]
    assert x.year.null_count() == 1


def test_leap_count_is_lower_inclusive_nonnegative_and_can_use_each_row():
    x = Pldt(["2020-01-01", "2024-01-01", "2024-01-01", None], name="time")
    assert x.leap_bt_year([2024, 2020, 2024, 0]).to_list() == [1, 1, 0, None]
    assert x.is_leap_year.to_list() == [True, True, True, False]
    assert x.is_long_year().to_list() == [True, False, False, False]
    expr = pl.col("time").pldt.leap_bt_year(pl.col("year"))
    assert pl.DataFrame({"time": pl.Series(x), "year": [2024, 2020, 2024, 0]}).select(expr)["time"].to_list() == [1, 1, 0, None]


def test_iso_struct_has_uint32_children_outer_null_and_signed_year_boundary():
    x = Pldt(["2021-01-01", "2024-02-29", None], name="time")
    got = x.isocalendar()
    assert type(got) is pl.Series
    assert got.dtype == pl.Struct({"year": pl.UInt32, "week": pl.UInt32, "day": pl.UInt32})
    assert got.to_list() == [{"year": 2020, "week": 53, "day": 5}, {"year": 2024, "week": 9, "day": 4}, None]
    assert got.is_null().to_list() == [False, False, True]
    expr = pl.col("time").pldt.isocalendar()
    assert pl.DataFrame({"time": pl.Series(x)}).lazy().select(expr).collect()["time"].equals(got)
    x = Pldt(np.array(["0000-01-04"], dtype="datetime64[us]"))
    assert x.isocalendar().struct.field("year").to_list() == [0]
    x = Pldt(np.array(["0000-01-01"], dtype="datetime64[us]"))
    assert x.year.to_list() == [0] and x.isoyear().to_list() == [-1]
    with pytest.raises(OverflowError, match="UInt32|isoyear"):
        x.isocalendar()


@pytest.mark.parametrize("tz,dst,offset", [(None, [-1, -1], [None, None]), ("UTC", [-1, -1], [0, 0]), ("Etc/GMT-8", [0, 0], [28800, 28800]), ("America/New_York", [0, 1], [-18000, -14400]), ("Europe/Dublin", [1, 0], [0, 3600])])
def test_time_tables_have_fixed_dtypes_dst_and_utc_naive_rules(tz, dst, offset):
    values = [tick("2024-01-15T12:34:56", "us"), tick("2024-07-15T12:34:56", "us"), None]
    x = Pldt(values, unit="us", tz=tz, name="time")
    names = ["tm_year", "tm_mon", "tm_mday", "tm_hour", "tm_min", "tm_sec", "tm_wday", "tm_yday", "tm_isdst"]
    expected_dtype = [pl.Int64, pl.Int8, pl.Int8, pl.Int8, pl.Int8, pl.Int8, pl.Int8, pl.Int16, pl.Int8]
    table = x.timedf()
    assert type(table) is pl.DataFrame and table.columns == names and table.dtypes == expected_dtype
    assert table["tm_isdst"].to_list() == dst + [None]
    assert x.utcoffset_seconds().to_list() == offset + [None]
    assert x.is_dst().to_list() == [v == 1 for v in dst] + [False]
    utc = x.utctimedf()
    assert utc["tm_hour"].to_list() == [12, 12, None]
    assert utc["tm_isdst"].to_list() == [0, 0, None]
    for method in ("timedf", "utctimedf"):
        expr = getattr(pl.col("time").pldt, method)()
        result = pl.DataFrame({"time": pl.Series(x)}).lazy().select(expr).collect()["time"]
        assert result.struct.unnest().equals(getattr(x, method)())
        assert result.is_null().to_list() == [False, False, True]


def test_clock_query_reference_is_once_at_expression_creation_and_eager_when_needed(monkeypatch):
    import rstimes.pldt as module
    calls = []
    current = [100_000_000_000]
    def clock():
        calls.append(current[0])
        return (0, current[0])
    monkeypatch.setattr(module, "_pldt_query_clock", clock)
    x = Pldt([101_000_000, None], unit="us", tz="UTC", name="time")
    df = pl.DataFrame({"time": pl.Series(x)})
    expr = pl.col("time").pldt.is_past()
    assert calls == [100_000_000_000]
    current[0] = 200_000_000_000
    for _ in range(2):
        assert df.lazy().select(expr).collect()["time"].to_list() == [False, False]
    assert len(calls) == 1
    assert x.is_past().to_list() == [True, False]
    assert len(calls) == 2
    assert Pldt([], tz="UTC").is_future().to_list() == []
    assert Pldt([None], tz="UTC").is_past().to_list() == [False]
    assert len(calls) == 2
    pl.col("empty").pldt.is_future()
    assert len(calls) == 3
    current[0] = 101_000_000_000
    assert x.is_past().to_list() == [False, False]
    assert x.is_future().to_list() == [False, False]


def test_aware_clock_comparison_does_not_need_local_timezone_and_naive_errors_retry():
    code = """from rstimes import Pldt
import json,os
x=Pldt([0],unit='us',tz='UTC')
assert x.is_past().to_list()==[True]
try:Pldt([0],unit='us').is_past()
except ValueError:pass
else:raise AssertionError('invalid local must fail')
os.environ['TZ']='UTC'
assert Pldt([0],unit='us').is_past().to_list()==[True]
print('PASS')
"""
    env = os.environ.copy()
    env["TZ"] = "invalid-zone-for-query"
    result = subprocess.run([sys.executable, "-c", code], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_native_date_queries_and_chunked_grouped_targets_do_not_guess_text():
    source = pl.Series("time", [date(2024, 1, 1), None, date(2024, 2, 2)])
    assert source.pldt.weekday.to_list() == [0, None, 4]
    assert source.pldt.is_month([1, 2, 2]).to_list() == [True, False, True]
    with pytest.raises(TypeError):
        pl.Series(["2024-01-01"]).pldt.is_year(2024)
    source = pl.concat([source.slice(0, 1), source.slice(1)], rechunk=False)
    df = pl.DataFrame({"time": source, "group": [1, 1, 2], "year": [2024, 2025, 2024]})
    expr = pl.col("time").pldt.is_year(pl.col("year").min()).over("group")
    assert df.lazy().select(expr).collect(engine="streaming")["time"].to_list() == [True, False, True]


@pytest.mark.parametrize("key", ["UTC", "Etc/UTC", "Etc/GMT", "GMT"])
def test_utc_alias_metadata_has_the_normalized_standard_utc_time_table_role(key):
    source = pl.Series("time", [0, None], dtype=pl.Datetime("us", key))
    assert source.pldt.timedf()["tm_isdst"].to_list() == [-1, None]
    assert source.pldt.utctimedf()["tm_isdst"].to_list() == [0, None]


def test_fraction_fields_do_not_require_regional_calendar_capacity():
    values = [-(2**63), 2**63 - 1, None]
    x = Pldt(values, unit="us", tz="America/New_York", name="time")
    expected = {
        "millisecond": [v // 1000 % 1000 if v is not None else None for v in values],
        "microsecond": [v % 1_000_000 if v is not None else None for v in values],
        "nanosecond": [0, 0, None],
    }
    df = pl.DataFrame({"time": pl.Series(x)})
    for name, answer in expected.items():
        assert getattr(x, name).to_list() == answer
        expr = getattr(pl.col("time").pldt, name)
        assert df.lazy().select(expr).collect()["time"].to_list() == answer
