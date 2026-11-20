"""Field snapshots finish before the next user callback starts."""
import numpy as np
import polars as pl
import pytest

from rstimes import Pldt


def change(column, values):
    if isinstance(column, np.ndarray):
        column[:] = values
    else:
        for i, value in enumerate(values):
            column[i] = value


def physical(texts, unit):
    return np.array(texts, dtype=f"datetime64[{unit}]").view("i8").tolist()


@pytest.mark.parametrize("kind", ["numpy", "polars"])
@pytest.mark.parametrize("unit", ["us", "ns"])
def test_earlier_native_column_is_owned_before_later_index_callback(kind, unit):
    column = np.array([1, 2], dtype="i8")
    if kind == "polars":
        column = pl.Series("months", column)
    class Later:
        calls = 0
        def __index__(self):
            self.calls += 1
            change(column, [0, 0])
            return 0
    later = Later()
    source = Pldt(["2024-01-31", "2024-01-31"], unit=unit, name="events")
    before = source.to_physical().to_list()
    result = source.add(months=column, days=later)
    assert result.to_physical().to_list() == physical(["2024-02-29", "2024-03-31"], unit)
    assert later.calls == 1 and list(column) == [0, 0]
    assert source.to_physical().to_list() == before
    assert result.dtype == source.dtype and result.name == "events"


@pytest.mark.parametrize("kind", ["numpy", "polars"])
@pytest.mark.parametrize("unit", ["us", "ns"])
def test_later_native_column_observes_earlier_index_callback(kind, unit):
    column = np.array([0, 0], dtype="i8")
    if kind == "polars":
        column = pl.Series("days", column)
    class Earlier:
        calls = 0
        def __index__(self):
            self.calls += 1
            change(column, [1, 2])
            return 1
    earlier = Earlier()
    source = Pldt(["2024-01-31", "2024-01-31"], unit=unit)
    result = source.add(months=earlier, days=column)
    assert result.to_physical().to_list() == physical(["2024-03-01", "2024-03-02"], unit)
    assert earlier.calls == 1


@pytest.mark.parametrize("unit", ["us", "ns"])
def test_saved_name_and_null_selector_snapshot_precedes_later_callback(unit):
    month = pl.Series("month", ["February", None], dtype=pl.String)
    class Day:
        calls = 0
        def __index__(self):
            self.calls += 1
            month[0] = "March"
            return 29
    day = Day()
    source = Pldt(["2024-01-31", "2024-01-31"], unit=unit)
    result = source.to_year(0, month=month, day=day)
    assert result.to_physical().to_list() == physical(["2024-02-29", "2024-01-29"], unit)
    assert day.calls == 1 and month[0] == "March"


def test_invalid_column_finishes_error_before_later_callback():
    class Later:
        calls = 0
        def __index__(self):
            self.calls += 1
            return 0
    later = Later()
    source = Pldt(["2024-01-31", "2024-01-31"], unit="ns")
    values = pl.Series("months", [1, 1 << 63], dtype=pl.UInt64)
    with pytest.raises(OverflowError, match="months"):
        source.add(months=values, days=later)
    assert later.calls == 0


def test_wide_column_capacity_error_precedes_earlier_row_selector_error():
    class Later:
        calls = 0

        def __index__(self):
            self.calls += 1
            return 1

    later = Later()
    source = Pldt(["2024-01-31", "2024-01-31"], unit="ns")
    month = pl.Series("month", [0, 1 << 63], dtype=pl.UInt64)
    with pytest.raises(OverflowError, match="month.*signed64"):
        source.to_year(0, month=month, day=later)
    assert later.calls == 0


def test_empty_typed_parameter_validates_before_later_callback():
    class Later:
        calls = 0

        def __index__(self):
            self.calls += 1
            return 1

    later = Later()
    source = Pldt([], unit="ns")
    with pytest.raises(TypeError, match="month.*integer"):
        source.to_year(0, month=pl.Series("month", [], dtype=pl.Float64), day=later)
    assert later.calls == 0


@pytest.mark.parametrize("dtype", [pl.Int8, pl.Int16, pl.UInt32])
def test_chunked_optional_integer_selector_preserves_independent_null(dtype):
    day = pl.concat([pl.Series("day", [None], dtype=dtype),
                     pl.Series("day", [20], dtype=dtype)], rechunk=False)
    source = Pldt(["2024-01-31", "2024-01-31"], unit="us")
    result = source.to_date(day=day)
    assert result.to_physical().to_list() == physical(["2024-01-31", "2024-01-20"], "us")
    assert day.to_list() == [None, 20]


def test_null_dtype_optional_selector_and_length_one_collection_roles():
    source = Pldt(["2024-01-31", "2024-01-31"], unit="us")
    assert source.to_date(day=pl.Series([None, None], dtype=pl.Null)).to_physical().to_list() == source.to_physical().to_list()
    with pytest.raises(ValueError, match="length|scalar"):
        source.add(months=pl.Series([1], dtype=pl.Int64))
