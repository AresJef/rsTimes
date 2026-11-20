"""Large immutable transform snapshots retain values, ownership and errors."""
from datetime import timedelta, timezone

import numpy as np
import pytest

from rstimes import Pddt


@pytest.mark.parametrize("size", [16383, 16384, 16385, 65536])
@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("zone", [None, "UTC", timezone(timedelta(hours=8))])
def test_large_month_transform_keeps_full_independent_values(size, unit, zone):
    source_values = np.array(["2024-01-31T12:34:56.123456789", "NaT",
                              "2024-03-31T01:02:03.000000001"], dtype="datetime64[ns]").astype(f"datetime64[{unit}]")
    answer_values = np.array(["2024-02-29T12:34:56.123456789", "NaT",
                              "2024-04-30T01:02:03.000000001"], dtype="datetime64[ns]").astype(f"datetime64[{unit}]")
    expected = np.resize(answer_values, size).view("i8").copy()
    if isinstance(zone, timezone):
        valid = expected != -(1 << 63)
        expected[valid] -= 8 * 3600 * {"s": 1, "ms": 1000, "us": 1_000_000, "ns": 1_000_000_000}[unit]
    source = Pddt(np.resize(source_values, size), tz=zone, name="immutable input")
    before = source.asi8.copy()
    output = source.add(months=1)
    assert type(output) is Pddt and output.unit == unit and output.name == source.name
    assert output.tz is source.tz and np.array_equal(output.asi8, expected)
    assert np.array_equal(source.asi8, before)


@pytest.mark.parametrize("size", [16383, 16384, 16385])
@pytest.mark.parametrize("missing", [False, True])
def test_large_unchanged_results_return_the_same_actual_subclass(size, missing):
    class Events(Pddt):
        pass

    values = np.full(size, -(1 << 63) if missing else 1_714_842_123_123_456, dtype="i8")
    source = Events(values, unit="us", name="shared immutable dates")
    before = source.asi8.copy()
    assert source.add(microseconds=1, nanoseconds=-1000) is source
    assert np.array_equal(source.asi8, before)


@pytest.mark.parametrize("size", [16383, 16384, 16385])
def test_late_transform_error_precedes_an_earlier_pack_error(size):
    source = Pddt(np.zeros(size, dtype="i8"), unit="us")
    years = np.zeros(size, dtype="i8")
    years[-1] = (1 << 63) - 1
    nanos = np.zeros(size, dtype="i8")
    nanos[0] = 1
    with pytest.raises(OverflowError) as error:
        source.add(years=years, nanoseconds=nanos)
    assert str(error.value) == f"Pddt.add(): result[{size-1}]: integer overflow in Delta date arithmetic"
    assert not source.asi8.any()


@pytest.mark.parametrize("size", [16383, 16384, 16385])
def test_first_pack_error_retains_its_original_position_and_message(size):
    source = Pddt(np.zeros(size, dtype="i8"), unit="us")
    nanos = np.zeros(size, dtype="i8")
    nanos[2] = 1
    nanos[-1] = 2
    with pytest.raises(ValueError) as error:
        source.add(nanoseconds=nanos)
    assert str(error.value) == "Pddt.add(): result[2]: cannot preserve this date at the requested unit; choose a finer unit"
    assert not source.asi8.any()


@pytest.mark.parametrize("unit", ["us", "ns"])
@pytest.mark.parametrize("method,arguments,answer", [
    ("sub", {"months": 1}, ["2023-12-31T12:34:56.123456789", "NaT", "2024-02-29T01:02:03.000000001"]),
    ("to_year", {"offset": 1}, ["2025-01-31T12:34:56.123456789", "NaT", "2025-03-31T01:02:03.000000001"]),
    ("to_quarter", {"offset": 1}, ["2024-04-30T12:34:56.123456789", "NaT", "2024-06-30T01:02:03.000000001"]),
    ("to_month", {"offset": 1}, ["2024-02-29T12:34:56.123456789", "NaT", "2024-04-30T01:02:03.000000001"]),
    ("to_weekday", {"offset": 1, "weekday": 0}, ["2024-02-05T12:34:56.123456789", "NaT", "2024-04-01T01:02:03.000000001"]),
    ("to_day", {"offset": 1}, ["2024-02-01T12:34:56.123456789", "NaT", "2024-04-01T01:02:03.000000001"]),
    ("to_date", {"month": 2}, ["2024-02-29T12:34:56.123456789", "NaT", "2024-02-29T01:02:03.000000001"]),
    ("to_datetime", {"hour": 7, "microsecond": 123456}, ["2024-01-31T07:34:56.123456000", "NaT", "2024-03-31T07:02:03.123456000"]),
])
def test_large_transforms_cover_all_prepared_column_arities(unit, method, arguments, answer):
    pattern = np.array(["2024-01-31T12:34:56.123456789", "NaT", "2024-03-31T01:02:03.000000001"], dtype="datetime64[ns]").astype(f"datetime64[{unit}]")
    source = Pddt(np.resize(pattern, 16384), name="prepared arities")
    before = source.asi8.copy()
    output = getattr(source, method)(**arguments)
    expected = np.resize(np.array(answer, dtype="datetime64[ns]").astype(f"datetime64[{unit}]"), 16384)
    assert output.unit == unit and output.name == source.name and output.tz is None
    assert np.array_equal(output.asi8, expected.view("i8")) and np.array_equal(source.asi8, before)


def test_large_explicit_replace_policy_keeps_its_existing_path():
    source = Pddt(np.resize(np.array(["2024-01-31T12:34:56.123456789", "NaT", "2024-03-31T01:02:03.000000001"], dtype="datetime64[ns]"), 16384))
    expected = np.resize(np.array(["2023-01-31T12:34:56.123456789", "NaT", "2023-03-31T01:02:03.000000001"], dtype="datetime64[ns]"), 16384)
    assert np.array_equal(source.pddt.replace(year=2023).asi8, expected.view("i8"))
