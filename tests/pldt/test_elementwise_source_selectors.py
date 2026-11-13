"""Calendar plugin eligibility must preserve native Polars source forms."""

import polars as pl
import pytest

from rstimes import Delta, Pldt


@pytest.mark.parametrize("kind", ["all", "names", "regex", "column", "alias", "aggregate"])
@pytest.mark.parametrize("operation", ["month", "delta"])
@pytest.mark.parametrize("lazy", [False, True])
def test_public_sources_keep_calendar_values_and_shape(
    kind: str, operation: str, lazy: bool,
) -> None:
    """Selectors stay valid; aggregate and alias shape/name semantics survive."""
    dates = Pldt([0, 86_400_000_000, None], unit="us", name="time1")
    frame = pl.DataFrame({"time1": dates, "time2": dates})
    sources = {
        "all": pl.all(),
        "names": pl.col(["time1", "time2"]),
        "regex": pl.col("^time.*$"),
        "column": pl.col("time1"),
        "alias": pl.col("time1").alias("renamed"),
        "aggregate": pl.col("time1").max(),
    }
    source = sources[kind]
    expression = (
        source.pldt.to_next_month()
        if operation == "month"
        else source.pldt.add_delta(Delta(months=1))
    )
    assert isinstance(expression, pl.Expr)
    result = frame.lazy().select(expression).collect() if lazy else frame.select(expression)
    expected = [2_678_400_000_000, 2_764_800_000_000, None]
    columns = ["time1", "time2"] if kind in ("all", "names", "regex") else [
        "renamed" if kind == "alias" else "time1"
    ]
    if kind == "aggregate":
        expected = [2_764_800_000_000]
    assert result.columns == columns
    assert all(dtype == pl.Datetime("us") for dtype in result.dtypes)
    assert [series.cast(pl.Int64).to_list() for series in result] == [expected] * len(columns)
