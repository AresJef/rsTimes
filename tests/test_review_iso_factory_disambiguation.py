"""Complete wide years take precedence over overlapping compact separators."""
from datetime import datetime, timedelta, timezone

import pytest

from rstimes import Pydt


def epoch_millis(value):
    return (value - datetime(1970, 1, 1, tzinfo=timezone.utc)) // timedelta(milliseconds=1)


def epoch_seconds(year, month, day):
    previous = year - 1
    ordinal = previous * 365 + previous // 4 - previous // 100 + previous // 400
    lengths = (31, 28 + int(year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)),
               31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return (ordinal + sum(lengths[:month - 1]) + day - datetime(1970, 1, 1).toordinal()) * 86_400


@pytest.mark.parametrize("text, hour, minute, offset", (
    ("20000229-11:05", 11, 5, 0),
    ("20000229-13-00", 13, 0, 0),
    ("20000229011-02:30", 11, 0, -150),
    ("20000229011+02:30", 11, 0, 150),
    ("2000060-13:00", 13, 0, 0),
    ("2000060T13:00", 13, 0, 0),
    ("2000-060-13:00", 13, 0, 0),
    ("20000229🕐13:00Z", 13, 0, 0),
))
def test_pddt_compact_date_time_complete_grammar(text, hour, minute, offset):
    pytest.importorskip("pandas")
    from rstimes import Pddt

    aware = datetime(2000, 2, 29, hour, minute, tzinfo=timezone(timedelta(minutes=offset)))
    expected = epoch_millis(aware)
    values = Pddt.fromisoformat([text, None], unit="ms", tz="UTC", name="stamp")
    assert values.unit == "ms" and values.name == "stamp"
    assert values.asi8.tolist() == [expected, -(2**63)]
    scalar = Pddt.fromisoformat(text, size=1, unit="ms", tz="UTC")
    assert scalar.asi8.tolist() == [expected]


@pytest.mark.parametrize("text, ms", (
    ("20000229-11:05", 951822300000),
    ("20000229-13-00", 951829200000),
    ("20000229011-02:30", 951831000000),
    ("20000229011+02:30", 951813000000),
    ("2000060-13:00", 951829200000),
    ("2000060T13:00", 951829200000),
    ("2000-060-13:00", 951829200000),
))
def test_polars_native_iso_factories_agree_with_independent_coordinates(text, ms):
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    dtype = pl.Datetime("ms", "UTC")
    source = pl.Series("stamp", [text, None])
    results = (
        Pldt.fromisoformat(text, size=1, unit="ms", tz="UTC", name="stamp"),
        Pldt.fromisoformat([text], unit="ms", tz="UTC", name="stamp"),
        source.pldt.fromisoformat(unit="ms", tz="UTC"),
        source.to_frame().select(pl.col("stamp").pldt.fromisoformat(unit="ms", tz="UTC"))["stamp"],
        source.to_frame().lazy().select(
            pl.col("stamp").pldt.fromisoformat(unit="ms", tz="UTC")
        ).collect()["stamp"],
    )
    for index, values in enumerate(results):
        assert values.dtype == dtype and values.name == "stamp"
        assert values.to_physical().to_list() == ([ms] if index < 2 else [ms, None])


@pytest.mark.parametrize("text, year, month, day", (
    ("20000229-01-02", 20000229, 1, 2),
    ("20000230-01-02", 20000230, 1, 2),
    ("2000060-01-02", 2000060, 1, 2),
    ("20000229011-01-02", 20000229011, 1, 2),
))
def test_pddt_wide_years_keep_precedence_and_final_capacity(text, year, month, day):
    pytest.importorskip("pandas")
    from rstimes import Pddt

    values = Pddt.fromisoformat([text], unit="s")
    assert values.asi8.tolist() == [epoch_seconds(year, month, day)]
    with pytest.raises(OverflowError):
        Pddt.fromisoformat([text], unit="ns")
    if year == 20000229011:
        with pytest.raises(OverflowError):
            Pddt.fromisoformat([text], unit="ms")


