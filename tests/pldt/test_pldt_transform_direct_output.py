"""Polars typed output retains full validity and deferred output failures."""
import numpy as np
import polars as pl
import pytest

from rstimes import Pldt


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
@pytest.mark.parametrize("zone", [None, "UTC", "Etc/GMT-8", "America/New_York"])
@pytest.mark.parametrize("host", ["eager", "expr"])
def test_chunked_transform_keeps_ticks_missingness_and_metadata(unit, zone, host):
    raw = np.array(["2024-01-31T12:34:56", "2024-03-31T01:02:03"],
                   dtype=f"datetime64[{unit}]").view("i8").tolist()
    # March 31 at 01:02 UTC is March 30 at 21:02 in New York. Its
    # one-month local move is April 30 at 21:02, hence May 1 in UTC.
    second = "2024-05-01T01:02:03" if zone == "America/New_York" else "2024-04-30T01:02:03"
    expected = np.array(["2024-02-29T12:34:56", second],
                        dtype=f"datetime64[{unit}]").view("i8").tolist()
    chunks = [pl.Series("events", [raw[0], None], dtype=pl.Int64),
              pl.Series("events", [raw[1]], dtype=pl.Int64)]
    source = Pldt(pl.concat(chunks, rechunk=False).cast(pl.Datetime(unit, zone)))
    before = source.to_physical().to_list()
    if host == "eager":
        result = source.add(months=1)
    else:
        result = pl.DataFrame(source).select(pl.col("events").pldt.add(months=1)).to_series()
    assert result.to_physical().to_list() == [expected[0], None, expected[1]]
    assert result.is_null().to_list() == [False, True, False]
    assert result.dtype == source.dtype and result.name == "events"
    assert source.to_physical().to_list() == before


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
def test_valid_minimum_is_kept_separate_from_null(unit):
    source = Pldt(pl.Series("events", [-(1 << 63), None, -(1 << 63)+1], dtype=pl.Int64)
                  .cast(pl.Datetime(unit)))
    result = source.sub(**{{"ms": "milliseconds", "us": "microseconds", "ns": "nanoseconds"}[unit]:
                          [0, 0, 1]})
    assert result.to_physical().to_list() == [-(1 << 63), None, -(1 << 63)]
    assert result.is_null().to_list() == [False, True, False]
    assert source.add().to_physical().to_list() == [-(1 << 63), None, -(1 << 63)+1]


@pytest.mark.parametrize("values,changes,expected_type,expected_message", [
    ([0, (1 << 63)-1], {"nanoseconds": [1, 0], "days": [0, 1]}, ValueError,
     "Pldt.add(): data[0]: source precision cannot fit the selected unit without loss; choose a finer unit or explicitly use as_unit"),
    ([(1 << 63)-1, 0], {"nanoseconds": [0, 1], "days": [1, 0]}, OverflowError,
     "Pldt.add(): data[0]: date exceeds the selected unit capacity; explicitly select a coarser supported unit"),
    ([0, 0], {"nanoseconds": [1, 0], "years": [0, (1 << 63)-1]}, OverflowError,
     "Pldt.add(): data[1]: integer overflow in Delta date arithmetic"),
    ([(1 << 63)-1, 0], {"days": [1, 0], "years": [0, (1 << 63)-1]}, OverflowError,
     "Pldt.add(): data[1]: integer overflow in Delta date arithmetic"),
])
def test_later_transform_failure_precedes_first_output_failure(values, changes, expected_type, expected_message):
    source = Pldt(values, unit="us")
    before = source.to_physical().to_list()
    with pytest.raises(expected_type) as error:
        source.add(**changes)
    assert str(error.value) == expected_message
    assert source.to_physical().to_list() == before


@pytest.mark.parametrize("unit", ["ms", "us"])
def test_wide_year_cancellation_preserves_one_final_calendar_move(unit):
    dates = np.array(["0000-01-31", "-0001-12-31", "12000-01-31"], dtype=f"datetime64[{unit}]")
    expected = np.array(["0000-02-29", "0000-01-31", "12000-02-29"], dtype=dates.dtype)
    result = Pldt(dates).add(months=1, microseconds=1, nanoseconds=-1000)
    assert result.to_physical().to_list() == expected.view("i8").tolist()


