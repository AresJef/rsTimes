"""F04/H06/I01-I03: independent period, grid and true-instant answers."""
from datetime import date, datetime, timedelta
from pathlib import Path
import re

import numpy as np
import polars as pl
import pytest
from rstimes import Pldt


def tick(text, unit="ns"):
    return int(np.datetime64(text, unit).astype(np.int64))


def ticks(value):
    return value.to_physical().to_list()


def run(x, method, *args, expr=False, **kwargs):
    if expr:
        value = getattr(pl.col("time").pldt, method)(*args, **kwargs)
        assert isinstance(value, pl.Expr)
        return pl.DataFrame({"time": pl.Series(x)}).lazy().select(value).collect()["time"]
    owner = x.pldt if method in ("round", "ceil", "floor") else x
    return getattr(owner, method)(*args, **kwargs)


@pytest.mark.parametrize("expr", [False, True])
@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
@pytest.mark.parametrize("period,first,last", [
    ("Y", "2024-01-01", "2024-12-31"),
    ("Q", "2024-04-01", "2024-06-30"),
    ("M", "2024-05-01", "2024-05-31"),
    ("W", "2024-05-06", "2024-05-12"),
    ("February", "2024-02-01", "2024-02-29"),
])
def test_calendar_days_and_edges_have_independent_exact_answers(expr, unit, period, first, last):
    # Choose a clock exactly representable at every supported storage unit.
    x = Pldt(["2024-05-07T12:34:56.123", None], unit=unit, name="time")
    before = ticks(x)
    cases = {
        "to_first_of": tick(first + "T12:34:56.123", unit),
        "to_last_of": tick(last + "T12:34:56.123", unit),
        "to_start_of": tick(first, unit),
        "to_end_of": tick(last, unit) + 86_400 * {"ms": 1000, "us": 1_000_000, "ns": 1_000_000_000}[unit] - 1,
    }
    for method, expected in cases.items():
        got = run(x, method, period, expr=expr)
        assert type(got) is (pl.Series if expr else Pldt)
        assert got.name == "time" and got.dtype == x.dtype
        assert ticks(got) == [expected, None]
    assert ticks(x) == before


@pytest.mark.parametrize("expr", [False, True])
def test_named_weekday_is_this_week_and_normalize_is_this_day(expr):
    x = Pldt(["2024-05-07T12:34:56.123456789", None], unit="ns", name="time")
    assert ticks(run(x, "to_start_of", "Friday", expr=expr)) == [tick("2024-05-10"), None]
    assert ticks(run(x, "to_end_of", "Friday", expr=expr)) == [tick("2024-05-11") - 1, None]
    assert ticks(run(x, "normalize", expr=expr)) == [tick("2024-05-07"), None]


@pytest.mark.parametrize("expr", [False, True])
def test_queries_are_boolean_with_false_null_and_do_not_round_trip_dates(expr):
    x = Pldt(["2024-05-01T12:00", "2024-05-31T12:00", None], unit="ns", name="time")
    for method, expected in [
        ("is_first_of", [True, False, False]),
        ("is_last_of", [False, True, False]),
        ("is_start_of", [False, False, False]),
        ("is_end_of", [False, False, False]),
    ]:
        got = run(x, method, "M", expr=expr)
        assert type(got) is pl.Series and got.dtype == pl.Boolean and got.name == "time"
        assert got.to_list() == expected
    limits = Pldt([-(2**63), 2**63 - 1, None], unit="ns", name="time")
    for method in ("is_start_of", "is_end_of"):
        assert run(limits, method, "Y", expr=expr).to_list() == [False, False, False]
    with pytest.raises(OverflowError, match="as_unit"):
        limits.to_start_of("Y")


@pytest.mark.parametrize("storage", ["ms", "us", "ns"])
@pytest.mark.parametrize("period", ["ms", "us", "ns"])
def test_fine_boundaries_use_existing_lattice_without_inventing_tail(storage, period):
    x = Pldt([0, 1, -1, None], unit=storage, name="time")
    quantum = {"ms": 1_000_000, "us": 1000, "ns": 1}
    if quantum[period] <= quantum[storage]:
        for method in ("to_start_of", "to_end_of"):
            assert ticks(run(x, method, period)) == ticks(x)
        for method in ("is_start_of", "is_end_of"):
            assert run(x, method, period).to_list() == [True, True, True, False]
    elif storage == "ns" and period == "us":
        assert ticks(x.to_start_of("us")) == [0, 0, -1000, None]
        assert ticks(x.to_end_of("us")) == [999, 999, -1, None]


