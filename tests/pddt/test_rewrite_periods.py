"""Boundary producers and predicates use the same native period definition."""
from datetime import timedelta,timezone
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt,Pydt


@pytest.mark.parametrize("unit",["Y","Q","M","W","January","February"])
@pytest.mark.parametrize("which",["first","last"])
def test_calendar_day_selection_matches_scalar_and_preserves_clock(unit,which):
    x=Pddt(["2024-05-07 12:34:56.123456789",None])
    got=getattr(x,"to_"+which+"_of")(unit)
    scalar=getattr(Pydt(2024,5,7,12,34,56,123456),"to_"+which+"_of")(unit)
    assert got[0].to_pydatetime(warn=False)==scalar
    assert got[0].nanosecond==789 and pd.isna(got[1])
    assert getattr(got,"is_"+which+"_of")(unit).tolist()==[True,False]


@pytest.mark.parametrize("unit",["Y","Q","M","W","D","h","m","min","s","ms","us","ns","Friday","January"])
@pytest.mark.parametrize("edge",["start","end"])
def test_boundary_query_agrees_with_transform_at_ns_precision(unit,edge):
    x=Pddt(["2024-05-07 12:34:56.123456789",None],name="time")
    got=getattr(x,"to_"+edge+"_of")(unit)
    assert got.unit=="ns" and got.name=="time"
    assert getattr(got,"is_"+edge+"_of")(unit).tolist()==[True,False]


@pytest.mark.parametrize("storage",["s","ms","us","ns"])
@pytest.mark.parametrize("period",["ms","us","ns"])
def test_finer_periods_do_not_invent_precision_or_overflow(storage,period):
    x=Pddt(["2024-01-01"],unit=storage)
    a=x.to_start_of(period);b=x.to_end_of(period)
    assert a.is_start_of(period).tolist()==[True]
    assert b.is_end_of(period).tolist()==[True]
    assert a.unit==storage and b.unit==storage


@pytest.mark.parametrize("unit",["Y","Q","M","W","D"])
def test_regional_day_and_period_boundaries_stay_inside_the_period(unit):
    x=Pddt(["2024-03-10 12:34"],tz="America/New_York")
    first=x.to_start_of(unit);last=x.to_end_of(unit)
    assert first.is_start_of(unit).tolist()==[True]
    assert last.is_end_of(unit).tolist()==[True]
    assert last.asi8[0]>=first.asi8[0]


def test_missing_midnight_normalization_and_missing_end_date_query():
    x=Pddt(["2018-11-04 12:00"],tz="America/Sao_Paulo")
    got=x.normalize()
    assert got.day.tolist()==[4] and got.hour.tolist()==[1]
    assert got.is_start_of("D").tolist()==[True]
    x=Pddt(["1844-12-15 12:00"],tz="Asia/Manila",unit="us")
    end=x.to_end_of("Y")
    assert end.day.tolist()==[30]
    assert end.is_end_of("Y").tolist()==[True]


def test_naive_and_fixed_offset_shortcuts_and_fractional_grid():
    zone=timezone(timedelta(microseconds=500))
    x=Pddt([0],tz=zone,unit="ms")
    got=x.to_start_of("D")
    assert got.asi8.tolist()==[0]
    assert got.is_start_of("D").tolist()==[True]
    end=x.to_end_of("D")
    assert end.asi8.tolist()==[86_399_999]
    assert end.is_end_of("D").tolist()==[True]


def test_boundary_query_near_ns_capacity_does_not_construct_outside_dates():
    x=Pddt(np.array([-2**63+1,2**63-1],dtype="i8").view("datetime64[ns]"))
    assert x.is_start_of("Y").tolist()==[False,False]
    assert x.is_end_of("Y").tolist()==[False,False]
    with pytest.raises(OverflowError):x.to_start_of("Y")


@pytest.mark.parametrize("method",["to_first_of","to_last_of","to_start_of","to_end_of","is_first_of","is_last_of","is_start_of","is_end_of"])
def test_boundary_argument_errors_even_on_empty_data(method):
    x=Pddt([])
    for value in [None,1,b"D",["D"]]:
        with pytest.raises(TypeError):getattr(x,method)(value)
    for value in ["","unknown"]:
        with pytest.raises(ValueError):getattr(x,method)(value)


@pytest.mark.parametrize("precision",range(10))
def test_fraction_trimming_is_local_and_retains_nanos_when_requested(precision):
    x=Pddt(["1969-12-31 23:59:59.123456789",None])
    got=x.fsp(precision)
    value=123456789//(10**(9-min(precision,9)))*(10**(9-min(precision,9)))
    assert got[0].microsecond*1000+got[0].nanosecond==value
    assert pd.isna(got[1]) and got.unit==x.unit
    if precision==9:assert got is x


