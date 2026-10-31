"""Native same-coordinate copies preserve source-specific null and owner rules."""
import numpy as np
import polars as pl
import pytest

from rstimes import Pldt


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
@pytest.mark.parametrize("readonly", [False, True])
def test_numpy_without_nat_still_owns_its_final_copy(unit, readonly):
    raw = np.array([-1, 0, 123456789], dtype="i8")
    view = raw.view("datetime64[" + unit + "]")
    view.flags.writeable = not readonly
    result = Pldt(view, name="copied")
    assert result.dtype == pl.Datetime(unit) and result.name == "copied"
    assert not np.shares_memory(raw, result.to_physical().to_numpy())
    raw[:] = 99
    assert result.to_physical().to_list() == [-1, 0, 123456789]


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
def test_numpy_same_unit_keeps_nat_distinct_from_real_tick_values(unit):
    raw = np.array([-(2**63), -1, 0, 123456789], dtype="i8")
    source = raw.view("datetime64[" + unit + "]")
    result = Pldt(source, name="numpy")
    assert result.dtype == pl.Datetime(unit) and result.name == "numpy"
    assert result.to_physical().to_list() == [None, -1, 0, 123456789]
    raw[:] = 99
    assert result.to_physical().to_list() == [None, -1, 0, 123456789]


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
@pytest.mark.parametrize("target", [None, "UTC"])
def test_native_copy_keeps_valid_minimum_null_chunks_and_known_instants(unit, target):
    dtype = pl.Datetime(unit, "America/New_York")
    source = pl.concat([pl.Series("time", [-(2**63), None], dtype=dtype),
                        pl.Series("time", [-1, 0, 17], dtype=dtype)], rechunk=False)
    result = Pldt(source, copy=True, tz=target)
    assert result.dtype == pl.Datetime(unit, target or "America/New_York")
    assert result.name == "time"
    assert result.to_physical().to_list() == [-(2**63), None, -1, 0, 17]
    assert result.is_null().to_list() == [False, True, False, False, False]


@pytest.mark.parametrize("kind", ["numeric", "datetime"])
@pytest.mark.parametrize("readonly", [False, True])
def test_native_copy_true_is_independent_of_numpy_backing_alias(kind, readonly):
    raw = np.array([1, 2, 3], dtype="i8")
    view = raw.view("datetime64[ns]" if kind == "datetime" else "i8")
    view.flags.writeable = not readonly
    source = pl.Series("time", view)
    result = Pldt(source, copy=True)
    assert not np.shares_memory(raw, result.to_physical().to_numpy())
    raw[:] = 99
    assert result.to_physical().to_list() == [1, 2, 3]


@pytest.mark.parametrize("kind", ["numpy", "polars"])
def test_changed_unit_still_requires_lossless_input_conversion(kind):
    source = (np.array([1], dtype="datetime64[ns]") if kind == "numpy"
              else pl.Series("time", [1], dtype=pl.Datetime("ns")))
    with pytest.raises(ValueError, match="precision|loss|finer"):
        Pldt(source, unit="us", copy=True)


@pytest.mark.parametrize("dtype, unit, expected", [
    ("datetime64[s]", "ms", [1000, 2000]),
    ("datetime64[2us]", "us", [2, 4]),
])
def test_coarse_or_multiplier_source_still_scales_its_real_ticks(dtype, unit, expected):
    result = Pldt(np.array([1, 2], dtype=dtype))
    assert result.dtype == pl.Datetime(unit)
    assert result.to_physical().to_list() == expected


@pytest.mark.parametrize("kind", ["numpy", "polars"])
def test_empty_same_unit_still_checks_the_supplied_policy_length(kind):
    source = (np.array([], dtype="datetime64[us]") if kind == "numpy"
              else pl.Series("time", [], dtype=pl.Datetime("us")))
    with pytest.raises(ValueError, match="length|match"):
        Pldt(source, copy=True, ambiguous=[True])


def test_native_unsigned_copy_checks_capacity_before_returning_any_dates():
    source = pl.Series("time", [0, 2**63], dtype=pl.UInt64)
    with pytest.raises(OverflowError, match="signed64|range|capacity"):
        Pldt(source, copy=True)


def test_same_unit_native_wide_year_is_not_limited_by_python_datetime():
    source = np.array(["12024-01-01"], dtype="datetime64[us]")
    result = Pldt(source)
    assert result.dtype == pl.Datetime("us") and result.year.to_list() == [12024]
