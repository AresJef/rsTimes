"""R18 optimization contracts: actual converted values, chunks and error rows."""
from math import gcd

import polars as pl
import pytest

from rstimes._native import _pldt_check_numpy


LINEAR_UNITS = [(2, 604_800_000_000_000), (4, 86_400_000_000_000),
                (5, 3_600_000_000_000), (6, 60_000_000_000),
                (7, 1_000_000_000), (8, 1_000_000), (9, 1000), (10, 1)]


@pytest.mark.parametrize("unit,quantum", [("ms", 1_000_000), ("us", 1000), ("ns", 1)])
@pytest.mark.parametrize("code,scale", LINEAR_UNITS)
@pytest.mark.parametrize("multiplier", [1, 3])
def test_numpy_temporal_check_uses_exact_linear_unit_and_multiplier(unit, quantum, code, scale, multiplier):
    target_quantum = scale * multiplier
    step = target_quantum // gcd(quantum, target_quantum)
    values = [0, step, -step, None]
    expected = [None if v is None else v * quantum // target_quantum for v in values]
    source = pl.Series(values, dtype=pl.Datetime(unit))
    target = pl.Series(expected, dtype=pl.Int64)
    assert _pldt_check_numpy(source, target, (code, multiplier)) is None


@pytest.mark.parametrize("slice_inputs", [False, True])
def test_numpy_temporal_check_pairs_different_chunk_boundaries_and_slices(slice_inputs):
    values = [0, 1000, None, -1000, 3000, None, 4000]
    source = pl.concat([pl.Series(values[:3], dtype=pl.Datetime("ns")),
                        pl.Series(values[3:], dtype=pl.Datetime("ns"))], rechunk=False)
    target = pl.concat([pl.Series([0, 1], dtype=pl.Int64),
                        pl.Series([None, -1, 3], dtype=pl.Int64),
                        pl.Series([None, 4], dtype=pl.Int64)], rechunk=False)
    if slice_inputs:
        source, target = source.slice(1, 5), target.slice(1, 5)
    assert source.n_chunks() > 1 and target.n_chunks() > 1
    assert _pldt_check_numpy(source, target, (9, 1)) is None


@pytest.mark.parametrize("values,target", [([0, 1001, 2000], [0, 1, 2]),
                                          ([0, -1001, 2000], [0, -2, 2]),
                                          ([0, None, 2000], [0, 1, 2])])
def test_numpy_temporal_check_reports_first_global_invalid_row(values, target):
    source = pl.concat([pl.Series(values[:1], dtype=pl.Datetime("ns")),
                        pl.Series(values[1:], dtype=pl.Datetime("ns"))], rechunk=False)
    with pytest.raises(ValueError, match=r"Pldt\.__array__\(\): data\[1\]"):
        _pldt_check_numpy(source, pl.Series(target, dtype=pl.Int64), (9, 1))


@pytest.mark.parametrize("target", [None, -(1 << 63)])
def test_numpy_temporal_check_rejects_valid_date_becoming_nat(target):
    with pytest.raises(OverflowError, match=r"data\[0\]"):
        _pldt_check_numpy(pl.Series([0], dtype=pl.Datetime("ns")),
                          pl.Series([target], dtype=pl.Int64), (9, 1))


def test_numpy_temporal_check_does_not_wrap_large_linear_products():
    with pytest.raises(OverflowError, match="NumPy datetime epoch overflow"):
        _pldt_check_numpy(pl.Series([0], dtype=pl.Datetime("ns")),
                          pl.Series([(1 << 63) - 1], dtype=pl.Int64), (2, (1 << 31) - 1))


@pytest.mark.parametrize("unit,source_values,raw,code", [
    ("ns", [0, 31_536_000_000_000_000], [0, 1], 0),
    ("ns", [0, 2_678_400_000_000_000], [0, 1], 1),
    ("ns", [1, -1, None], [1000, -1000, None], -1),
    ("ns", [1, -1, None], [1_000_000, -1_000_000, None], -2),
    ("ns", [1, -1, None], [1_000_000_000, -1_000_000_000, None], -3),
])
def test_numpy_temporal_check_preserves_calendar_and_subnanosecond_roles(unit, source_values, raw, code):
    assert _pldt_check_numpy(pl.Series(source_values, dtype=pl.Datetime(unit)),
                             pl.Series(raw, dtype=pl.Int64), (code, 1)) is None


def test_numpy_temporal_check_keeps_null_and_empty_validation_order():
    # These private-call controls preserve the pre-existing lazy decoder order.
    source = pl.Series([None], dtype=pl.Datetime("ns"))
    for target in (pl.Series([None], dtype=pl.Null), pl.Series([None], dtype=pl.Int64)):
        assert _pldt_check_numpy(source, target, (9, 0)) is None
    assert _pldt_check_numpy(pl.Series([], dtype=pl.Datetime("ns")),
                             pl.Series([], dtype=pl.String), (9, 0)) is None
    with pytest.raises(ValueError, match="length"):
        _pldt_check_numpy(source, pl.Series([], dtype=pl.Int64), (9, 1))


@pytest.mark.parametrize("dtype", [pl.Int8, pl.Int64, pl.UInt64, pl.Float32, pl.Float64])
def test_numpy_numeric_check_fallback_preserves_complete_source_ticks(dtype):
    source = pl.Series([0, 1, 2], dtype=pl.Datetime("us"))
    assert _pldt_check_numpy(source, pl.Series([0, 1, 2], dtype=dtype), None) is None
    with pytest.raises(ValueError, match=r"data\[1\]"):
        _pldt_check_numpy(source, pl.Series([0, 2, 2], dtype=dtype), None)


def test_numpy_numeric_check_rejects_missing_and_float_precision_loss():
    with pytest.raises(ValueError, match="missing date"):
        _pldt_check_numpy(pl.Series([None], dtype=pl.Datetime("ns")),
                          pl.Series([0], dtype=pl.Int64), None)
    with pytest.raises(ValueError, match="complete date tick"):
        _pldt_check_numpy(pl.Series([(1 << 53) + 1], dtype=pl.Datetime("ns")),
                          pl.Series([float((1 << 53) + 1)], dtype=pl.Float64), None)
