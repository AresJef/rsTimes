"""Calendar component diagnostics preserve only positions that a layer knows."""
import polars as pl
import pytest

from rstimes import Pldt


@pytest.mark.parametrize("dtype, values, exception", (
    (pl.Float64, [None, 1.5, 2.5], TypeError),
    (pl.String, [None, "2", "bad"], TypeError),
    (pl.UInt64, [None, 2**63, 2**63+1], OverflowError),
    (pl.Int128, [None, -(2**63)-1, 2**63], OverflowError),
    (pl.Int64, [1, 0, -1], ValueError),
    (pl.Int64, [None, 0, -1], ValueError),
))
def test_eager_and_worker_report_first_real_component_row(dtype, values, exception):
    years = pl.Series("year", [2024] * 3)
    weekday = pl.Series("same", values, dtype=dtype)
    with pytest.raises(exception, match=r"Pldt\.fromisocalendar\(\): weekday\[1\]"):
        Pldt.fromisocalendar(years, 9, weekday)
    frame = pl.DataFrame({"year": years, "position": weekday}).lazy()
    expr = pl.col("year").pldt.fromisocalendar(9, pl.col("position"))
    assert frame.select(expr).collect_schema()["year"] == pl.Datetime("us")
    with pytest.raises(pl.exceptions.ComputeError) as caught:
        frame.select(expr).collect()
    message = str(caught.value)
    assert "weekday" in message and "batch item 1" in message
    assert "batch item 2" not in message and "data[1]" not in message


def test_unsupported_dtype_schema_uses_parameter_but_no_item_position():
    frame = pl.LazyFrame({"year": [2024, 2024], "value": [None, True]})
    expr = pl.col("year").pldt.fromisocalendar(9, pl.col("value"))
    with pytest.raises(pl.exceptions.PolarsError) as caught:
        frame.select(expr).collect_schema()
    message = str(caught.value)
    assert "weekday" in message and "integer dtype" in message
    assert "batch item" not in message and "weekday[" not in message


def test_non_expression_literal_gets_its_eager_position():
    with pytest.raises(TypeError, match=r"weekday\[1\]"):
        pl.col("year").pldt.fromisocalendar(9, pl.Series([None, 1.5]))


def test_shape_precedes_low_values_and_low_roles_preserve_order():
    with pytest.raises(ValueError, match="length"):
        Pldt.fromisocalendar([2024, 2024], [0, 1, 1], [0, 1])
    with pytest.raises(ValueError, match=r"\bweek\[1\]"):
        Pldt.fromisocalendar(pl.Series("same", [2024, 2024]),
                             pl.Series("same", [9, 0]), pl.Series("same", [0, 1]))
    with pytest.raises(ValueError, match=r"weekday(?=:).*(at least 1)"):
        Pldt.fromisocalendar(2024, 1, 0, size=0)
    with pytest.raises(ValueError, match=r"doy\[1\]"):
        Pldt.fromdayofyear([2024, None], [1, 0])


def test_first_source_error_does_not_read_later_business_inputs():
    visits = []
    marker = LookupError("original reading error")
    marker.add_note("original note")

    def invalid_week():
        visits.append("week")
        raise marker
        yield

    def later():
        visits.append("weekday")
        yield 1

    with pytest.raises(LookupError) as caught:
        Pldt.fromisocalendar([2024], invalid_week(), later())
    assert caught.value is marker and visits == ["week"]
    assert "original note" in caught.value.__notes__
    assert any("week[0]" in note for note in caught.value.__notes__)


def test_valid_dates_and_null_survive_role_propagation():
    values = [1, None, 4]
    frame = pl.LazyFrame({"year": [2024] * 3, "day": values})
    expr = pl.col("year").pldt.fromisocalendar(9, pl.col("day"), unit="ms")
    ticks = [1708905600000, None, 1709164800000]
    assert frame.select(expr).collect()["year"].to_physical().to_list() == ticks
    assert Pldt.fromisocalendar([2024] * 3, 9, values, unit="ms").to_physical().to_list() == ticks