@pytest.mark.parametrize("host", ["eager", "expr"])
def test_later_regional_gap_error_precedes_earlier_precision_failure(host):
    source = Pldt(["2011-12-28T12:00", "2011-12-29T12:00"], unit="us",
                  tz="Pacific/Apia", name="events")
    if host == "eager":
        call = lambda: source.add(days=[0, 1], nanoseconds=[1, 0])
        expected = ValueError
    else:
        call = lambda: pl.DataFrame(source).select(
            pl.col("events").pldt.add(days=[0, 1], nanoseconds=[1, 0]))
        expected = pl.exceptions.ComputeError
    with pytest.raises(expected, match=r"(?:data\[1\]|batch item 1).*selected calendar day has no valid local result"):
        call()


@pytest.mark.parametrize("host", ["eager", "expr"])
def test_date_source_scales_days_once_and_returns_millisecond_datetime(host):
    source = pl.Series("events", [19753, None], dtype=pl.Int32).cast(pl.Date)
    if host == "eager":
        result = source.pldt.add(months=1)
    else:
        result = pl.DataFrame(source).select(pl.col("events").pldt.add(months=1)).to_series()
    assert result.dtype == pl.Datetime("ms") and result.name == "events"
    assert result.to_physical().to_list() == [1709164800000, None]


@pytest.mark.parametrize("tick,increment", [((1 << 63)-1, 1), (-(1 << 63), -1)])
def test_nanosecond_encoding_keeps_both_capacity_endpoints(tick, increment):
    source = Pldt([tick, None], unit="ns")
    with pytest.raises(OverflowError) as error:
        source.add(nanoseconds=increment)
    assert str(error.value) == (
        "Pldt.add(): data[0]: date exceeds the selected unit capacity; "
        "explicitly select a coarser supported unit")
    assert source.to_physical().to_list() == [tick, None]


def test_nanosecond_output_error_still_follows_later_calendar_failure():
    source = Pldt([(1 << 63)-1, 0], unit="ns")
    with pytest.raises(OverflowError) as error:
        source.add(days=[1, 0], years=[0, (1 << 63)-1])
    assert str(error.value) == "Pldt.add(): data[1]: integer overflow in Delta date arithmetic"


def test_all_null_nanoseconds_do_not_create_a_precision_or_capacity_error():
    source = Pldt([None, None], unit="ns", name="events")
    result = source.add(nanoseconds=1)
    assert result.dtype == pl.Datetime("ns") and result.name == "events"
    assert result.to_physical().to_list() == [None, None]


@pytest.mark.parametrize("unit,argument", [("ms", "milliseconds"), ("us", "microseconds")])
@pytest.mark.parametrize("tick,increment", [((1 << 63)-1, 1), (-(1 << 63), -1)])
def test_coarse_encoding_checks_signed_capacity_after_calendar_work(unit, argument, tick, increment):
    source = Pldt([tick, None], unit=unit)
    with pytest.raises(OverflowError) as error:
        source.add(**{argument: increment})
    assert str(error.value) == (
        "Pldt.add(): data[0]: date exceeds the selected unit capacity; "
        "explicitly select a coarser supported unit")
    assert source.to_physical().to_list() == [tick, None]


@pytest.mark.parametrize("unit", ["ms", "us"])
@pytest.mark.parametrize("increment", [-1, 1])
def test_coarse_encoding_rejects_either_sign_of_nonzero_nanosecond_remainder(unit, increment):
    source = Pldt([-1, None, 0], unit=unit)
    with pytest.raises(ValueError) as error:
        source.add(nanoseconds=increment)
    assert str(error.value) == (
        "Pldt.add(): data[0]: source precision cannot fit the selected unit without loss; "
        "choose a finer unit or explicitly use as_unit")
    assert source.to_physical().to_list() == [-1, None, 0]


@pytest.mark.parametrize("unit", ["ms", "us"])
def test_coarse_encoding_keeps_exact_cross_field_cancellation_and_validity(unit):
    ticks = [-1, None, -(1 << 63), (1 << 63)-1]
    source = Pldt(ticks, unit=unit, name="events")
    result = source.add(microseconds=1, nanoseconds=-1000)
    assert result.to_physical().to_list() == ticks
    assert result.is_null().to_list() == [False, True, False, False]
    assert result.dtype == source.dtype and result.name == "events"
