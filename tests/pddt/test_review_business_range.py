"""Native business frequencies contribute a precision floor before generation."""
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from rstimes import Pddt

NS_EPOCH = datetime(1970, 1, 1)


@pytest.mark.parametrize("endpoint", (date(2024, 1, 1), np.datetime64("2024-01-01", "s")))
@pytest.mark.parametrize("custom, unit, offset, step, scale", [
    (False, "us", 1, timedelta(days=1), 1_000_000),
    (False, "us", -1, timedelta(days=1), 1_000_000),
    (True, "ms", 1, timedelta(days=2), 1_000),
])
@pytest.mark.parametrize("periods", [0, 1, 2])
def test_subsecond_business_range_sets_minimum_output_unit(endpoint, custom, unit, offset, step, scale, periods):
    increment = timedelta(microseconds=offset * (1_000_000 // scale))
    frequency = (pd.offsets.CustomBusinessDay(holidays=["2024-01-02"], offset=increment)
                 if custom else pd.offsets.BusinessDay(offset=increment))
    result = Pddt.date_range(endpoint, periods=periods, freq=frequency, name="stamp")
    first = (datetime(2024, 1, 1) - NS_EPOCH) // timedelta(microseconds=1_000_000 // scale)
    # The existing pandas 3-compatible one-period rule yields no row when
    # a negative business offset puts the calculated end before the start.
    expected = [] if offset < 0 and periods == 1 else [
        first, first + step.days * 86_400 * scale + offset,
    ][:periods]
    assert result.name == "stamp" and result.unit == unit
    assert result.asi8.tolist() == expected
    assert result.freq == frequency
    with pytest.raises(ValueError, match="frequency|unit|precision"):
        Pddt.date_range(endpoint, periods=periods, freq=frequency, unit="s")
    explicit = Pddt.date_range(endpoint, periods=periods, freq=frequency, unit="ns")
    assert explicit.unit == "ns"
    assert explicit.asi8.tolist() == [v * (1_000_000_000 // scale) for v in expected]


def test_business_precision_is_preserved_through_endpoint_localization():
    start = date(2024, 3, 8)
    offset = timedelta(microseconds=1)
    frequency = pd.offsets.BusinessDay(offset=offset)
    result = Pddt.date_range(start, periods=2, freq=frequency, tz="America/New_York")
    epoch = NS_EPOCH.replace(tzinfo=timezone.utc)
    first = datetime(2024, 3, 8, 5, tzinfo=timezone.utc)
    second = datetime(2024, 3, 11, 4, 0, 0, 1, tzinfo=timezone.utc)
    assert result.unit == "us"
    assert result.asi8.tolist() == [(value - epoch) // offset for value in (first, second)]


def _ranges(options, expected, *, unit="us", zone=None):
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    pddt = Pddt.date_range(**options)
    pldt = Pldt.date_range(**{**options, "unit": unit})
    assert type(pddt) is Pddt and type(pldt) is Pldt
    assert pddt.asi8.tolist() == pldt.to_physical().to_list() == expected
    assert pddt.isna().tolist() == pldt.is_null().to_list() == [False] * len(expected)
    assert pddt.unit == unit and pldt.dtype == pl.Datetime(unit, zone)
    assert (str(pddt.tz) if pddt.tz else None) == zone
    assert pddt.name == pldt.name == options["name"]
    if pddt.freq is not None:
        assert pddt.freq == options["freq"]


@pytest.mark.parametrize("factory,n,day,count,ticks", [
    ("CustomBusinessMonthBegin", -1, 1, 1, []),
    ("CustomBusinessMonthBegin", -1, 9, 1, []),
    ("CustomBusinessMonthBegin", -1, 9, 2, [1704067199999999, 1701475199999998]),
    ("CustomBusinessMonthEnd", 1, 1, 1, [1706659199999999, 1706745599999998]),
    ("CustomBusinessMonthBegin", 1, 9, 4,
     [1706745599999999, 1706831999999998, 1709337599999997, 1712015999999996]),
])
def test_custom_work_month_roll_end_and_emission_use_full_offset(factory, n, day, count, ticks):
    freq = getattr(pd.offsets, factory)(n, offset=-timedelta(microseconds=1))
    _ranges(dict(start=date(2024, 1, day), periods=count, freq=freq, name="dates"), ticks)


def test_normalized_custom_work_month_rolls_in_the_requested_direction():
    month_end = pd.offsets.CustomBusinessMonthEnd
    freq = month_end(normalize=True)
    _ranges(dict(end="2024-01-31 12:34:56", periods=1, freq=freq, unit="us", name="dates"),
            [1706659200000000])
    freq = month_end(normalize=True, offset=-timedelta(microseconds=1))
    _ranges(dict(start="2024-01-09 12:34:56", periods=2, freq=freq, unit="us", name="dates"),
            [1706659200000000, 1709078400000000])
    _ranges(dict(end="2024-01-09 12:34:56", periods=2, freq=-freq, unit="us", name="dates"),
            [1709078400000000])


def test_custom_work_month_dst_reverse_bounds_and_inclusive():
    # March 11 and April 1 are the first business days with this holiday set.
    freq = pd.offsets.CustomBusinessMonthBegin(-2, holidays=[
        "2024-03-01", "2024-03-04", "2024-03-05", "2024-03-06",
        "2024-03-07", "2024-03-08",
    ])
    zone = "America/New_York"
    options = dict(start="2024-05-01 08:00", end="2024-01-01 08:00",
                   freq=freq, unit="us", name="dates", tz=zone, inclusive="right")
    # Jan 1 is a workday for the given weekmask. UTC clocks move with DST.
    expected = [datetime(2024, 3, 11, 12, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 13, tzinfo=timezone.utc)]
    epoch = NS_EPOCH.replace(tzinfo=timezone.utc)
    _ranges(options, [(value - epoch) // timedelta(microseconds=1) for value in expected], zone=zone)


def test_custom_work_month_zero_count_and_nonadvancing_frequency():
    pytest.importorskip("polars")
    from rstimes import Pldt

    freq = pd.offsets.CustomBusinessMonthEnd(2)
    _ranges(dict(start="2024-01-01", periods=0, freq=freq, unit="us", name="dates"), [])
    for owner in (Pddt, Pldt):
        with pytest.raises(ValueError, match=r"frequency must not be zero"):
            owner.date_range("2024-01-01", periods=2, freq=pd.offsets.CustomBusinessMonthEnd(0), unit="us")
        with pytest.raises(ValueError, match=r"does not advance"):
            owner.date_range("2024-01-01", periods=3, unit="us",
                             freq=pd.offsets.CustomBusinessMonthEnd(offset=timedelta(days=-31)))


@pytest.mark.parametrize("freq_options, endpoint, expected", [
    (("CustomBusinessMonthBegin", 1, 1), {"start": "2024-01-01"},
     [1706745600000000001, 1709251200000000003, 1711929600000000007]),
    (("CustomBusinessMonthEnd", 3, -1), {"end": "2024-01-31 12:34:56"},
     [1680266096000000997, 1688128496000001993, 1695990896000002985]),
])
def test_s02_month_offsets_preserve_native_nanosecond_coordinates(freq_options, endpoint, expected):
    name, n, ns = freq_options
    freq = getattr(pd.offsets, name)(n, offset=pd.Timedelta(ns, "ns"))
    _ranges(dict(**endpoint, periods=4, freq=freq, unit="ns", name="stamp"), expected, unit="ns")


@pytest.mark.parametrize("name, start, ns, count, zone, expected", [
    ("BusinessDay", "2024-01-08 12:00:00.000000003", 1, 4, None,
     [1704715200000000003, 1704801600000000007, 1704888000000000015]),
    ("CustomBusinessDay", "2024-01-08 12:00:00.000000003", 1, 4, None,
     [1704715200000000003, 1704801600000000003, 1704888000000000003, 1704974400000000003]),
    ("BusinessDay", "2024-01-13 12:00:00.000000003", 1, 2, None,
     [1705320000000000007, 1705406400000000015]),
    ("CustomBusinessDay", "2024-01-13 12:00:00.000000003", 1, 2, None,
     [1705320000000000003, 1705406400000000003]),
    ("BusinessDay", "2024-01-13 12:00:00.000000003", -1, 2, None,
     [1705320000000000005, 1705406400000000009]),
    ("CustomBusinessDay", "2024-01-13 12:00:00.000000003", -1, 2, None,
     [1705319999999999003, 1705406399999998003]),
    ("CustomBusinessDay", "2024-03-08 12:00:00.000000003", -1, 4, "America/New_York",
     [1709917200000000003, 1710172799999999003, 1710259199999998003, 1710345599999997003]),
])
def test_s02_daily_offset_respects_real_frequency_kind_and_weekend_roll(name, start, ns, count, zone, expected):
    freq = getattr(pd.offsets, name)(offset=pd.Timedelta(ns, "ns"))
    _ranges(dict(start=start, periods=count, freq=freq, unit="ns", tz=zone, name="stamp"),
            expected, unit="ns", zone=zone)


def test_s02_month_checked_capacity_applies_to_emitted_ticks():
    pytest.importorskip("polars")
    from rstimes import Pldt

    freq = pd.offsets.CustomBusinessMonthBegin(
        holidays=[date(2262, 4, d) for d in range(1, 11)], offset=pd.Timedelta(1, "ns"),
    )
    maximum = 2**63 - 1
    _ranges(dict(start="2262-03-31 23:47:16.854775403", end=maximum, freq=freq,
                 unit="ns", name="stamp"), [maximum], unit="ns")
    for owner in (Pddt, Pldt):
        with pytest.raises(OverflowError, match="capacity|outside|exceeds the requested unit"):
            owner.date_range("2262-03-31 23:47:16.854775805", periods=1, freq=freq, unit="ns")


@pytest.mark.parametrize("name, offset, expected", [
    ("BusinessDay", 1, [1705363200000000000, 1705449600000000000]),
    ("CustomBusinessDay", -1, [1705276800000000000]),
])
def test_s02_forward_weekend_roll_normalizes_after_the_submicrosecond_shift(name, offset, expected):
    freq = getattr(pd.offsets, name)(offset=pd.Timedelta(offset, "ns"), normalize=True)
    _ranges(dict(start="2024-01-13 23:59:59.999999999", periods=2, freq=freq, unit="ns",
                 name="stamp"), expected, unit="ns")


def test_s02_negative_epoch_month_roundtrip_and_normalization():
    offset = pd.Timedelta(-2, "ns")
    month = pd.offsets.CustomBusinessMonthBegin
    start = "1969-12-01 00:00:00.000000001"
    _ranges(dict(start=start, end=0, freq=month(offset=offset), unit="ns", name="stamp"), [0], unit="ns")
    freq = pd.offsets.CustomBusinessMonthEnd(offset=offset, normalize=True)
    _ranges(dict(start="1969-12-01 12:00:00.000000001", end=0, freq=freq, unit="ns", name="stamp"),
            [-86_400_000_000_000], unit="ns")


@pytest.mark.parametrize("name, expected", [
    ("CustomBusinessMonthEnd", [1703721600000000]),
    ("BusinessDay", [1706659200000000]),
    ("CustomBusinessDay", [1706659200000000]),
])
@pytest.mark.parametrize("inclusive", ("both", "left", "right", "neither"))
def test_s02_explicit_zero_period_uses_existing_calendar_bounds(name, expected, inclusive):
    freq = getattr(pd.offsets, name)(offset=-timedelta(days=1))
    if name != "CustomBusinessMonthEnd" and inclusive in ("left", "neither"):
        expected = []
    _ranges(dict(end="2024-01-31", periods=0, freq=freq, unit="us", name="stamp", inclusive=inclusive), expected)


def test_s02_zero_period_propagates_nonadvance_and_keeps_bounds_validation():
    pytest.importorskip("polars")
    from rstimes import Pldt

    freq = pd.offsets.CustomBusinessMonthBegin(
        -1, weekmask="Mon", holidays=[date(2024, 1, day) for day in (1, 8, 15, 22, 29)],
        offset=timedelta(microseconds=1),
    )
    for owner in (Pddt, Pldt):
        with pytest.raises(ValueError, match="does not advance"):
            owner.date_range(end="2024-01-09 12:34:56.000000003", periods=0, freq=freq,
                             unit="ns", tz="America/New_York")
        with pytest.raises(ValueError, match="preserved"):
            owner.date_range("2024-01-01 00:00:00.000000001", periods=0, freq="B", unit="us")

    _ranges(dict(start=5, end=0, periods=0, freq=None, unit="ns", name="stamp"), [], unit="ns")
    _ranges(dict(start=5, end=0, periods=4, freq=None, unit="ns", name="stamp"), [5, 3, 1, 0], unit="ns")


def test_s02_preserves_implicit_zero_when_rolled_start_is_after_end():
    freq = pd.offsets.BusinessDay(offset=timedelta(days=1))
    _ranges(dict(start="2024-02-03", end="2024-02-04", freq=freq, unit="us", name="stamp"), [])


@pytest.mark.parametrize("owner_name", ("Pddt", "Pldt"))
@pytest.mark.parametrize("frequency_name", ("BusinessDay", "CustomBusinessDay"))
def test_forward_workday_offset_crosses_midnight_before_frequency_normalize(owner_name, frequency_name):
    frequency = getattr(pd.offsets, frequency_name)(offset=timedelta(hours=2), normalize=True)
    expected = [(datetime(2024, 1, 16) - NS_EPOCH) // timedelta(microseconds=1)]
    options = dict(start="2024-01-13 23:00", periods=1, freq=frequency, unit="us", name="stamp")

    if owner_name == "Pddt":
        result = Pddt.date_range(**options)
        assert type(result) is Pddt
        ticks, missing = result.asi8.tolist(), result.isna().tolist()
        assert result.unit == "us" and result.tz is None
        assert result.freq is None or result.freq == frequency
    else:
        pl = pytest.importorskip("polars")
        from rstimes import Pldt

        result = Pldt.date_range(**options)
        assert type(result) is Pldt
        ticks, missing = result.to_physical().to_list(), result.is_null().to_list()
        assert result.dtype == pl.Datetime("us")
    assert len(result) == 1 and result.name == "stamp" and missing == [False]
    assert ticks == expected


@pytest.mark.parametrize("frequency_name", ("BusinessDay", "CustomBusinessDay"))
@pytest.mark.parametrize("endpoints,n,offset,normalize,day", [
    pytest.param({"end": "2024-01-13 23:00", "periods": 1}, 1, 2, False, 12, id="backward"),
    pytest.param({"end": "2024-01-13 23:00", "periods": 1}, -1, 2, False, 16, id="forward-from-end"),
    pytest.param({"start": "2024-01-13 23:00", "periods": 1}, 1, 2, True, 15, id="endpoint-normalize"),
    pytest.param({"start": "2024-01-13 10:00", "periods": 1}, 1, 2, False, 15, id="same-day"),
    pytest.param({"start": "2024-01-13 03:00", "end": "2024-01-15"}, 1, -2, False, 15, id="negative-offset"),
])
def test_normalized_workday_roll_depends_on_actual_direction(frequency_name, endpoints, n, offset, normalize, day):
    frequency = getattr(pd.offsets, frequency_name)(n, offset=timedelta(hours=offset), normalize=True)
    expected = [(datetime(2024, 1, day) - NS_EPOCH) // timedelta(microseconds=1)]
    _ranges(dict(**endpoints, freq=frequency, normalize=normalize, unit="us", name="stamp"), expected)


def test_forward_workday_offset_keeps_custom_holiday_calendar():
    frequency = pd.offsets.CustomBusinessDay(
        holidays=["2024-01-15"], offset=timedelta(hours=2), normalize=True,
    )
    expected = [(datetime(2024, 1, 17) - NS_EPOCH) // timedelta(microseconds=1)]
    _ranges(dict(start="2024-01-13 23:00", periods=1, freq=frequency, unit="us", name="stamp"), expected)
