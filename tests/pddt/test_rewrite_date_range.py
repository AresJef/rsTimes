"""Public range contracts: native generation, shared parsing and final ownership."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from _fixed_pandas3 import date_range as fixed_date_range
import pytest
from rstimes import Pddt, Configs

FREQUENCIES = ["500ns", "2us", "3ms", "5s", "15min", "2h", "D", "2D", "W", "W-MON", "MS", "ME", "QS", "QE", "YS", "YE", "B", "BMS", "BME", "BQS", "BQE", "BYS", "BYE", "SMS", "SME", "WOM-2MON", "LWOM-FRI", "-2h", "-1D", "-1ME"]

@pytest.mark.parametrize("freq", FREQUENCIES)
@pytest.mark.parametrize("side", ["start", "end"])
def test_public_native_ranges_match_fixed_pandas3(freq, side):
    args = {side: "2024-01-10 09:15:12", "periods": 5, "freq": freq}
    got = Pddt.date_range(**args)
    expected = fixed_date_range(**args)
    assert got.unit == expected.unit
    assert got.asi8.tolist() == expected.asi8.tolist()
    assert isinstance(got, Pddt)

@pytest.mark.parametrize("inclusive", ["both", "left", "right", "neither"])
@pytest.mark.parametrize("count", [0, 1, 4])
def test_equal_integer_interpolation(inclusive, count):
    got = Pddt.date_range(0, end=5, periods=count, unit="ns", inclusive=inclusive)
    expected = fixed_date_range(0, end=5, periods=count, unit="ns", inclusive=inclusive)
    assert got.asi8.tolist() == expected.asi8.tolist()

@pytest.mark.parametrize("freq", ["D", "h", "24h", "ME"])
@pytest.mark.parametrize("side", ["start", "end"])
def test_elapsed_and_calendar_across_dst(freq, side):
    kwargs = {side: "2024-03-09 12:00", "periods": 5, "freq": freq, "tz": "America/New_York"}
    got, expected = Pddt.date_range(**kwargs), fixed_date_range(**kwargs)
    assert got.asi8.tolist() == expected.asi8.tolist()
    assert got.tz.key == "America/New_York"


def test_source_zone_instants_and_shared_text_configuration():
    src = datetime(2024, 1, 1, 10, tzinfo=ZoneInfo("Asia/Shanghai"))
    got = Pddt.date_range(src, periods=2, freq="h", tz="UTC")
    assert got.hour.tolist() == [2, 3]
    cfg = Configs()
    cfg.add_month("myjanuary", 1)
    got = Pddt.date_range("2 myjanuary 2024", periods=2, cfg=cfg)
    assert got.day.tolist() == [2, 3]


def test_wide_years_and_explicit_unit_are_native():
    got = Pddt.date_range("0000-01-01", periods=3, unit="us")
    assert got.year.tolist() == [0, 0, 0]
    assert got.day.tolist() == [1, 2, 3]
    with pytest.raises(ValueError, match="frequency"):
        Pddt.date_range("2024-01-01", periods=3, freq="500ns", unit="us")
    got = Pddt.date_range("2024-01-01 12:00:00.000000123", periods=2, normalize=True, unit="s")
    assert got.hour.tolist() == [0, 0]


@pytest.mark.parametrize("unit,tail", [("s", "5"), ("ms", "0005"), ("us", "0000005")])
@pytest.mark.parametrize("freq", ["s", "D", "-1s", "-1D"])
@pytest.mark.parametrize("inclusive", ["both", "left", "right", "neither"])
def test_explicit_unit_checks_end_even_when_it_is_not_generated(unit, tail, freq, inclusive):
    start = "2024-01-04" if freq.startswith("-") else "2024-01-01"
    with pytest.raises(ValueError, match="end.*unit"):
        Pddt.date_range(start, end="2024-01-03 00:00:00." + tail,
                        freq=freq, unit=unit, inclusive=inclusive)


@pytest.mark.parametrize("side", ["start", "end"])
@pytest.mark.parametrize("count", [0, 1])
@pytest.mark.parametrize("freq", ["s", "D", pd.offsets.BusinessHour()])
def test_short_and_empty_ranges_validate_the_supplied_endpoint(side, count, freq):
    with pytest.raises(ValueError, match=side + ".*unit"):
        Pddt.date_range(**{side: "2024-01-03 10:00:00.000001"},
                        periods=count, freq=freq, unit="s")


@pytest.mark.parametrize("freq", ["D", pd.offsets.BusinessHour()])
def test_normalize_intentionally_removes_endpoint_clock_precision(freq):
    got = Pddt.date_range("2024-01-01 00:00:00.000001",
        end="2024-01-03 12:00:00.000001", freq=freq, unit="s", normalize=True)
    dates = ([datetime(2024, 1, day) for day in (1, 2, 3)] if freq == "D" else
             [datetime(2024, 1, day, hour) for day in (1, 2) for hour in range(9, 17)])
    expected = [np.datetime64(value, "s").view("i8") for value in dates]
    assert got.unit == "s" and got.asi8.tolist() == expected


@pytest.mark.parametrize("tz", [None, "UTC", "Asia/Shanghai", "America/New_York"])
def test_endpoint_precision_is_checked_with_the_selected_timezone(tz):
    with pytest.raises(ValueError, match="end.*unit"):
        Pddt.date_range("2024-01-01", end="2024-01-03 00:00:00.000001",
                        freq="D", unit="s", tz=tz)


@pytest.mark.parametrize("freq", ["D", "h"])
def test_endpoint_unit_validation_uses_the_stored_instant_for_subsecond_offsets(freq):
    zone = timezone(timedelta(microseconds=1))
    start = datetime(2024, 1, 1, microsecond=1, tzinfo=zone)
    got = Pddt.date_range(start, periods=2, freq=freq, unit="s")
    step = 86400 if freq == "D" else 3600
    assert got.asi8.tolist() == [1704067200, 1704067200 + step]


@pytest.mark.parametrize("side", ["start", "end"])
def test_empty_range_does_not_hide_endpoint_storage_overflow(side):
    with pytest.raises(OverflowError, match=side + ".*unit"):
        Pddt.date_range(**{side: "2500-01-01"}, periods=0, freq="D", unit="ns")


def test_full_generated_mask_and_missing_endpoints():
    got = Pddt.date_range("2024-11-02 01:30", periods=3, tz="America/New_York", ambiguous=[False, True, False], inclusive="right")
    assert len(got) == 2
    assert got[0].utcoffset() == timedelta(hours=-4)
    with pytest.raises(ValueError, match="mask length"):
        Pddt.date_range("2024-01-01", periods=3, ambiguous=[True])
    with pytest.raises(ValueError, match="endpoint"):
        Pddt.date_range(pd.NaT, periods=2)
    with pytest.raises(ValueError, match="does not exist"):
        Pddt.date_range("2024-03-10 02:30", periods=2, freq="h", tz="America/New_York")
    got = Pddt.date_range("2024-03-10 02:30", periods=2, freq="h", tz="America/New_York", nonexistent="shift_forward")
    assert got.hour.tolist() == [3, 4]


def test_subclass_constructs_once_after_generation():
    calls = []
    class Child(Pddt):
        def __new__(cls, *args, **kwargs):
            calls.append("new")
            return super().__new__(cls, *args, **kwargs)
        def __init__(self, *args, **kwargs):
            calls.append("init")
    got = Child.date_range("2024-01-01", periods=3)
    assert isinstance(got, Child)
    assert calls == ["new", "init"]

@pytest.mark.parametrize("offset", [pd.offsets.BusinessHour(), pd.offsets.CustomBusinessHour(start="10:00", end="17:00", holidays=["2024-01-15"]), pd.offsets.DateOffset(months=1, days=2), pd.offsets.FY5253(weekday=5, startingMonth=12, variation="last")])
def test_explicit_mature_rules_receive_decoded_endpoints(offset):
    kwargs = dict(start="2024-01-10 09:00", periods=4, freq=offset)
    got, expected = Pddt.date_range(**kwargs), fixed_date_range(**kwargs)
    assert got.unit == expected.unit
    assert got.asi8.tolist() == expected.asi8.tolist()


def test_delegated_rule_uses_our_text_and_regional_localization():
    cfg = Configs()
    cfg.add_month("mymarch", 3)
    result = Pddt.date_range("8 mymarch 2024 02:30", periods=4,
        freq=pd.offsets.DateOffset(days=1), cfg=cfg, tz="America/New_York", nonexistent="shift_forward")
    assert result.hour.tolist() == [2, 2, 3, 2]
    assert result.day.tolist() == [8, 9, 10, 11]
    assert result.tz.key == "America/New_York"


@pytest.mark.parametrize("freq", [pd.offsets.BusinessDay(offset=timedelta(hours=2)), pd.offsets.CustomBusinessMonthEnd(weekmask="Mon Wed Fri", holidays=["2024-01-31"], offset=timedelta(hours=2)), pd.offsets.Week(weekday=None), pd.offsets.MonthEnd(normalize=True)])
@pytest.mark.parametrize("side", ["start", "end"])
def test_complete_static_offset_parameters(freq, side):
    kwargs = {side: "2024-01-10 09:15", "periods": 4, "freq": freq}
    got, expected = Pddt.date_range(**kwargs), fixed_date_range(**kwargs)
    assert got.asi8.tolist() == expected.asi8.tolist()


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_native_source_unit_retained(unit):
    got = Pddt.date_range(np.datetime64("2024-01-01", unit), periods=2, freq="D")
    assert got.unit == unit


def test_named_range_capacity_and_type_errors():
    for periods in (True, 3.0):
        with pytest.raises(TypeError):
            Pddt.date_range("2024-01-01", periods=periods)
    with pytest.raises(OverflowError):
        Pddt.date_range("2262-04-11", periods=3, unit="ns")
    with pytest.raises(ValueError):
        Pddt.date_range("2024-01-01", periods=3, freq="0D")

@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("first,last,expected", [(0,5,[0,1,3,5]),(5,0,[5,3,1,0]),(-5,0,[-5,-4,-2,0])])
def test_interpolation_uses_selected_integer_lattice(unit, first, last, expected):
    result = Pddt.date_range(first, end=last, periods=4, unit=unit)
    assert result.asi8.tolist() == expected

@pytest.mark.parametrize("freq", ["D", "h", "ME", "W-MON"])
@pytest.mark.parametrize("tz", [None,"UTC","America/New_York"])
def test_only_valid_frequency_metadata_is_retained(freq, tz):
    got = Pddt.date_range("2024-01-02 12:00", periods=4, freq=freq, tz=tz)
    expected = fixed_date_range("2024-01-02 12:00", periods=4, freq=freq, tz=tz)
    assert got.freq == expected.freq


def test_shifted_gap_does_not_attach_false_calendar_frequency():
    got = Pddt.date_range("2024-03-09 02:30", periods=3, tz="America/New_York", nonexistent="shift_forward")
    assert got.hour.tolist() == [2,3,2]
    assert got.freq is None

@pytest.mark.parametrize("freq,unit", [("1000ns","ns"),("1000ms","ms"),("1000000us","us"),(pd.offsets.Nano(1000),"ns")])
def test_declared_frequency_resolution_survives_exact_coarse_divisibility(freq, unit):
    from datetime import date
    got = Pddt.date_range(date(2024,1,1), periods=2, freq=freq)
    assert got.unit == unit

@pytest.mark.parametrize("offset,unit", [(pd.DateOffset(microseconds=1),"us"),(pd.DateOffset(nanoseconds=1),"ns")])
def test_mature_extra_semantics_choose_necessary_initial_unit(offset, unit):
    from datetime import date
    got = Pddt.date_range(date(2024,1,1),periods=3,freq=offset)
    assert got.unit == unit
    assert np.diff(got.asi8).tolist() == [1,1]


@pytest.mark.parametrize("offset", [pd.offsets.BusinessHour(),pd.DateOffset(months=1,days=2)])
def test_mature_builtin_frequency_metadata_is_validated(offset):
    got = Pddt.date_range("2024-01-01", periods=3, freq=offset)
    assert got.freq == offset


@pytest.mark.parametrize("rule,unit",[(pd.DateOffset(months=1),"s"),(pd.DateOffset(microseconds=1),"us"),(pd.DateOffset(nanoseconds=1000),"ns"),(pd.DateOffset(seconds=.5),"us"),(pd.offsets.BusinessHour(),"us"),(pd.offsets.FY5253(),"s")])
def test_mature_initial_precision_is_uniform_without_truncating_generation(rule,unit):
    from datetime import date
    x=Pddt.date_range(date(2024,1,1),periods=3,freq=rule)
    assert x.unit==unit
    if type(rule) is pd.DateOffset and rule.kwds=={"seconds":.5}:
        assert np.diff(x.asi8).tolist()==[500000,500000]


def test_explicit_mature_unit_does_not_truncate_before_final_validation():
    from datetime import date
    for rule in [pd.DateOffset(microseconds=1),pd.DateOffset(nanoseconds=1)]:
        with pytest.raises(ValueError):Pddt.date_range(date(2024,1,1),periods=3,freq=rule,unit="s")
