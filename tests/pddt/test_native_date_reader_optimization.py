"""Homogeneous tick decoding retains units, missing values and late errors."""
from datetime import timedelta, tzinfo
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from rstimes import Pddt


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("key", [None, "UTC", "America/New_York"])
def test_native_unit_conversion_and_localization_preserve_sliced_input(unit, key):
    data = (np.datetime64("2024-05-07T01:02:03", "s")
            + np.arange(8) * np.timedelta64(137, "s")).astype(f"datetime64[{unit}]")
    data[4] = np.datetime64("NaT", unit)
    source = data[::2]
    saved = data.copy()
    selected = "ns" if unit != "ns" else "us"
    zone = None if key is None else ZoneInfo(key)
    expected = pd.DatetimeIndex(source)
    if zone is not None:
        expected = expected.tz_localize(zone)
    expected = expected.as_unit(selected)
    result = Pddt(source, unit=selected, tz=zone, name="source")
    assert result.asi8.tolist() == expected.asi8.tolist()
    assert result.unit == selected and result.name == "source"
    assert str(result.tz) == str(expected.tz)
    assert data.view("i8").tolist() == saved.view("i8").tolist()


def test_later_timezone_error_precedes_first_row_precision_failure():
    marker = RuntimeError("second local date failed")

    class Zone(tzinfo):
        def utcoffset(self, value):
            if value is not None and value.day == 8:
                raise marker
            return timedelta(0)

        def dst(self, value):
            return timedelta(0)

        def tzname(self, value):
            return "DYNAMIC"

    source = np.array(["2024-05-07T00:00:00.000000001", "2024-05-08"],
                      dtype="datetime64[ns]")
    saved = source.view("i8").tolist()
    with pytest.raises(RuntimeError) as error:
        Pddt(source, unit="us", tz=Zone())
    assert error.value is marker
    assert source.view("i8").tolist() == saved
