"""Polars ProductReady regressions execute the expression, including streaming."""
from fractions import Fraction

import numpy as np
import polars as pl
import pytest

from rstimes import Pldt


class IsoText(str):
    """A passive real str subclass, read by native storage."""


@pytest.mark.parametrize("value", ["0.5", "0.5" + "0" * 40,
                                  "0.123456789012345678901234567890",
                                  "0." + "0" * 40 + "1"])
@pytest.mark.parametrize("clock_unit,factor", [("h", 3_600_000_000_000),
                                              ("m", 60_000_000_000)])
@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("isoformat", [False, True])
def test_decimal_clock_eager_and_expr_match_exact_rational(value, clock_unit, factor,
                                                          strict, isoformat):
    text = "1970-01-01 " + value + clock_unit
    expected = [int(Fraction(value) * factor), None]
    options = {"unit": "ns", "strict": strict, "isoformat": isoformat}
    source = pl.Series("time", [text, None])
    eager = Pldt(source, **options)
    assert eager.name == "time" and eager.to_physical().to_list() == expected
    query = pl.DataFrame({"time": source}).lazy().select(pl.col("time").pldt.parse(**options))
    for engine in ("auto", "streaming"):
        result = query.collect(engine=engine)["time"]
        assert result.dtype == pl.Datetime("ns")
        assert result.to_physical().to_list() == expected
    assert source.to_list() == [text, None]


@pytest.mark.parametrize("shape", ["empty", "missing", "chunked"])
def test_long_decimal_clock_empty_null_and_chunked_columns(shape):
    text = "1970-01-01 0.5" + "0" * 40 + "m"
    values = {"empty": [], "missing": [None], "chunked": [text, None, text]}[shape]
    pieces = [pl.Series("time", [value], dtype=pl.String) for value in values]
    source = pl.concat(pieces, rechunk=False) if pieces else pl.Series("time", [], dtype=pl.String)
    expected = [None if value is None else 30_000_000_000 for value in values]
    assert Pldt(source, unit="ns").to_physical().to_list() == expected
    query = pl.DataFrame({"time": source}).lazy().select(pl.col("time").pldt.parse(unit="ns"))
    for engine in ("auto", "streaming"):
        assert query.collect(engine=engine)["time"].to_physical().to_list() == expected


@pytest.mark.parametrize("separator", ["T", "x", "🕒", "\0", "\ud800", "\udfff"])
@pytest.mark.parametrize("scalar", [False, True])
@pytest.mark.parametrize("factory", [str, IsoText, np.str_])
def test_iso_python_codepoint_and_representable_native_expression(separator, scalar, factory):
    from datetime import datetime

    text = "2024-01-02" + separator + "12:30:01.123456789"
    base = datetime(2024, 1, 2, 12, 30, 1) - datetime(1970, 1, 1)
    expected = (base.days * 86400 + base.seconds) * 1_000_000_000 + 123456789
    value = factory(text)
    result = Pldt.fromisoformat(value, size=1) if scalar else Pldt.fromisoformat([value])
    assert result.to_physical().to_list() == [expected]
    assert result.dtype == pl.Datetime("ns")
    if not 0xD800 <= ord(separator) <= 0xDFFF:
        query = pl.DataFrame({"time": [text]}).lazy().select(
            pl.col("time").pldt.fromisoformat(unit="ns"))
        for engine in ("auto", "streaming"):
            assert query.collect(engine=engine)["time"].to_physical().to_list() == [expected]


@pytest.mark.parametrize("literal", ["", "日期", "🌏", "\0", "\ud800", "\udfff"])
def test_formatted_python_literals_and_native_string_domain_remain_distinct(literal):
    text = "2024-01-02" + literal
    fmt = "%Y-%m-%d" + literal
    result = Pldt.strptime([text, None], fmt, unit="us")
    assert result.to_physical().to_list() == [1704153600000000, None]
    if literal not in ("\ud800", "\udfff"):
        query = pl.DataFrame({"time": [text, None]}).lazy().select(
            pl.col("time").pldt.strptime(fmt, unit="us"))
        for engine in ("auto", "streaming"):
            assert query.collect(engine=engine)["time"].to_physical().to_list() == [1704153600000000, None]
    else:
        # Python format text may contain a surrogate; actual Polars String output may not.
        with pytest.raises(UnicodeEncodeError):
            result.strftime(literal + "%Y %f")


@pytest.mark.parametrize("values", [[], [None]])
def test_invalid_format_is_not_hidden_by_empty_or_null_polars_data(values):
    with pytest.raises(ValueError, match="fraction precision") as observed:
        Pldt(values, unit="us").strftime("\ud800%.12f")
    assert not isinstance(observed.value, UnicodeEncodeError)


@pytest.mark.parametrize("display", ["ordinary", "tuple", "raise"])
@pytest.mark.parametrize("wrapped", [False, True])
def test_default_restore_keeps_actual_dict_subclass_and_native_validity(display, wrapped):
    calls = []

    class State(dict):
        @property
        def __class__(self):
            calls.append("display")
            if display == "raise":
                raise RuntimeError("display identity must not be read")
            return tuple if display == "tuple" else dict

    payload = []
    state = State(payload=payload)
    value = Pldt([-(1 << 63), None], unit="ns", name="stamp")
    value.__setstate__((state, None) if wrapped else state)
    assert calls == [] and value.payload is payload
    assert value.to_physical().to_list() == [-(1 << 63), None]
    assert value.is_null().to_list() == [False, True]
    assert value.name == "stamp" and value.dtype == pl.Datetime("ns")