@pytest.mark.parametrize("text, year", (("20000229-01-02", 20000229), ("2000060-01-02", 2000060)))
def test_polars_full_wide_date_before_capacity(text, year):
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    source = pl.LazyFrame({"stamp": [text]})
    expr = pl.col("stamp").pldt.fromisoformat(unit="ms")
    assert source.select(expr).collect()["stamp"].to_physical().to_list() == [
        epoch_seconds(year, 1, 2) * 1000,
    ]
    with pytest.raises(OverflowError):
        Pldt.fromisoformat([text], unit="ns")
    with pytest.raises(pl.exceptions.ComputeError, match="capacity|range|overflow"):
        source.select(pl.col("stamp").pldt.fromisoformat(unit="ns")).collect()


@pytest.mark.parametrize("text", (
    "20000229-25-00", "2001366-13:00", "20000229011-02:30tail", "20000229011-26:30",
))
def test_no_incomplete_or_invalid_compact_parse(text):
    pytest.importorskip("pandas")
    from rstimes import Pddt

    with pytest.raises(ValueError):
        Pddt.fromisoformat([text], unit="ms", tz="UTC")


def test_existing_iso_fast_paths_and_python_code_point():
    pytest.importorskip("pandas")
    from rstimes import Pddt

    assert Pydt.fromisoformat("20000229-13-00").isoformat() == "2000-02-29T13:00:00+00:00"
    values = Pddt.fromisoformat(["20000229\ud800130000.123456789500"], unit="ns", tz="UTC")
    assert values.asi8.tolist() == [951829200123456789]
    assert Pddt.fromisoformat(["0000-01-01"], unit="s").asi8.tolist() == [epoch_seconds(0, 1, 1)]


_WEEK_TEXT = (
    ("2000-W09-2123", 951772980000),
    ("2000W09-2123", 951772980000),
    ("2000-W09-212345", 951773025000),
    ("2000W09-13:45", 951745500000),
    ("2000-W09-13:45", 951745500000),
    ("2000-W09-2T23:00", 951865200000),
    ("2000W0921234", 951741240000),
    ("2000W09013:45+02:30", 951736500000),
    ("2000W09013:45-02:30", 951754500000),
)

_ORDINAL_TEXT = (
    ("2000060013:00", 951829200000),
    ("2000060013-02:30", 951838200000),
    ("2000060013+02:30", 951820200000),
    ("2000-060013:00", 951829200000),
    ("2000060-13:00", 951829200000),
)


@pytest.mark.parametrize("text,ms", _WEEK_TEXT)
def test_shared_week_date_uses_the_same_separator_as_pydt(text, ms):
    # ISO week 9 of 2000 begins on Monday, February 28.
    observed = Pydt.fromisoformat(text)
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    assert observed == datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=ms)


@pytest.mark.parametrize("text,ms", _WEEK_TEXT + _ORDINAL_TEXT)
def test_new_iso_week_and_ordinal_coordinates_pddt(text, ms):
    pytest.importorskip("pandas")
    from rstimes import Pddt

    kwargs = dict(unit="ms", tz="UTC", name="stamp")
    scalar = Pddt.fromisoformat(text, size=1, **kwargs)
    column = Pddt.fromisoformat([text, None], **kwargs)
    assert scalar.asi8.tolist() == [ms]
    assert column.asi8.tolist() == [ms, -(2**63)] and column.isna().tolist() == [False, True]
    for value in (scalar, column):
        assert type(value) is Pddt and value.unit == "ms" and value.name == "stamp"
        assert str(value.tz) == "UTC"