@pytest.mark.parametrize("method", [
    "to_first_of", "to_last_of", "to_start_of", "to_end_of",
    "is_first_of", "is_last_of", "is_start_of", "is_end_of", "snap",
])
@pytest.mark.parametrize("values", [[], [None]])
def test_period_options_are_checked_even_when_there_are_no_valid_dates(method, values):
    x = Pldt(values, unit="us")
    for invalid in (None, True, 1, b"D", ["D"], pl.col("x")):
        with pytest.raises(TypeError):
            getattr(x, method)(invalid)
    for invalid in ("", "unknown", "15min", "year", "oCt", " Monday "):
        with pytest.raises(ValueError):
            getattr(x, method)(invalid)
    if "first" in method or "last" in method:
        for invalid in ("D", "h", "Monday"):
            with pytest.raises(ValueError):
                getattr(x, method)(invalid)


def test_boundaries_require_prepared_datetime_not_implicit_date_or_text_parse():
    for x in (pl.Series("time", [date(2024, 1, 2)]), pl.Series("time", ["2024-01-02"])):
        with pytest.raises(TypeError, match="Datetime"):
            x.pldt.normalize()
        with pytest.raises(pl.exceptions.PolarsError, match="Datetime"):
            pl.DataFrame({"time": x}).lazy().select(pl.col("time").pldt.to_start_of("M")).collect_schema()
    # Grid operations can promote native Date without parsing text.
    x = pl.Series("time", [date(2024, 1, 2), None])
    assert x.pldt.snap("D").dtype == pl.Datetime("ms")
    assert x.pldt.fsp(3).dtype == pl.Datetime("ms")


@pytest.mark.parametrize("expr", [False, True])
def test_missing_midnight_and_repeated_clock_edges_obey_real_period(expr):
    x = Pldt(["2018-11-04T12:00", None], tz="America/Sao_Paulo", unit="us", name="time")
    for method in ("normalize", "to_start_of"):
        args = () if method == "normalize" else ("D",)
        got = run(x, method, *args, expr=expr)
        assert got.dtype == x.dtype
        assert ticks(got) == [tick("2018-11-04T03:00", "us"), None]
    # Physical UTC06:30 is the second local01:30, offset -05.
    x = Pldt([tick("2024-11-03T06:30", "us"), None], tz="America/New_York", unit="us", name="time")
    for method, period, expected in [
        ("to_start_of", "h", "2024-11-03T06:00"),
        ("to_end_of", "h", "2024-11-03T06:59:59.999999"),
        ("to_start_of", "D", "2024-11-03T04:00"),
        ("to_end_of", "D", "2024-11-04T04:59:59.999999"),
    ]:
        got = run(x, method, period, expr=expr)
        assert got.dtype == x.dtype
        assert ticks(got) == [tick(expected, "us"), None]


def test_whole_missing_selected_day_does_not_get_replaced_by_another_day():
    x = Pldt(["1844-12-15T12:00"], tz="Asia/Manila", unit="us", name="time")
    with pytest.raises(ValueError):
        x.to_last_of("Y")
    got = x.to_end_of("Y")
    # Pinned native IANA2026b has historical Manila offset -15:56:08.
    # The system's newer database uses -15:56, so it is not this oracle.
    assert ticks(got) == [tick("1844-12-31T15:56:07.999999", "us")]
    assert ticks(got.normalize()) == [tick("1844-12-30T15:56:08", "us")]
    assert ticks(got.to_end_of("D")) == ticks(got)
    assert x.is_last_of("Y").to_list() == [False]
    assert got.is_end_of("Y").to_list() == [True]
    x = Pldt(["2011-12-31T12:00"], tz="Pacific/Apia", unit="us", name="time")
    assert x.is_start_of("Friday").to_list() == [False]
    with pytest.raises(ValueError):
        x.to_start_of("Friday")


