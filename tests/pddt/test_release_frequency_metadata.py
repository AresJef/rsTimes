"""Frequency metadata remains valid across the supported pandas2/3 containers."""
from datetime import timedelta
import copy
import pickle

import numpy as np
import pandas as pd
import pytest
from rstimes import Delta, Pddt


@pytest.mark.parametrize("operation", [
    lambda x: x + Delta(days=1),
    lambda x: x + timedelta(days=1),
    lambda x: x.add(days=1),
    lambda x: x.to_date(day=2),
    lambda x: x.to_start_of("h"),
    lambda x: x.round("h"),
    lambda x: x.fsp(3),
])
def test_valid_hourly_metadata_and_units_are_preserved(operation):
    x = Pddt.date_range("2024-01-01", periods=3, freq="h", unit="us", name="events")
    result = operation(x)
    assert type(result) is Pddt and result.unit == "us" and result.name == "events"
    assert result.freq == pd.offsets.Hour()
    np.testing.assert_array_equal(np.diff(result.asi8), [3_600_000_000] * 2)


def test_invalid_frequency_is_dropped_without_changing_date_values():
    x = Pddt.date_range("2024-01-01", periods=3, freq="h", unit="us")
    result = x.to_time(hour=0)
    assert result.freq is None and result.unit == "us"
    assert result.asi8.tolist() == [1_704_067_200_000_000] * 3


def test_no_frequency_nanoseconds_and_nat_survive_calendar_arithmetic():
    result = Pddt(["2024-01-31T00:00:00.123456789", None], unit="ns") + Delta(months=1)
    assert result.freq is None and result.unit == "ns"
    assert result[0].isoformat() == "2024-02-29T00:00:00.123456789"
    assert result.isna().tolist() == [False, True]


def test_frequency_core_and_underscore_business_state_remain_separate():
    x = Pddt.date_range("2024-01-01", periods=2, freq="D", unit="us", name="events")
    x._business = [1]
    assert x.__getstate__() == {"_business": [1]}
    for result in (copy.copy(x), copy.deepcopy(x), pickle.loads(pickle.dumps(x))):
        assert result.freq == pd.offsets.Day() and result.name == "events"
        assert result.unit == "us" and result._business == [1]
        np.testing.assert_array_equal(result.asi8, x.asi8)
