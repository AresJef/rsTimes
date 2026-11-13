"""Native range families and strict endpoint/unit semantics, independent answers."""
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
import numpy as np
import polars as pl
import pytest
from rstimes import Pldt


def ticks(value):return value.to_physical().to_list()
def tick(text,unit="us"):return int(np.datetime64(text,unit).astype(np.int64))


@pytest.mark.parametrize("freq,start,expected",[
 ("D","2024-01-01",["2024-01-01","2024-01-02","2024-01-03"]),
 ("W","2024-01-01",["2024-01-07","2024-01-14","2024-01-21"]),
 ("W-MON","2024-01-01",["2024-01-01","2024-01-08","2024-01-15"]),
 ("MS","2024-01-15",["2024-02-01","2024-03-01","2024-04-01"]),
 ("ME","2024-01-15",["2024-01-31","2024-02-29","2024-03-31"]),
 ("QS","2024-01-15",["2024-04-01","2024-07-01","2024-10-01"]),
 ("QE","2024-01-15",["2024-03-31","2024-06-30","2024-09-30"]),
 ("QS-FEB","2024-01-15",["2024-02-01","2024-05-01","2024-08-01"]),
 ("YS","2024-01-15",["2025-01-01","2026-01-01","2027-01-01"]),
 ("YE-JUN","2024-01-15",["2024-06-30","2025-06-30","2026-06-30"]),
 ("B","2024-01-05",["2024-01-05","2024-01-08","2024-01-09"]),
 ("C","2024-01-05",["2024-01-05","2024-01-08","2024-01-09"]),
 ("BMS","2024-06-15",["2024-07-01","2024-08-01","2024-09-02"]),
 ("CBME","2024-05-15",["2024-05-31","2024-06-28","2024-07-31"]),
 ("BQS","2024-01-15",["2024-04-01","2024-07-01","2024-10-01"]),
 ("BQE","2024-01-15",["2024-03-29","2024-06-28","2024-09-30"]),
 ("BYS","2024-01-15",["2025-01-01","2026-01-01","2027-01-01"]),
 ("BYE","2024-01-15",["2024-12-31","2025-12-31","2026-12-31"]),
 ("SMS","2024-01-15",["2024-01-15","2024-02-01","2024-02-15"]),
 ("SME","2024-01-15",["2024-01-15","2024-01-31","2024-02-15"]),
 ("WOM-2MON","2024-01-01",["2024-01-08","2024-02-12","2024-03-11"]),
 ("LWOM-FRI","2024-01-01",["2024-01-26","2024-02-23","2024-03-29"]),
 ("-ME","2024-03-31",["2024-03-31","2024-02-29","2024-01-31"]),
])
def test_native_frequency_calendar_families(freq,start,expected):
    result=Pldt.date_range(start,periods=3,freq=freq)
    assert result.dtype==pl.Datetime("us") and ticks(result)==[tick(value) for value in expected]


@pytest.mark.parametrize("freq",["500ns","0.5us"])
def test_exact_decimal_frequency_preserves_ns(freq):
    result=Pldt.date_range(0,periods=3,freq=freq)
    assert result.dtype==pl.Datetime("ns") and ticks(result)==[0,500,1000]


def test_combined_fixed_duration_and_reverse_unit_ticks():
    assert ticks(Pldt.date_range("2024-01-01",periods=3,freq="1h30min"))==[tick("2024-01-01T00:00"),tick("2024-01-01T01:30"),tick("2024-01-01T03:00")]
    assert ticks(Pldt.date_range(0,periods=3,freq="-15min",unit="ms"))==[0,-900000,-1800000]
    assert ticks(Pldt.date_range(-(1<<63),periods=1,freq="ms",unit="ms"))==[-(1<<63)]


def test_integer_interpolation_order_empty_and_singleton():
    assert ticks(Pldt.date_range(0,end=5,periods=4,unit="ns"))==[0,1,3,5]
    assert ticks(Pldt.date_range(5,end=0,periods=4,unit="ns"))==[5,3,1,0]
    assert ticks(Pldt.date_range(5,end=0,periods=1,unit="ns"))==[5]
    assert Pldt.date_range("2024-01-01",periods=0).len()==0
    assert ticks(Pldt.date_range("2024-01-01",end="2024-01-03",freq="D",inclusive="neither"))==[tick("2024-01-02")]


