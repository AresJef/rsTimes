"""Final-buffer transforms preserve wide results, sentinels and error ordering."""
from datetime import timedelta, timezone

import numpy as np
import pytest

from rstimes import Pddt


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("zone", [None, "UTC", timezone(timedelta(hours=8))])
def test_month_move_keeps_independent_ticks_and_missingness(unit, zone):
    dates = np.array(["2024-01-31T12:34:56", "NaT", "2024-03-31T01:02:03"],
                     dtype=f"datetime64[{unit}]")
    expected = np.array(["2024-02-29T12:34:56", "NaT", "2024-04-30T01:02:03"],
                        dtype=dates.dtype).view("i8").copy()
    if isinstance(zone, timezone):
        valid = expected != -(1 << 63)
        expected[valid] -= int(zone.utcoffset(None).total_seconds()) * {
            "s": 1, "ms": 1000, "us": 1_000_000, "ns": 1_000_000_000}[unit]
    source = Pddt(dates, tz=zone, name="events")
    before = source.asi8.copy()
    result = source.add(months=1)
    assert result.asi8.tolist() == expected.tolist()
    assert result.unit == unit and result.name == "events" and result.tz is source.tz
    assert source.asi8.tolist() == before.tolist()


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_wide_calendar_and_subsecond_cancellation(unit):
    dates = np.array(["0000-01-31", "-0001-12-31", "12000-01-31"],
                     dtype=f"datetime64[{unit}]") if unit != "ns" else np.array(
                         ["2024-01-31", "2024-03-31", "2024-05-31"], dtype="datetime64[ns]")
    expected = np.array(["0000-02-29", "0000-01-31", "12000-02-29"],
                        dtype=dates.dtype) if unit != "ns" else np.array(
                            ["2024-02-29", "2024-04-30", "2024-06-30"], dtype=dates.dtype)
    source = Pddt(dates)
    result = source.add(months=1, microseconds=1, nanoseconds=-1000)
    assert result.asi8.tolist() == expected.view("i8").tolist()
    assert source.add(microseconds=1, nanoseconds=-1000) is source


@pytest.mark.parametrize("values,changes,expected_type,expected_message", [
    ([0, (1 << 63)-1], {"nanoseconds": [1, 0], "days": [0, 1]}, ValueError,
     "Pddt.add(): result[0]: cannot preserve this date at the requested unit; choose a finer unit"),
    ([(1 << 63)-1, 0], {"nanoseconds": [0, 1], "days": [1, 0]}, OverflowError,
     "Pddt.add(): result[0]: date is outside the requested unit; explicitly choose a coarser unit"),
    ([0, 0], {"nanoseconds": [1, 0], "years": [0, (1 << 63)-1]}, OverflowError,
     "Pddt.add(): result[1]: integer overflow in Delta date arithmetic"),
    ([(1 << 63)-1, 0], {"days": [1, 0], "years": [0, (1 << 63)-1]}, OverflowError,
     "Pddt.add(): result[1]: integer overflow in Delta date arithmetic"),
])
def test_transform_errors_precede_deferred_output_errors(values, changes, expected_type, expected_message):
    source = Pddt(values, unit="us")
    before = source.asi8.copy()
    with pytest.raises(expected_type) as error:
        source.add(**changes)
    assert str(error.value) == expected_message
    assert source.asi8.tolist() == before.tolist()


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_valid_result_cannot_become_nat_sentinel(unit):
    source = Pddt([-(1 << 63)+1], unit=unit)
    with pytest.raises(OverflowError, match=r"result\[0\].*outside the requested unit"):
        source.sub(**{{"s": "seconds", "ms": "milliseconds", "us": "microseconds", "ns": "nanoseconds"}[unit]: 1})
    assert source.asi8.tolist() == [-(1 << 63)+1]


@pytest.mark.parametrize("dates", [[], [None], [None, None]])
def test_empty_and_missing_sources_still_check_arguments(dates):
    source = Pddt(dates, unit="us")
    assert source.add(nanoseconds=1) is source
    with pytest.raises(TypeError):
        source.add(days=True)
