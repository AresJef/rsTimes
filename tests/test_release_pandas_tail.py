"""Preserve real Timestamp sub-microsecond data across pandas2 and pandas3."""
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from rstimes import Delta


class HiddenTail(pd.Timestamp):
    """Hide Python properties without changing the actual Timestamp value."""

    @property
    def nanosecond(self):
        return 0


@pytest.mark.parametrize("year", [1970, 1972, 2024])
@pytest.mark.parametrize("direction", ["left", "right", "many"])
def test_relative_delta_retains_real_tail(year, direction):
    value = pd.Timestamp(f"{year}-01-02 03:04:05.000001123")
    value.__class__ = HiddenTail
    expected = value + timedelta(microseconds=1)
    delta = Delta(microseconds=1)
    result = delta + value if direction == "left" else value + delta if direction == "right" else delta.apply_many([value])[0]
    assert result == expected
    assert pd.Timestamp.nanosecond.__get__(result) == 123


@pytest.mark.parametrize("unit", ["s", "ms", "us"])
def test_zero_tail_does_not_narrow_wide_timestamp(unit):
    value = pd.Timestamp(np.datetime64("12024-01-01", unit))
    result = value + Delta(days=1)
    assert result.year == 12024 and result.day == 2
    assert result.asm8.dtype == value.asm8.dtype
