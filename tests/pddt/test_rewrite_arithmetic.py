"""Real elapsed durations, calendar Delta values and full precision differences."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt,Delta


@pytest.mark.parametrize("duration",[timedelta(days=1),pd.Timedelta(days=1),np.timedelta64(24,"h")])
def test_fixed_elapsed_and_calendar_days_differ_at_dst(duration):
    x=Pddt(["2024-03-09 12:00",None],tz="America/New_York",name="when")
    result=x+duration
    assert isinstance(result,Pddt) and result.hour.tolist()[0]==13
    assert result.name=="when" and pd.isna(result[1])
    assert (duration+x).asi8.tolist()==result.asi8.tolist()
    assert (x-duration)[0].hour==12
    assert x.add(days=1)[0].hour==12
    assert (x+Delta(days=1))[0].hour==12
    assert (Delta(days=1)+x).asi8.tolist()==(x+Delta(days=1)).asi8.tolist()


def test_calendar_delta_directions_absolute_values_and_nanos():
    x=Pddt(["2024-01-31 12:34:56.123456789","2024-02-29 12:34:56.123456789"],name="t")
    assert (x+[Delta(months=1),Delta(months=2)]).month.tolist()==[2,4]
    assert (x-Delta(months=1)).month.tolist()==[12,1]
    assert (x+Delta(microsecond=1))[0].isoformat().endswith(".000001")
    assert (x+Delta(microseconds=1))[0].isoformat().endswith(".123457789")
    with pytest.raises(TypeError,match="missing"):
        x+[Delta(),None]
    with pytest.raises(ValueError):x+[Delta()]


def test_current_unit_precision_and_capacity_are_protected():
    x=Pddt(["2024-01-01"],unit="s")
    with pytest.raises(ValueError):x+np.timedelta64(1,"ns")
    with pytest.raises(ValueError):x+Delta(microseconds=1)
    assert (x+np.timedelta64(1000,"ms")).unit=="s"
    y=Pddt([np.datetime64(2**63-1,"ns")])
    with pytest.raises(OverflowError):y+np.timedelta64(1,"ns")


@pytest.mark.parametrize("unit",["s","ms","us","ns"])
def test_date_difference_preserves_source_resolution(unit):
    left=Pddt(np.array([3,5,-2**63],dtype="int64").view(f"datetime64[{unit}]"),name="when")
    right=pd.DatetimeIndex(np.array([1,2,-2**63],dtype="int64").view(f"datetime64[{unit}]"))
    got=left-right
    assert isinstance(got,pd.TimedeltaIndex) and got.unit==unit
    assert got.asi8.tolist()==[2,3,-2**63] and got.name=="when"


def test_different_aware_zones_and_finer_right_values():
    x=Pddt(["2024-01-01 12:00"],tz="Asia/Shanghai")
    other=datetime(2024,1,1,3,tzinfo=timezone.utc)
    assert (x-other)[0]==pd.Timedelta(hours=1)
    with pytest.raises(TypeError):x-datetime(2024,1,1)
    left=Pddt([np.datetime64(1,"us")])
    got=left-np.datetime64(1,"ns")
    assert got.unit=="ns" and got.asi8.tolist()==[999]


def test_numpy_temporal_columns_are_real_native_buffers():
    x=Pddt(np.array([2,4],dtype="i8").view("datetime64[us]"))
    durations=np.arange(4,dtype="i8").view("timedelta64[us]")[::2]
    assert (x+durations).asi8.tolist()==[2,6]
    assert (x-np.array([1,2],dtype="i8").view("datetime64[us]")).asi8.tolist()==[1,2]
    with pytest.raises(TypeError):x+np.timedelta64(1,"M")


def test_delta_subclass_reflected_arithmetic_is_not_silently_bypassed():
    class Child(Delta):
        def __radd__(self,other):return "custom-right"
    x=Pddt(["2024-01-01"])
    assert x+Child(days=1)=="custom-right"


def test_one_result_construction_for_true_date_subclasses():
    calls=[]
    class Child(Pddt):
        def __new__(cls,*args,**kwargs):calls.append("new");return super().__new__(cls,*args,**kwargs)
        def __init__(self,*args,**kwargs):calls.append("init")
    x=Child(["2024-01-01"]);calls.clear()
    got=x+timedelta(days=1)
    assert isinstance(got,Child) and calls==["new","init"]
    calls.clear();assert x+Delta() is x;assert calls==[]


def test_timedelta_subclass_reflection_and_missing_delta_columns():
    class Child(timedelta):
        def __radd__(self,other):return "span-right"
        def __rsub__(self,other):return "span-sub"
    x=Pddt(["2024-01-01"])
    assert x+Child(days=1)=="span-right"
    assert x-Child(days=1)=="span-sub"
    with pytest.raises(TypeError):x+[None]
    assert pd.isna((x+np.timedelta64("NaT","ns"))[0])


def test_duration_columns_keep_their_actual_nanoseconds():
    x=Pddt([np.datetime64(0,"ns"),np.datetime64(1,"ns")])
    duration=pd.TimedeltaIndex(np.array([1,2],dtype="i8").view("timedelta64[ns]"))
    assert (x+duration).asi8.tolist()==[1,3]
    pl=pytest.importorskip("polars")
    assert (x+pl.Series([1,2],dtype=pl.Duration("ns"))).asi8.tolist()==[1,3]


def test_delta_calendar_reuses_wide_native_fields_without_pydt_capacity():
    x=Pddt(["9999-01-31","0000-02-29"],unit="us")
    got=x+[Delta(years=1),Delta(months=1)]
    assert got.year.tolist()==[10000,0]
    assert got.month.tolist()==[1,3]
    assert got.day.tolist()==[31,29]


def test_date_difference_negative_nat_reserved_tick_is_an_overflow():
    left=Pddt(np.array([-2**63+1],dtype="i8").view("datetime64[s]"))
    with pytest.raises(OverflowError):left-np.datetime64(1,"s")


def test_date_difference_supports_date_scalars_and_positional_columns():
    x=Pddt(["2024-01-03","2024-01-05"],unit="s")
    assert (x-date(2024,1,1)).asi8.tolist()==[2*86400,4*86400]
    assert (x-[date(2024,1,1),None]).isna().tolist()==[False,True]
    with pytest.raises(ValueError):x-[date(2024,1,1)]
    with pytest.raises(ValueError):x-[date(2024,1,1)]*3


def test_arithmetic_text_scalars_are_never_split_into_character_targets():
    x=Pddt(["2024-01-01"])
    for value in ["2024-01-01", b"123", bytearray(b"123")]:
        with pytest.raises(TypeError):x+value
        with pytest.raises(TypeError):x-value


def test_unchanged_and_changed_rows_are_detected_in_the_calculation_loop():
    x=Pddt(["2024-01-01",None])
    assert x+timedelta(0) is x
    assert x+Delta() is x
    assert x.to_date(day=[1,None]) is x
    assert (x+timedelta(days=1))[0].day==2


def test_empty_and_missing_sources_do_not_relax_date_domain_compatibility():
    for x in [Pddt([]),Pddt([None])]:
        with pytest.raises(TypeError,match="aware|naive"):
            x-datetime(2024,1,1,tzinfo=timezone.utc)
    with pytest.raises(TypeError,match="aware|naive"):
        Pddt([],tz="UTC")-pd.DatetimeIndex([])


def test_missing_numpy_duration_retains_the_duration_role_in_subtraction():
    x=Pddt(["2024-01-01"])
    result=x-np.timedelta64("NaT","ns")
    assert isinstance(result,Pddt) and result.isna().tolist()==[True]
    with pytest.raises(TypeError):x+np.datetime64("NaT","ns")
