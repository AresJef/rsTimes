"""Static scalar optimization preserves native values, strict shapes and ordered DST."""
from datetime import datetime

import numpy as np
import polars as pl
import pytest

from rstimes import Delta, Pldt


TEXT = ["2024-01-31T12:34:56.123456789", None,
        "2024-02-29T12:34:56.123456789", "2024-01-30T12:34:56.123456789"]


def ticks(text):
    return None if text is None else int(np.datetime64(text, "ns").astype(np.int64))


def operation(kind, source):
    if kind == "move":
        return source.pldt.to_next_month()
    if kind == "replace":
        return source.pldt.replace(day=1)
    if kind == "delta":
        return source.pldt.add_delta(Delta(months=1, nanoseconds=1))
    if kind == "query":
        return source.pldt.is_month(1)
    return source.pldt.diff(np.datetime64("2024-01-01", "ns"), "D")


def expected(kind):
    if kind == "query":
        return [True, False, False, True]
    if kind == "diff":
        return [30, None, 59, 29]
    if kind == "replace":
        return [ticks("2024-01-01T12:34:56.123456789"), None,
                ticks("2024-02-01T12:34:56.123456789"), ticks("2024-01-01T12:34:56.123456789")]
    values = [ticks("2024-02-29T12:34:56.123456789"), None,
              ticks("2024-03-29T12:34:56.123456789"), ticks("2024-02-29T12:34:56.123456789")]
    return [None if value is None else value + (kind == "delta") for value in values]


@pytest.mark.parametrize("kind", ["move", "replace", "delta", "query", "diff"])
@pytest.mark.parametrize("rechunk", [False, True])
def test_static_scalar_routes_preserve_all_values_in_streaming_groups_and_windows(kind, rechunk):
    chunks = [pl.Series(Pldt(TEXT[:2], unit="ns", name="time")),
              pl.Series(Pldt(TEXT[2:3], unit="ns", name="time")),
              pl.Series(Pldt(TEXT[3:], unit="ns", name="time"))]
    source = pl.concat(chunks, rechunk=rechunk)
    frame = pl.DataFrame({"time": source, "group": [0, 1, 0, 1]})
    original = source.to_physical().to_list()
    expr = operation(kind, pl.col("time"))
    want = expected(kind)
    for engine in ("auto", "streaming"):
        result = frame.lazy().select(expr).collect(engine=engine)["time"]
        assert result.to_physical().to_list() == want
        assert result.name == "time"
        assert result.dtype == (pl.Boolean if kind == "query" else pl.Int64 if kind == "diff" else pl.Datetime("ns"))
        sliced = frame.lazy().select(expr).slice(1, 2).collect(engine=engine)["time"]
        assert sliced.to_physical().to_list() == want[1:3]
    assert frame.select(expr.over("group"))["time"].to_physical().to_list() == want
    grouped = frame.group_by("group", maintain_order=True).agg(expr.to_physical())
    assert grouped["time"].to_list() == [[want[0], want[2]], [want[1], want[3]]]
    filtered = frame.lazy().with_columns(expr.alias("answer")).filter(pl.col("group") == 0).collect()
    assert filtered["answer"].to_physical().to_list() == [want[0], want[2]]
    assert source.to_physical().to_list() == original


@pytest.mark.parametrize("kind", ["move", "replace", "delta", "query", "diff"])
def test_static_scalar_routes_preserve_empty_all_null_and_literal_source_shapes(kind):
    for data in ([], [None, None]):
        source = Pldt(data, unit="ns", name="time")
        result = pl.DataFrame({"time": source}).lazy().select(operation(kind, pl.col("time"))).collect(engine="streaming")
        assert result.height == len(data)
        assert result.to_series().to_physical().to_list() == ([False] * len(data) if kind == "query" else [None] * len(data))
    # A genuinely scalar source remains a scalar; no N-row synthetic expansion.
    frame = pl.DataFrame({"n": [1, 2, 3]})
    result = frame.select(operation(kind, pl.lit(datetime(2024, 1, 31)).cast(pl.Datetime("ns"))))
    assert result.height == 1


@pytest.mark.parametrize("kind", ["move", "delta", "query", "diff"])
@pytest.mark.parametrize("slice_result", [False, True])
def test_one_element_collections_remain_strict_even_with_result_slice(kind, slice_result):
    source = Pldt(TEXT, unit="ns", name="time")
    namespace = pl.col("time").pldt
    if kind == "move":
        expr = namespace.to_day([1])
    elif kind == "delta":
        expr = namespace.add_delta([Delta(days=1)])
    elif kind == "query":
        expr = namespace.is_month([1])
    else:
        expr = namespace.diff(["2024-01-01"], "D")
    query = pl.DataFrame({"time": source}).lazy().select(expr)
    if slice_result:
        query = query.head(1)
    with pytest.raises((ValueError, pl.exceptions.PolarsError), match="length|scalar|shape"):
        query.collect(engine="streaming")


def test_infer_and_explicit_full_masks_keep_sequence_wide_dst_semantics():
    wall = ["2024-11-03T00:30", "2024-11-03T01:30", "2024-11-03T01:30", "2024-11-03T02:30"]
    source = pl.concat([pl.Series(Pldt(wall[:2], unit="ns", name="time")),
                        pl.Series(Pldt(wall[2:], unit="ns", name="time"))], rechunk=False)
    frame = pl.DataFrame({"time": source})
    want = [ticks(value) for value in ["2024-11-03T04:30", "2024-11-03T05:30", "2024-11-03T06:30", "2024-11-03T07:30"]]
    for ambiguous in ("infer", [True, True, False, False]):
        expr = pl.col("time").pldt.replace(tzinfo="America/New_York", ambiguous=ambiguous)
        result = frame.lazy().select(expr).collect(engine="streaming").to_series()
        assert result.dtype == pl.Datetime("ns", "America/New_York")
        assert result.to_physical().to_list() == want