@pytest.mark.parametrize("text,ms", _WEEK_TEXT + _ORDINAL_TEXT)
def test_new_iso_week_and_ordinal_coordinates_polars(text, ms):
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    raw = pl.Series("stamp", [text, None])
    kwargs = dict(unit="ms", tz="UTC")
    expr = pl.col("stamp").pldt.fromisoformat(**kwargs)
    frame = raw.to_frame()
    results = (
        Pldt.fromisoformat(text, size=1, name="stamp", **kwargs),
        Pldt.fromisoformat([text, None], name="stamp", **kwargs),
        raw.pldt.fromisoformat(**kwargs),
        frame.select(expr).to_series(),
        frame.lazy().select(expr).collect().to_series(),
    )
    for index, value in enumerate(results):
        assert value.dtype == pl.Datetime("ms", "UTC") and value.name == "stamp"
        assert value.to_physical().to_list() == ([ms] if index == 0 else [ms, None])
        assert value.is_null().to_list() == ([False] if index == 0 else [False, True])


@pytest.mark.parametrize("text", ("2000-W09-0T13:45", "2000-W09-8T13:45", "2000-W00-13:45",
                                 "2001366013:00", "2000060013:00Ztail"))
def test_disambiguation_rejects_invalid_calendar_or_unconsumed_tail(text):
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    with pytest.raises(ValueError):
        Pldt.fromisoformat([None, text], unit="ms", tz="UTC")
    source = pl.LazyFrame({"stamp": [None, text]})
    expr = pl.col("stamp").pldt.fromisoformat(unit="ms", tz="UTC")
    # An elementwise plugin can receive a one-row slice or the entire input.
    # Polars owns this partitioning, so the emitted position is batch-local.
    with pytest.raises(pl.exceptions.ComputeError, match=r"batch item [01]: expected a complete ISO"):
        source.select(expr).collect()


def test_compact_extended_iso_preserves_nano_and_one_separator_code_point():
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    value = 951829200123456789
    text = "2000060🕐13:00:00.123456789Z"
    lone_surrogate = "2000060\ud80013:00:00.123456789Z"
    for source in (text, lone_surrogate):
        eager = Pldt.fromisoformat(source, size=1, unit="ns", tz="UTC")
        assert eager.to_physical().to_list() == [value]
    frame = pl.LazyFrame({"stamp": [text, None]})
    expr = pl.col("stamp").pldt.fromisoformat(unit="ns", tz="UTC")
    assert frame.select(expr).collect().to_series().to_physical().to_list() == [value, None]
    with pytest.raises(UnicodeEncodeError):
        pl.Series("stamp", [lone_surrogate])


_S02_COMPACT_TIME = (
    ("2000-W09-20212345", "us", 951769283450000),
    ("2000W09-20212345", "us", 951769283450000),
    ("2000-W09-20212345Z", "us", 951769283450000),
    ("2000-02-28T20212345", "us", 951769283450000),
    ("2000-02-28T202123.45", "us", 951769283450000),
    ("2000-W09-20212345+02:30", "us", 951760283450000),
    ("2000-W09-20212345-02:30", "us", 951778283450000),
    ("2000-02-28T20212345+02304567", "us", 951760237780000),
    ("20000229020212345-02:30", "us", 951864683450000),
    ("20000229020212345+02:30", "us", 951846683450000),
    ("2000022902021234567890123-02:30", "ns", 951864683456789012),
    ("2000022902021234567890123-0230", "ns", 951864683456789012),
    ("2000022902021234567890123-023024", "ns", 951864707456789012),
    ("2000022902021234567890123-000001", "ns", 951855684456789012),
    ("200002290202123456-023045", "ns", 951864728456000000),
)


