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
