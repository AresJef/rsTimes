"""A prepared calendar workspace must keep each row's clock, target and errors."""
from datetime import timedelta, tzinfo

import numpy as np
import pytest

from rstimes import Pddt


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_repeated_day_with_varying_clocks_and_target_dates(unit):
    n = 64
    data = (np.datetime64("2024-05-07T00:00:00.123456789", "ns")
            + np.arange(n) * np.timedelta64(137, "s")).astype(f"datetime64[{unit}]")
    data[7] = np.datetime64("NaT", unit)
    years, months, days = 2021 + np.arange(n) % 4, 1 + np.arange(n) % 12, 1 + np.arange(n) % 28
    expected = []
    for i, value in enumerate(data):
        if np.isnat(value):
            expected.append("NaT")
        else:
            clock = np.datetime_as_string(value, unit=unit).split("T")[1]
            expected.append(f"{years[i]:04d}-{months[i]:02d}-{days[i]:02d}T{clock}")
    source = Pddt(data, name="workspace")
    result = source.to_date(year=years, month=months, day=days)
    assert result.asi8.tolist() == np.array(expected, dtype=data.dtype).view("i8").tolist()
    assert result.unit == unit and result.name == "workspace"
    assert source.to_date() is source


def test_calendar_workspace_keeps_nanoseconds_and_explicit_microsecond_reset():
    data = np.datetime64("2024-05-07T01:02:03.123456789", "ns") + np.arange(64) * np.timedelta64(137, "s")
    source = Pddt(data)
    expected = data + np.timedelta64(2, "h") + np.timedelta64(3, "us") + np.timedelta64(4, "ns")
    assert source.add(hours=2, microseconds=3, nanoseconds=4).asi8.tolist() == expected.view("i8").tolist()
    micros = np.arange(64) * 1000
    expected = data.astype("datetime64[s]").astype("datetime64[ns]") + micros.astype("timedelta64[us]")
    assert source.to_datetime(microsecond=micros).asi8.tolist() == expected.view("i8").tolist()


def test_calendar_workspace_keys_include_zero_negative_and_wide_years():
    source = Pddt(np.array(["0000-01-31", "-0001-12-31", "2024-01-31", "12000-01-31"], dtype="datetime64[us]"))
    expected = np.array(["0000-02-29", "-0001-02-28", "2024-02-29", "12000-02-29"], dtype="datetime64[us]")
    assert source.to_date(month=2, day=31).asi8.tolist() == expected.view("i8").tolist()


def test_later_dynamic_zone_error_precedes_final_unit_loss():
    armed = False
    marker = RuntimeError("second source timezone failed")

    class Zone(tzinfo):
        def utcoffset(self, value):
            if armed and value is not None and value.day == 8:
                raise marker
            return timedelta(0)

        def dst(self, value):
            return timedelta(0)

        def tzname(self, value):
            return "DYNAMIC"

    data = np.array(["2024-05-07", "2024-05-08"], dtype="datetime64[s]")
    source = Pddt(data, unit="s", tz=Zone())
    armed = True
    with pytest.raises(RuntimeError) as error:
        source.to_datetime(microsecond=[1, 0])
    assert error.value is marker
    assert source.asi8.tolist() == data.view("i8").tolist()
