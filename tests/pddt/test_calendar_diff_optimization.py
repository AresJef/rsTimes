"""Calendar boundary reuse keeps wide years, negative ticks and missing masks."""
import numpy as np
import pytest

from rstimes import Pddt


def indices(values, boundary):
    if boundary == "Y":
        return values.astype("datetime64[Y]").view("i8")
    months = values.astype("datetime64[M]").view("i8")
    return months // 3 if boundary == "Q" else months


@pytest.mark.parametrize("storage", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("boundary", ["Y", "Q", "M"])
def test_calendar_diff_full_storage_range_and_nat(storage, boundary):
    raw = np.array([-2**63 + 1, -100000, -1, 0, 1, 100000, 2**63 - 1], dtype="i8")
    data = raw.view(f"datetime64[{storage}]")
    source = Pddt(np.append(data, np.datetime64("NaT", storage)))
    result = source.diff(np.datetime64(0, "s"), boundary)
    assert result[:-1].tolist() == indices(data, boundary).tolist()
    assert result.isna().tolist() == [False] * len(data) + [True]


@pytest.mark.parametrize("storage", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("boundary", ["Y", "Q", "M"])
def test_calendar_diff_repeated_random_and_reverse_days(storage, boundary):
    days = (np.arange(1024, dtype="i8") * 8191) % 73049
    data = (np.datetime64("1900-01-01", "D") + days).astype(f"datetime64[{storage}]")
    data[12:32] = data[11]
    target = np.roll(data[::-1], 7).copy()
    result = Pddt(data).diff(target, boundary)
    assert result.tolist() == (indices(data, boundary) - indices(target, boundary)).tolist()


@pytest.mark.parametrize("boundary", ["Y", "Q", "M"])
def test_calendar_diff_zero_negative_and_wide_years(boundary):
    data = np.array(["0000-01-01", "-0001-12-31", "0000-01-01", "12000-02-29",
                     "1969-12-31", "1970-01-01"], dtype="datetime64[us]")
    target = np.datetime64("1970-05-01", "us")
    assert Pddt(data).diff(target, boundary).tolist() == (
        indices(data, boundary) - indices(np.array([target]), boundary)[0]
    ).tolist()
