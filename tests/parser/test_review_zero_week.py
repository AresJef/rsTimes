"""Recognized zero weeks cannot disappear into a default date."""
from datetime import datetime

import pytest

from rstimes import Pydt, parse, parse_str, parse_to_epoch


@pytest.mark.parametrize("reader", (parse_str, parse, parse_to_epoch, Pydt.parse))
@pytest.mark.parametrize("isoformat", (False, True))
@pytest.mark.parametrize("strict", (False, True))
@pytest.mark.parametrize("default", (None, datetime(1999, 5, 7)))
def test_compact_zero_week_is_rejected(reader, isoformat, strict, default):
    with pytest.raises(ValueError, match=r"ISO week\b"):
        reader("2024, W001", default=default, isoformat=isoformat, strict=strict)
    actual = reader("2024, W091", default=default, isoformat=isoformat, strict=strict)
    if reader is parse_to_epoch:
        expected = (datetime(2024, 2, 26) - datetime(1970, 1, 1)).days * 86_400_000_000
    else:
        expected = datetime(2024, 2, 26)
    assert actual == expected


@pytest.mark.parametrize("text", ("2024W001", "2024, W00-1", "2024, W090"))
def test_recognized_zero_week_or_weekday(text):
    with pytest.raises(ValueError, match="ISO week"):
        parse_str(text, default=datetime(1999, 5, 7))


def test_pddt_recognized_zero_week():
    pytest.importorskip("pandas")
    from rstimes import Pddt

    with pytest.raises(ValueError, match="ISO week"):
        Pddt.parse(["2024, W001"], default=datetime(1999, 5, 7))
    assert Pddt.parse(["2024, W091"]).asi8.tolist() == [1708905600000000]


def test_pldt_recognized_zero_week():
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    default = datetime(1999, 5, 7)
    with pytest.raises(ValueError, match="ISO week"):
        Pldt.parse(["2024, W001"], default=default, unit="us")
    expr = pl.col("date").pldt.parse(default=default, unit="us")
    with pytest.raises(pl.exceptions.ComputeError, match="ISO week"):
        pl.LazyFrame({"date": ["2024, W001"]}).select(expr).collect()
    result = pl.LazyFrame({"date": ["2024, W091"]}).select(expr).collect()["date"]
    assert result.to_physical().to_list() == [1708905600000000]