@pytest.mark.parametrize("freq",["D","24h","3h","15min","s","ms","us","500ns"])
@pytest.mark.parametrize("method",["round","ceil","floor"])
def test_fixed_frequency_rounding_matches_mature_naive_math(freq,method):
    data=["1969-12-31 23:59:59.123456789","2024-01-02 12:34:56.123456789",None]
    x=Pddt(data)
    got=getattr(x,method)(freq)
    expected=getattr(pd.DatetimeIndex(data),method)(freq)
    assert got.asi8.tolist()==expected.as_unit("ns").asi8.tolist()
    assert got.unit=="ns"


@pytest.mark.parametrize("fold",[False,True])
@pytest.mark.parametrize("method",["round","ceil","floor"])
def test_regional_rounding_preserves_direction_and_scalar_hour_results(fold,method):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    source=datetime(2024,11,3,1,30,tzinfo=ZoneInfo("America/New_York"),fold=fold)
    x=Pddt([source])
    got=getattr(x,method)("h")
    scalar=getattr(Pydt.fromdatetime(source),method)("h")
    assert got[0].to_pydatetime()==scalar
    if method=="ceil":assert got.asi8[0]>=x.asi8[0]
    if method=="floor":assert got.asi8[0]<=x.asi8[0]


def test_gap_rounding_uses_valid_grid_boundaries_instead_of_preserving_gap_clock():
    x=Pddt(["2024-03-10 01:45"],tz="America/New_York")
    assert x.ceil("h")[0].hour==3
    assert x.round("h")[0].hour==3
    x=Pddt(["2024-03-10 01:30"],tz="America/New_York")
    assert x.ceil("2h")[0].hour==4
    for method in ["round","ceil","floor"]:
        assert getattr(Pddt([],unit="s"),method)("us").unit=="s"
        with pytest.raises(ValueError):getattr(x,method)("ME")
        with pytest.raises(ValueError):getattr(x,method)("0s")


@pytest.mark.parametrize("unit",["Y","Q","M","W","D","h","m","min","s","ms","us","ns","Monday","Friday","January","April"])
def test_snap_matches_scalar_at_common_precision(unit):
    x=Pddt(["2024-05-07 12:34:56.123456"],unit="us")
    scalar=Pydt(2024,5,7,12,34,56,123456).snap(unit)
    assert x.snap(unit)[0].to_pydatetime()==scalar


def test_snap_uses_nanoseconds_and_does_not_round_ties_like_round():
    x=Pddt(["1970-01-01 00:00:00.000000500","1970-01-01 00:00:00.000000501"])
    assert x.snap("us").asi8.tolist()==[1000,1000]
    assert x.round("us").asi8.tolist()==[0,1000]
    assert x.snap("ns") is x
    for value in [None,1,b"D",["D"]]:
        with pytest.raises(TypeError):x.snap(value)
    for value in ["","15min","year","Year"," D "]:
        with pytest.raises(ValueError):x.snap(value)


def test_snap_considers_both_repeated_starts_and_skips_entire_missing_days():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    x=Pddt([datetime(2024,11,3,1,45,tzinfo=ZoneInfo("America/New_York"),fold=0)])
    got=x.snap("h")
    assert got[0].hour==1 and got[0].fold==1
    x=Pddt(["2011-12-29 12:00"],tz="Pacific/Apia")
    assert x.snap("D")[0].day==31
    x=Pddt(["2024-10-06 02:45"],tz="Australia/Lord_Howe")
    assert x.snap("h")[0].hour==3


def test_snap_losing_far_boundary_does_not_cause_false_ns_overflow():
    x=Pddt(np.array([-2**63+1,2**63-1],dtype="i8").view("datetime64[ns]"))
    got=x.snap("Y")
    assert got.year.tolist()==[1678,2262]


def test_snap_all_554_approved_names_have_independent_calendar_expectations():
    from pathlib import Path
    from datetime import datetime,timedelta
    import re
    text=(Path(__file__).resolve().parents[1]/'data/snap_names.md').read_text().split('## 附录A',1)[1]
    source=Pddt(["2024-06-15 12:00"],unit="us")
    reference=datetime(2024,6,15,12)
    weekdays={'星期一':0,'星期二':1,'星期三':2,'星期四':3,'星期五':4,'星期六':5,'星期日':6}
    counted=0
    for row in text.splitlines():
        if not row.startswith('|'):continue
        cols=row.strip('|').split('|',1)
        if len(cols)!=2:continue
        heading=cols[0];names=re.findall(r'`([^`]+)`',cols[1])
        for name in names:
            if heading in weekdays:
                options=[reference.replace(hour=0)+timedelta(days=weekdays[heading]-reference.weekday()+7*n) for n in [-1,0,1]]
            elif re.fullmatch(r'\d+月',heading):
                options=[datetime(year,int(heading[:-1]),1) for year in [2023,2024,2025]]
            else:continue
            expected=min(options,key=lambda v:(abs(v-reference),-v.toordinal()))
            assert source.snap(name)[0].to_pydatetime()==expected,name
            counted+=1
    assert counted==554