def test_calendar_days_and_actual_24_hours_differ_across_dst():
    kwargs={"periods":3,"tz":"America/New_York"}
    calendar=Pldt.date_range("2024-03-09 12:00",freq="D",**kwargs)
    elapsed=Pldt.date_range("2024-03-09 12:00",freq="24h",**kwargs)
    assert ticks(calendar)==[tick("2024-03-09T17:00"),tick("2024-03-10T16:00"),tick("2024-03-11T16:00")]
    assert ticks(elapsed)==[tick("2024-03-09T17:00"),tick("2024-03-10T17:00"),tick("2024-03-11T17:00")]
    assert ticks(Pldt.date_range("2024-03-09 12:00",freq=timedelta(days=1),**kwargs))==ticks(elapsed)


def test_calendar_mask_uses_full_sequence_before_inclusive_trim():
    result=Pldt.date_range("2024-11-02 01:30",periods=3,freq="D",tz="America/New_York",ambiguous=[False,False,False],inclusive="right")
    assert ticks(result)==[tick("2024-11-03T06:30"),tick("2024-11-04T06:30")]
    with pytest.raises(ValueError,match="length"):
        Pldt.date_range("2024-11-02 01:30",periods=3,freq="D",tz="America/New_York",ambiguous=[False,False],inclusive="right")
    source=datetime(2024,11,3,1,30,tzinfo=ZoneInfo("America/New_York"),fold=1)
    assert ticks(Pldt.date_range(source,periods=2,freq="D"))==[tick("2024-11-03T06:30"),tick("2024-11-04T06:30")]


def test_all_endpoints_validated_even_when_not_output_and_normalize_is_intentional():
    with pytest.raises(ValueError,match="precision|unit|preserved"):
        Pldt.date_range("2024-01-01 00:00:00.000000001",periods=0,unit="us")
    with pytest.raises(OverflowError):
        Pldt.date_range("2500-01-01",periods=0,unit="ns")
    result=Pldt.date_range("2024-01-01 00:00:00.000000001",periods=1,normalize=True,unit="us")
    assert ticks(result)==[tick("2024-01-01")]
    with pytest.raises(ValueError):Pldt.date_range("NaT",periods=0)
    with pytest.raises(TypeError):Pldt.date_range("2024-01-01",periods=True)
    with pytest.raises(TypeError):Pldt.date_range("2024-01-01",periods=0,strict=1)
    with pytest.raises(TypeError):Pldt.date_range(["2024-01-01"],periods=1)


@pytest.mark.parametrize("freq",["H","M","m","T","0D","0ns","1h2","WOM-5MON","QS-XYZ"])
def test_removed_or_invalid_frequency_does_not_fallback(freq):
    with pytest.raises(ValueError):Pldt.date_range("2024-01-01",periods=2,freq=freq)


def test_range_shared_default_and_source_unit_capacity():
    assert ticks(Pldt.date_range("12:30",end="13:30",periods=2,default="2024-01-02"))==[tick("2024-01-02T12:30"),tick("2024-01-02T13:30")]
    assert ticks(Pldt.date_range(0,end=5,periods=4,unit="ns",default="Jan"))==[0,1,3,5]
    result=Pldt.date_range(np.datetime64("12000-01-01","ms"),periods=2,freq="D")
    assert result.dtype==pl.Datetime("ms") and ticks(result)==[tick("12000-01-01","ms"),tick("12000-01-02","ms")]


def test_special_range_uses_optional_mature_executor_only():
    try:import pandas as pd
    except ImportError:
        with pytest.raises(ImportError,match="pandas"):Pldt.date_range("2024-01-01 09:00",periods=3,freq="bh")
        return
    result=Pldt.date_range("2024-01-01 09:00",periods=3,freq="bh")
    assert ticks(result)==[tick("2024-01-01T09:00"),tick("2024-01-01T10:00"),tick("2024-01-01T11:00")]
    rule=pd.offsets.CustomBusinessDay(weekmask="Mon Tue Wed Thu",holidays=["2024-01-02"])
    result=Pldt.date_range("2024-01-01",periods=3,freq=rule)
    assert ticks(result)==[tick("2024-01-01"),tick("2024-01-03"),tick("2024-01-04")]


def _frozen_simple_cases():
    from pathlib import Path
    import json
    data=json.loads((Path(__file__).resolve().parents[1]/"pddt/data/fixed-pandas3-ranges.json").read_text())["cases"]
    for key,expected in data.items():
        args,kwargs=json.loads(key)
        if args or kwargs.get("unit")=="s" or not isinstance(kwargs.get("freq"),(str,type(None))):
            continue
        if all(isinstance(value,(str,int,float,bool,type(None))) for value in kwargs.values()):
            yield kwargs,expected