@pytest.mark.parametrize("expr", [False, True])
def test_snap_uses_real_nearest_start_and_ties_later_distinct_from_round(expr):
    x = Pldt(["2024-01-02T12:00", None], unit="ns", name="time")
    assert ticks(run(x, "snap", "D", expr=expr)) == [tick("2024-01-03"), None]
    x = Pldt([tick("2024-11-03T05:30"), None], tz="America/New_York", unit="ns", name="time")
    assert ticks(run(x, "snap", "h", expr=expr)) == [tick("2024-11-03T06:00"), None]
    assert ticks(run(x, "round", "h", expr=expr)) == [tick("2024-11-03T07:00"), None]
    x = Pldt(["2011-12-29T12:00"], tz="Pacific/Apia", unit="us", name="time")
    assert ticks(run(x, "snap", "Friday", expr=expr)) == [tick("2012-01-05T10:00", "us")]


def test_all_554_stored_snap_names_have_independent_calendar_answers():
    text = (Path(__file__).resolve().parents[1] / "data/snap_names.md").read_text(encoding="utf-8")
    reference = datetime(2024, 6, 15, 12)
    x = Pldt(["2024-06-15T12:00"], unit="us", name="time")
    weekdays = {"星期" + suffix: n for n, suffix in enumerate("一二三四五六日")}
    counted = 0
    for row in text.splitlines():
        columns = row.strip("|").split("|", 1)
        if len(columns) != 2:
            continue
        heading, words = columns
        if heading in weekdays:
            options = [reference.replace(hour=0) + timedelta(days=weekdays[heading] - reference.weekday() + 7 * n) for n in (-1, 0, 1)]
        elif re.fullmatch(r"\d+月", heading):
            options = [datetime(y, int(heading[:-1]), 1) for y in (2023, 2024, 2025)]
        else:
            continue
        expected = min(options, key=lambda d: (abs(d - reference), -d.toordinal()))
        for word in re.findall(r"`([^`]+)`", words):
            assert ticks(x.snap(word)) == [tick(expected.isoformat(), "us")], word
            counted += 1
    assert counted == 554


@pytest.mark.parametrize("expr", [False, True])
def test_round_ties_even_signed_grid_precision_capacity_and_native_method_boundary(expr):
    x = Pldt([500_000_000, 1_500_000_000, -500_000_000, -1_500_000_000, None], unit="ns", name="time")
    assert ticks(run(x, "round", "s", expr=expr)) == [0, 2_000_000_000, 0, -2_000_000_000, None]
    assert ticks(run(x, "floor", "s", expr=expr)) == [0, 1_000_000_000, -1_000_000_000, -2_000_000_000, None]
    assert ticks(run(x, "ceil", "s", expr=expr)) == [1_000_000_000, 2_000_000_000, 0, -1_000_000_000, None]
    x = Pldt([1], unit="us")
    with pytest.raises(ValueError, match="as_unit"):
        x.pldt.ceil("1500ns")
    with pytest.raises(OverflowError, match="as_unit"):
        Pldt([2**63 - 1], unit="ns").pldt.ceil("2ns")
    # The unqualified Polars numerical API is not overridden by date methods.
    assert Pldt.round is pl.Series.round
    assert Pldt.ceil is pl.Series.ceil and Pldt.floor is pl.Series.floor


def test_date_rounding_fixed_frequency_rejects_calendar_and_bad_options_on_empty():
    x = Pldt([], unit="us")
    for method in ("round", "ceil", "floor"):
        for invalid in ("ME", "0s", "-1s", "", "unknown"):
            with pytest.raises(ValueError):
                getattr(x.pldt, method)(invalid)
        for invalid in (True, 1.5, ["s"]):
            with pytest.raises(TypeError):
                getattr(x.pldt, method)(invalid)
        with pytest.raises(TypeError):
            getattr(x.pldt, method)(unit="s")
        assert ticks(getattr(Pldt(["2024-01-02T12:34:56"], unit="us").pldt, method)(timedelta(minutes=15)))


@pytest.mark.parametrize("expr", [False, True])
def test_gap_grid_uses_actual_boundary_and_preserves_true_instant_direction(expr):
    x = Pldt(["2024-03-10T01:45"], tz="America/New_York", unit="us", name="time")
    for method in ("round", "ceil"):
        assert ticks(run(x, method, "h", expr=expr)) == [tick("2024-03-10T07:00", "us")]
    assert ticks(run(x, "floor", "h", expr=expr)) == [tick("2024-03-10T06:00", "us")]


