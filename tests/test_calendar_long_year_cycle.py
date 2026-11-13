"""Standard datetime supplies independent ISO-year expectations for both columns."""

from datetime import date

import numpy as np
import pytest

import rstimes


def _constructor(name):
    pytest.importorskip("pandas" if name == "Pddt" else "polars")
    return getattr(rstimes, name)


@pytest.mark.parametrize("name", ["Pddt", "Pldt"])
@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
def test_long_year_matches_standard_datetime_for_every_cycle_position(name, unit):
    years = range(1800, 2200)
    source = np.array([f"{year:04d}-06-01" for year in years] + ["NaT"],
                      dtype=f"datetime64[{unit}]")
    expected = [date(year, 12, 28).isocalendar().week == 53 for year in years] + [False]

    result = _constructor(name)(source).is_long_year()

    assert list(result) == expected


@pytest.mark.parametrize("name", ["Pddt", "Pldt"])
def test_long_year_preserves_zero_negative_and_wide_years(name):
    years = [-400, -396, 0, 4, 10000, 10004, 1_000_000, 1_000_004]
    source = np.array([f"{year:04d}-06-01" for year in years], dtype="datetime64[ms]")
    expected = [date(2000 + year % 400, 12, 28).isocalendar().week == 53 for year in years]

    result = _constructor(name)(source).is_long_year()

    assert list(result) == expected


@pytest.mark.parametrize("name", ["Pddt", "Pldt"])
def test_same_day_query_cache_does_not_replace_row_specific_targets(name):
    source = np.array(["2024-06-01T01:00", "2024-06-01T02:00", "2024-06-01T03:00"],
                      dtype="datetime64[us]")
    result = _constructor(name)(source).is_year([2024, 2023, 2024])
    assert list(result) == [True, False, True]


@pytest.mark.parametrize("name", ["Pddt", "Pldt"])
def test_formatted_day_cache_distinguishes_iso_year_week_and_day_of_year(name):
    source = np.array(["2021-01-01", "2020-12-31", "2021-01-04"], dtype="datetime64[us]")
    result = _constructor(name)(source).strftime("%Y %j %V %G %j")
    assert list(result) == ["2021 001 53 2020 001", "2020 366 53 2020 366",
                            "2021 004 01 2021 004"]


def test_scalar_format_uses_the_same_query_identity_guard():
    from rstimes import Pydt

    assert Pydt(2021, 1, 1).strftime("%Y %j %V %G %j") == "2021 001 53 2020 001"
