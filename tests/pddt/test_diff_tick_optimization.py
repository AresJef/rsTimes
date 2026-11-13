"""Storage-tick optimization must retain mathematical boundary counts."""
import numpy as np
import pytest

from rstimes import Pddt


SCALES = {"s": 1_000_000_000, "ms": 1_000_000, "us": 1_000, "ns": 1}
STEPS = {
    "D": 86_400_000_000_000,
    "h": 3_600_000_000_000,
    "min": 60_000_000_000,
    "s": 1_000_000_000,
    "ms": 1_000_000,
    "us": 1_000,
    "ns": 1,
}


@pytest.mark.parametrize("storage", SCALES)
@pytest.mark.parametrize("boundary", STEPS)
def test_diff_counts_negative_boundaries_in_storage_ticks(storage, boundary):
    ticks = [-86_401, -60_001, -1, 0, 1, 60_001, 86_401]
    values = Pddt(np.array(ticks, dtype=f"datetime64[{storage}]"))
    expected = [tick * SCALES[storage] // STEPS[boundary] for tick in ticks]
    assert values.diff(np.datetime64(0, "ns"), boundary).tolist() == expected


@pytest.mark.parametrize("storage", SCALES)
def test_diff_coarsening_retains_full_tick_range_and_nat(storage):
    ticks = [-2**63 + 1, -1, 0, 1, 2**63 - 1]
    values = Pddt(np.array(ticks + [-2**63], dtype="i8").view(f"datetime64[{storage}]"))
    result = values.diff(np.datetime64(0, "s"), "D")
    expected = [tick * SCALES[storage] // STEPS["D"] for tick in ticks]
    assert result[:-1].tolist() == expected
    assert result.isna().tolist() == [False] * len(ticks) + [True]


def test_diff_scaling_still_rejects_real_result_overflow():
    values = Pddt(np.array([2**63 - 1], dtype="i8").view("datetime64[s]"))
    with pytest.raises(OverflowError):
        values.diff(np.datetime64(0, "ns"), "ns")