@pytest.mark.parametrize("text,unit,tick", _S02_COMPACT_TIME)
def test_s02_compact_time_pddt_keeps_the_complete_date_and_clock(text, unit, tick):
    pytest.importorskip("pandas")
    from rstimes import Pddt

    params = dict(unit=unit, tz="UTC", name="stamp")
    scalar = Pddt.fromisoformat(text, size=1, **params)
    column = Pddt.fromisoformat([text, None], **params)
    assert scalar.asi8.tolist() == [tick]
    assert column.asi8.tolist() == [tick, -(2**63)]
    for value in (scalar, column):
        assert type(value) is Pddt and value.unit == unit and value.name == "stamp"
        assert str(value.tz) == "UTC"
    assert column.isna().tolist() == [False, True]


@pytest.mark.parametrize("text,unit,tick", _S02_COMPACT_TIME)
def test_s02_compact_time_polars_keeps_the_complete_date_and_clock(text, unit, tick):
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    raw = pl.Series("stamp", [text, None])
    expr = pl.col("stamp").pldt.fromisoformat(unit=unit, tz="UTC")
    frame = raw.to_frame()
    results = (
        Pldt.fromisoformat(text, size=1, unit=unit, tz="UTC", name="stamp"),
        Pldt.fromisoformat([text, None], unit=unit, tz="UTC", name="stamp"),
        raw.pldt.fromisoformat(unit=unit, tz="UTC"),
        frame.select(expr).to_series(),
        frame.lazy().select(expr).collect().to_series(),
    )
    for index, value in enumerate(results):
        assert value.dtype == pl.Datetime(unit, "UTC") and value.name == "stamp"
        assert value.to_physical().to_list() == ([tick] if index == 0 else [tick, None])
        assert value.is_null().to_list() == ([False] if index == 0 else [False, True])


@pytest.mark.parametrize("text", (
    "2000022902021234567890123-023023",
    "2000022902021234567890123-01-02",
    "200002290202123456-023001",
))
def test_s02_valid_wide_fields_keep_original_capacity_error(text):
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    with pytest.raises(OverflowError, match="ISO year exceeds|integer overflow in Delta date arithmetic"):
        Pldt.fromisoformat([text], unit="ns", tz="UTC")
    frame = pl.LazyFrame({"stamp": [text]})
    with pytest.raises(pl.exceptions.ComputeError,
                       match="batch item 0: (ISO year exceeds|integer overflow in Delta date arithmetic)"):
        frame.select(pl.col("stamp").pldt.fromisoformat(unit="ns", tz="UTC")).collect()


def test_s02_implicit_fraction_preserves_declared_precision_and_capacity_position():
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    ordinary = Pldt.fromisoformat("2000-02-28T20212345", size=1, tz="UTC")
    extended = Pldt.fromisoformat("2000-02-28T2021234500000", size=1, tz="UTC")
    assert ordinary.dtype == pl.Datetime("us", "UTC")
    assert extended.dtype == pl.Datetime("ns", "UTC")
    assert extended.to_physical().to_list() == [951769283450000000]
    frame = pl.DataFrame({"stamp": ["2000-02-28T20212345", None, "20000229-01-02"]})
    expr = pl.col("stamp").pldt.fromisoformat(unit="ns", tz="UTC")
    with pytest.raises(pl.exceptions.ComputeError, match="batch item 2: .*capacity"):
        frame.select(expr)
    with pytest.raises(pl.exceptions.ComputeError, match="batch item 0: .*capacity"):
        frame.slice(2).lazy().select(expr).collect()


@pytest.mark.parametrize("clock", ("2021234", "20:21:2345", "20:21:23:45", "2021234Z", "202123.Z"))
def test_s02_rejects_unfinished_or_unapproved_clock_spellings(clock):
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    with pytest.raises(ValueError, match="complete ISO"):
        Pldt.fromisoformat(["2000-02-28T" + clock], unit="ns", tz="UTC")
    frame = pl.LazyFrame({"stamp": ["2000-02-28T" + clock]})
    with pytest.raises(pl.exceptions.ComputeError, match="batch item 0: expected a complete ISO"):
        frame.select(pl.col("stamp").pldt.fromisoformat(unit="ns", tz="UTC")).collect()