@pytest.mark.parametrize("freq,step", [("D", 86_400_000_000_000), ("3h", 10_800_000_000_000), ("15min", 900_000_000_000), ("ms", 1_000_000), ("us", 1000), ("500ns", 500)])
@pytest.mark.parametrize("method", ["round", "ceil", "floor"])
def test_fixed_grids_have_independent_signed_integer_expectations(freq, step, method):
    values = [-(step * 3) - step // 2, -1, 0, step // 2, step + step // 2, 1_704_196_496_123_456_789]
    expected = []
    for value in values:
        quotient, remainder = divmod(value, step)
        up = method == "ceil" and remainder != 0
        if method == "round":
            up = remainder > step - remainder or (remainder == step - remainder and quotient % 2 != 0)
        expected.append((quotient + up) * step)
    x = Pldt(values + [None], unit="ns", name="time")
    assert ticks(run(x, method, freq)) == expected + [None]
    assert ticks(run(x, method, freq, expr=True)) == expected + [None]


@pytest.mark.parametrize("precision", range(12))
@pytest.mark.parametrize("expr", [False, True])
def test_fsp_truncates_local_fraction_not_signed_epoch_toward_zero(precision, expr):
    x = Pldt([-1, None], unit="ns", name="time")
    step = 10 ** (9 - min(precision, 9))
    got = run(x, "fsp", precision, expr=expr)
    assert ticks(got) == [-step, None] and got.dtype == x.dtype


def test_fsp_roles_validate_missing_sources_and_shortcut_wide_regions():
    for values in ([], [None]):
        x = Pldt(values, unit="us")
        for invalid in (True, np.bool_(True), 1.0, [1], None):
            with pytest.raises(TypeError):
                x.fsp(invalid)
        with pytest.raises(ValueError):
            x.fsp(-1)
    # These years are outside the civil zone backend, but fsp needs no calendar.
    x = Pldt([-(2**63) + 1000, 2**63 - 1, None], unit="us", tz="America/New_York")
    assert ticks(x.fsp(6)) == ticks(x)
    assert ticks(x.fsp(np.int64(3))) == [(-(2**63) + 1000) // 1000 * 1000, (2**63 - 1) // 1000 * 1000, None]
    assert x.fsp(3).dtype == x.dtype


def test_period_plugin_is_chunk_lazy_and_streaming_safe():
    source = pl.concat([pl.Series("time", [datetime(2024, 5, 7), None]), pl.Series("time", [datetime(2024, 6, 8)])], rechunk=False)
    df = pl.DataFrame({"time": source})
    expr = pl.col("time").pldt.to_last_of("M")
    expected = [tick("2024-05-31", "us"), None, tick("2024-06-30", "us")]
    assert ticks(df.lazy().select(expr).collect(engine="streaming")["time"]) == expected
    assert ticks(df.select(expr)["time"]) == expected
    assert df.lazy().select(pl.col("time").pldt.is_first_of("M")).collect()["time"].to_list() == [False, False, False]


@pytest.mark.parametrize("unit", ["ms", "us"])
@pytest.mark.parametrize("year,next_year", [("0000", "0001"), ("-0001", "0000"), ("12345", "12346")])
def test_naive_calendar_bounds_keep_zero_negative_and_wide_year_capacity(unit, year, next_year):
    x = Pldt(np.array([year + "-05-07T12:00"], dtype=f"datetime64[{unit}]"), name="time")
    assert ticks(x.to_start_of("Y")) == [tick(year + "-01-01", unit)]
    assert ticks(x.to_end_of("Y")) == [tick(next_year + "-01-01", unit) - 1]
    assert x.is_start_of("Y").to_list() == [False]


@pytest.mark.parametrize("zone,before,at,wall_before,wall_at", [
    ("Asia/Manila", "1844-12-31T15:56:07.999999", "1844-12-31T15:56:08", "1844-12-30T23:59:59.999999", "1845-01-01T00:00"),
    ("America/New_York", "1969-04-27T06:59:59.999999", "1969-04-27T07:00", "1969-04-27T01:59:59.999999", "1969-04-27T03:00"),
])
def test_negative_epoch_transition_fraction_removes_timezone_using_actual_offset(zone, before, at, wall_before, wall_at):
    x = Pldt([tick(before, "us"), tick(at, "us"), None], unit="us", tz=zone, name="time")
    expected = [tick(wall_before, "us"), tick(wall_at, "us"), None]
    assert ticks(x.tz_localize(None)) == expected
    expr = pl.col("time").pldt.tz_localize(None)
    assert ticks(pl.DataFrame({"time": pl.Series(x)}).select(expr)["time"]) == expected
