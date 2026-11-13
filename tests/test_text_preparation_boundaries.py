"""Stored format/frequency text is prepared before caching or delegation."""
import numpy as np
import pytest

pytest.importorskip("pandas")
pl = pytest.importorskip("polars")
from rstimes import Pydt, Pddt, Pldt


class DisplayFormat(str):
    def __str__(self):
        return "%Y-%d-%m"


class DisplayFrequency(str):
    def __str__(self):
        return "h"


class InferFrequency(str):
    def __eq__(self, other):
        return other == "infer"

    __hash__ = str.__hash__


@pytest.mark.parametrize("fmt", ("%Y-%m-%d", np.str_("%Y-%m-%d"), DisplayFormat("%Y-%m-%d")))
@pytest.mark.parametrize("base", (Pydt, Pddt, Pldt))
def test_strptime_uses_stored_format(base, fmt: str) -> None:
    if base is Pydt:
        value = base.strptime("2024-03-02", fmt)
        assert (value.year, value.month, value.day) == (2024, 3, 2)
    elif base is Pddt:
        value = base.strptime("2024-03-02", fmt, size=1, unit="ns")
        assert value.asi8.tolist() == [1709337600000000000]
    else:
        value = base.strptime("2024-03-02", fmt, size=1, unit="ns")
        assert value.to_physical().to_list() == [1709337600000000000]


def test_expr_strptime_collects_with_stored_format() -> None:
    expr = pl.col("text").pldt.strptime(DisplayFormat("%Y-%m-%d"), unit="ns")
    value = pl.DataFrame({"text": ["2024-03-02"]}).lazy().select(expr).collect()["text"]
    assert value.to_physical().to_list() == [1709337600000000000]


@pytest.mark.parametrize("freq", ("D", np.str_("D"), DisplayFrequency("D")))
@pytest.mark.parametrize("base", (Pddt, Pldt))
def test_range_uses_stored_frequency(base, freq: str) -> None:
    value = base.date_range("2024-01-01", periods=3, freq=freq, unit="ns")
    actual = value.asi8.tolist() if base is Pddt else value.to_physical().to_list()
    assert actual == [1704067200000000000 + i * 86400_000_000_000 for i in range(3)]


@pytest.mark.parametrize("factory", (Pddt, Pddt.parse))
def test_metadata_cannot_disguise_daily_as_inferred_frequency(factory) -> None:
    with pytest.raises(ValueError):
        factory(["2024-01-01", "2024-01-03", "2024-01-05"], freq=InferFrequency("D"))


def test_real_inferred_frequency_and_offset_are_preserved() -> None:
    import pandas as pd
    for freq in ("infer", pd.offsets.Day(2)):
        value = Pddt(["2024-01-01", "2024-01-03", "2024-01-05"], freq=freq)
        assert value.freq == pd.offsets.Day(2)


@pytest.mark.parametrize("base", (Pddt, Pldt))
@pytest.mark.parametrize("inclusive,days", (("both", [1, 2, 3]), ("left", [1, 2]), ("right", [2, 3]), ("neither", [2])))
def test_range_endpoint_mapping_is_shared(base, inclusive: str, days: list[int]) -> None:
    value = base.date_range("2024-01-01", end="2024-01-03", freq="D", inclusive=inclusive)
    actual = value.day.tolist() if base is Pddt else value.dt.day().to_list()
    assert actual == days


@pytest.mark.parametrize("mode,expected", (("floor", 1704067200000000000), ("ceil", 1704153600000000000), ("round", 1704153600000000000)))
@pytest.mark.parametrize("path", ("pddt", "series", "expr"))
def test_rounding_uses_stored_frequency(path: str, mode: str, expected: int) -> None:
    freq = DisplayFrequency("D")
    if path == "pddt":
        result = getattr(Pddt(["2024-01-01T17:42:00"], unit="ns"), mode)(freq)
        actual = result.asi8.tolist()
    elif path == "series":
        result = getattr(Pldt(["2024-01-01T17:42:00"], unit="ns").pldt, mode)(freq)
        actual = result.to_physical().to_list()
    else:
        source = Pldt(["2024-01-01T17:42:00"], unit="ns", name="time")
        expr = getattr(pl.col("time").pldt, mode)(freq)
        actual = pl.DataFrame([source]).lazy().select(expr).collect()["time"].to_physical().to_list()
    assert actual == [expected]


def test_business_constructor_receives_original_frequency_once() -> None:
    calls = []
    frequency = np.str_("D")

    class Business(Pddt):
        def __new__(cls, data, **kwargs):
            calls.append(kwargs.get("freq"))
            return super().__new__(cls, data, **kwargs)

    value = Business.parse(["2024-01-01", "2024-01-02"], freq=frequency)
    assert type(value) is Business and len(calls) == 1
    assert calls[0] is frequency