@pytest.mark.parametrize("kwargs,expected",list(_frozen_simple_cases()))
def test_existing_frozen_pandas3_expected_ranges_are_also_protected_without_pandas(kwargs,expected):
    result=Pldt.date_range(**kwargs)
    expected_unit="ms" if expected["unit"]=="s" else expected["unit"]
    expected_ticks=[value*1000 for value in expected["ticks"]] if expected["unit"]=="s" else expected["ticks"]
    assert result.dtype.time_unit==expected_unit
    assert ticks(result)==expected_ticks


def test_existing_pandas_install_does_not_change_native_engine_and_external_errors_survive(monkeypatch):
    pd=pytest.importorskip("pandas")
    error=RuntimeError("original mature range failure")
    def broken(*args,**kwargs):raise error
    monkeypatch.setattr(pd,"date_range",broken)
    assert ticks(Pldt.date_range("2024-01-01",periods=2,freq="D"))==[tick("2024-01-01"),tick("2024-01-02")]
    assert ticks(Pldt.date_range("2024-01-01",periods=2,freq=pd.offsets.MonthEnd()))==[tick("2024-01-31"),tick("2024-02-29")]
    with pytest.raises(RuntimeError) as captured:
        Pldt.date_range("2024-01-01 09:00",periods=3,freq="bh")
    assert captured.value is error
    class GenuineChild(pd.offsets.MonthEnd):pass
    with pytest.raises(RuntimeError) as captured:
        Pldt.date_range("2024-01-01",periods=2,freq=GenuineChild())
    assert captured.value is error


def test_mature_generation_keeps_full_precision_and_uses_shared_text_and_dst_rules():
    pd=pytest.importorskip("pandas")
    from rstimes import Configs
    for rule,unit,step in [(pd.DateOffset(microseconds=1),"us",1),(pd.DateOffset(nanoseconds=1),"ns",1),(pd.DateOffset(seconds=.5),"us",500000)]:
        result=Pldt.date_range(date(2024,1,1),periods=3,freq=rule)
        assert result.dtype.time_unit==unit
        assert ticks(result)==[tick("2024-01-01",unit)+step*index for index in range(3)]
    with pytest.raises(ValueError,match="precision|loss"):
        Pldt.date_range(date(2024,1,1),periods=3,freq=pd.DateOffset(nanoseconds=1),unit="us")
    cfg=Configs();cfg.add_month("mymarch",3)
    result=Pldt.date_range("8 mymarch 2024 02:30",periods=4,freq=pd.DateOffset(days=1),cfg=cfg,tz="America/New_York",nonexistent="shift_forward")
    assert ticks(result)==[tick("2024-03-08T07:30"),tick("2024-03-09T07:30"),tick("2024-03-10T07:00"),tick("2024-03-11T06:30")]


@pytest.mark.parametrize("value,zone",[((1<<63)-808,"Etc/GMT-14"),(-(1<<63)+808,"Etc/GMT+12")])
def test_mature_exact_local_carrier_does_not_artificially_exceed_final_ns_capacity(value,zone):
    pd=pytest.importorskip("pandas")
    source=pd.Timestamp(np.datetime64(value,"ns"),tz="UTC")
    result=Pldt.date_range(source,periods=1,freq=pd.DateOffset(minutes=1),tz=zone,unit="ns")
    assert result.dtype==pl.Datetime("ns",zone) and ticks(result)==[value]


def test_fractional_frequency_actual_quantum_joins_source_precision():
    value=tick("2024-01-01","ns")
    result=Pldt.date_range("2024-01-01",periods=3,freq="0.5us")
    assert result.dtype==pl.Datetime("ns") and ticks(result)==[value,value+500,value+1000]


def test_static_calendar_offset_quantum_from_date_source():
    pd=pytest.importorskip("pandas")
    result=Pldt.date_range(date(2024,1,1),periods=3,freq=pd.offsets.BusinessDay(offset=timedelta(microseconds=1)))
    expected=pd.date_range(pd.Timestamp("2024-01-01"),periods=3,freq=pd.offsets.BusinessDay(offset=timedelta(microseconds=1)),unit="us")
    assert result.dtype==pl.Datetime("us") and ticks(result)==expected.asi8.tolist()
