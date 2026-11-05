"""Independent outcomes for the first official-plugin execution slice.

These tests exercise the installed wheel, not a source-directory substitute.
"""

import polars as pl
import pytest
import gc

from rstimes import Pldt
from rstimes.pldt import Pldt as ModulePldt


def dates() -> pl.Series:
    """Return January/February dates with real nanoseconds and one null."""
    return pl.Series(
        "time",
        [1706659200123456789, 1709164800123456789, None],
        dtype=pl.Datetime("ns"),
    )


def test_class_and_final_date_return() -> None:
    assert Pldt is ModulePldt
    source = dates()
    original = source.clone()
    result = Pldt(source).to_next_month()
    assert isinstance(result, Pldt)
    assert isinstance(result, pl.Series)
    assert result.dtype == pl.Datetime("ns")
    assert result.name == "time"
    assert result.cast(pl.Int64).to_list() == [
        1709164800123456789,
        1711670400123456789,
        None,
    ]
    assert source.equals(original)
    assert source.pldt.to_next_month().equals(result)


def test_real_expr_lazy_and_schema() -> None:
    source = dates()
    expr = pl.col("time").pldt.to_next_month()
    assert isinstance(expr, pl.Expr)
    query = pl.DataFrame(source).lazy().select(expr)
    assert query.collect_schema()["time"] == pl.Datetime("ns")
    assert query.collect()["time"].cast(pl.Int64).to_list() == [
        1709164800123456789,
        1711670400123456789,
        None,
    ]


def test_query_has_boolean_output_and_null_false() -> None:
    result = dates().pldt.is_month(1)
    assert type(result) is pl.Series
    assert result.dtype == pl.Boolean
    assert result.to_list() == [True, False, False]
    expr = pl.col("time").pldt.is_month(1)
    assert pl.DataFrame(dates()).select(expr)["time"].to_list() == result.to_list()


def pairing_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "time": pl.Series(
                [1704067200000000, 1704844800000000, 1705708800000000],
                dtype=pl.Datetime("us"),
            ),
            "days": [1, 2, 3],
            "group": ["A", "A", "B"],
        }
    )


def test_logical_scalar_is_not_a_length_one_vector() -> None:
    frame = pairing_frame()
    expr = pl.col("time").pldt.add(days=pl.col("days").max())
    assert frame.select(expr)["time"].cast(pl.Int64).to_list() == [
        1704326400000000,
        1705104000000000,
        1705968000000000,
    ]
    expr = pl.col("time").pldt.add(days=pl.col("days"))
    assert frame.select(expr)["time"].cast(pl.Int64).to_list() == [
        1704153600000000,
        1705017600000000,
        1705968000000000,
    ]
    expr = pl.col("time").pldt.add(days=pl.col("days").head(1))
    with pytest.raises((ValueError, pl.exceptions.ShapeError, pl.exceptions.ComputeError)):
        frame.select(expr)


def test_scalar_aggregation_is_evaluated_in_its_group() -> None:
    expr = pl.col("time").pldt.add(days=pl.col("days").max()).over("group")
    assert pairing_frame().select(expr)["time"].cast(pl.Int64).to_list() == [
        1704240000000000,
        1705017600000000,
        1705968000000000,
    ]


def test_date_source_does_not_expand() -> None:
    expr = pl.col("time").head(1).pldt.add(days=pl.col("days"))
    with pytest.raises((ValueError, pl.exceptions.ShapeError, pl.exceptions.ComputeError)):
        pairing_frame().select(expr)


def test_chunks_slice_and_source_release_keep_values() -> None:
    source = pl.concat([dates().head(1), dates().tail(2)], rechunk=False)
    assert source.n_chunks() == 2
    result = source.slice(1, 2).pldt.to_next_month()
    del source
    gc.collect()
    assert result.cast(pl.Int64).to_list() == [1711670400123456789, None]


def test_filter_and_streaming_preserve_logical_pairing() -> None:
    frame = pairing_frame()
    query = frame.lazy().filter(pl.col("days") > 1).select(
        pl.col("time").pldt.add(days=pl.col("days"))
    )
    assert query.collect(engine="streaming")["time"].cast(pl.Int64).to_list() == [
        1705017600000000, 1705968000000000,
    ]


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
def test_empty_and_all_null_have_declared_schema(unit) -> None:
    for values in ([], [None, None]):
        source = pl.Series("time", values, dtype=pl.Datetime(unit))
        result = source.pldt.to_next_month()
        assert isinstance(result, Pldt)
        assert result.dtype == source.dtype
        assert result.to_physical().to_list() == values
        query = pl.DataFrame(source).lazy().select(pl.col("time").pldt.to_next_month())
        assert query.collect_schema()["time"] == source.dtype
        assert query.collect()["time"].to_physical().to_list() == values


def test_valid_minimum_tick_is_not_missing() -> None:
    minimum = -(2**63)
    source = pl.Series("time", [minimum, None], dtype=pl.Datetime("ns"))
    result = source.pldt.to_next_month()
    assert result.to_physical().to_list() == [minimum + 30 * 86400 * 10**9, None]
    assert result.is_null().to_list() == [False, True]


def test_float_aggregation_is_not_an_integer_scalar() -> None:
    expr = pl.col("time").pldt.add(days=pl.col("days").mean())
    with pytest.raises((ValueError, TypeError, pl.exceptions.PolarsError)):
        pairing_frame().select(expr)


def test_unknown_kwargs_version_is_rejected_without_data_scan() -> None:
    from pathlib import Path
    from polars.plugins import register_plugin_function
    from rstimes import _native

    expr = register_plugin_function(
        plugin_path=Path(_native.__file__),
        function_name="pldt_query",
        args=[pl.col("time")],
        kwargs={"version": 2, "code": 20, "entry": "Pldt.year", "scalar": False, "reference": None},
    )
    with pytest.raises(pl.exceptions.PolarsError, match="preparation version"):
        pl.DataFrame(dates()).lazy().select(expr).collect_schema()
