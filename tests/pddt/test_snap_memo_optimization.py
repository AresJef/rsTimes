"""A local Snap memo cannot leak dates or suppress dynamic protocols."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from rstimes import Pddt


@pytest.mark.parametrize("region", ["America/New_York", "Australia/Lord_Howe", "Pacific/Apia"])
@pytest.mark.parametrize("period", ["h", "D", "Monday", "M", "April"])
def test_snap_batch_cache_matches_independent_single_rows(region, period):
    days = ["2024-11-03T05:45", "2024-11-03T06:15", "2024-03-10T07:15",
            "2011-12-30T20:00", "2024-10-05T15:45", "2024-11-03T05:45"]
    values = np.array(days + ["NaT"], dtype="datetime64[us]")
    x = Pddt(values, tz="UTC").tz_convert(ZoneInfo(region))
    expected = [x[i:i+1].snap(period).asi8[0] for i in range(len(x))]
    assert x.snap(period).asi8.tolist() == expected
    assert x[::-1].snap(period).asi8.tolist() == list(reversed(expected))


def test_snap_zoneinfo_subclass_preserves_dynamic_offset_calls():
    calls = []

    class Dynamic(ZoneInfo):
        def utcoffset(self, value):
            calls.append(None if value is None else (value.year, value.month, value.day, value.fold))
            return super().utcoffset(value)

    zone = Dynamic("America/New_York")
    x = Pddt([datetime(2024, 5, 7, 12, tzinfo=zone)] * 3)
    calls.clear()
    result = x.snap("Monday")
    probes = [v for v in calls if v is not None and v[:3] == (2024, 5, 6)]
    assert len(probes) >= 6
    assert result.day.tolist() == [6, 6, 6]
