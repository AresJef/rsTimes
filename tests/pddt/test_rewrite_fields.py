"""Fields, calendar increments and scalar/row parameter contracts."""
from collections import deque
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt, Pydt


def test_strict_replace_and_convenient_month_end_are_distinct():
    x=Pddt(["2024-01-31 12:34:56.123456789",None])
    with pytest.raises(ValueError,match="day"):
        x.pddt.replace(month=2)
    got=x.to_date(month=2)
    assert got[0].isoformat()=="2024-02-29T12:34:56.123456789"
    assert pd.isna(got[1])
    assert x.month.tolist()[0]==1
    assert x.pddt.replace() is x
    assert x.to_datetime() is x


def test_subsecond_replacement_order_and_none_fields():
    x=Pddt(["2024-01-02 12:34:56.123456789","2024-01-03 12:34:56.123456789"])
    assert x.pddt.replace(microsecond=1)[0].isoformat().endswith(".000001")
    assert x.pddt.replace(nanosecond=2)[0].isoformat().endswith(".123456002")
    assert x.pddt.replace(microsecond=1,nanosecond=2)[0].isoformat().endswith(".000001002")
    assert x.to_date(day=[None,5]).day.tolist()==[2,5]
    with pytest.raises(TypeError):x.to_date(day=[pd.NA,5])
    with pytest.raises(TypeError):x.to_date(day=[float('nan'),5])


@pytest.mark.parametrize("field,value", [("month",0),("month",13),("day",0),("day",32),("hour",-1),("hour",24),("minute",60),("second",60),("microsecond",1000000),("nanosecond",1000)])
@pytest.mark.parametrize("method",["replace","to_datetime"])
def test_field_ranges_even_with_missing_sources(field,value,method):
    x=Pddt([None])
    with pytest.raises(ValueError,match="range"):
        getattr(x.pddt if method == "replace" else x,method)(**{field:value})
    with pytest.raises(ValueError):
        getattr(x.pddt if method == "replace" else x,method)(**{field:[value]})


@pytest.mark.parametrize("method",["replace","to_datetime","to_date"])
def test_wide_and_zero_year_fields(method):
    x=Pddt(["2024-01-02"],unit="us")
    assert getattr(x.pddt if method == "replace" else x,method)(year=0).year.tolist()==[0]
    assert getattr(x.pddt if method == "replace" else x,method)(year=-1).year.tolist()==[-1]
    assert getattr(x.pddt if method == "replace" else x,method)(year=10000).year.tolist()==[10000]


def test_combine_relative_months_before_month_end_and_clock_precision():
    x=Pddt(["2024-02-29 12:34:56"],unit="s")
    assert x.add(years=1,months=-12) is x
    assert x.sub(years=1,months=-12) is x
    assert x.add(microseconds=1,nanoseconds=-1000) is x
    with pytest.raises(ValueError,match="unit|precision"):
        x.add(nanoseconds=1)
    assert x.add(months=1,days=-1)[0]==pd.Timestamp("2024-03-28 12:34:56")
    assert x.sub(months=1,days=-1)[0]==pd.Timestamp("2024-01-30 12:34:56")
    assert x.add(years=[0],quarters=[4],months=[-12]) is x


@pytest.mark.parametrize("name",["years","quarters","months","weeks","days","hours","minutes","seconds","milliseconds","microseconds","nanoseconds"])
@pytest.mark.parametrize("bad",[None,True,1.0])
def test_all_increment_roles_are_integer_only(name,bad):
    x=Pddt([None])
    with pytest.raises(TypeError):x.add(**{name:bad})
    with pytest.raises(TypeError):x.sub(**{name:[bad]})


@pytest.mark.parametrize("make",[list,tuple,deque,lambda x:iter(x),lambda x:np.array(x,dtype="i8"),lambda x:pd.Series(x,index=[99,1]),lambda x:pd.Index(x),lambda x:pd.array(x,dtype="Int64")])
def test_parameter_containers_are_positional_and_equal_length(make):
    x=Pddt(["2024-01-02","2024-01-03"],name="when")
    got=x.to_date(day=make([4,5]))
    assert got.day.tolist()==[4,5] and got.name=="when"
    with pytest.raises(ValueError):x.to_date(day=[4])
    with pytest.raises(ValueError):x.to_date(day=[4,5,6])


def test_generator_not_consumed_after_first_extra_target():
    seen=[]
    def values():
        for i in [1,2,3,4]:
            seen.append(i);yield i
    with pytest.raises(ValueError):Pddt(["2024-01-01"]).to_date(day=values())
    assert seen==[1,2]


@pytest.mark.parametrize("method,args,expected",[("to_year",(1,),"2025-01-31"),("to_quarter",(1,),"2024-04-30"),("to_month",(1,),"2024-02-29"),("to_weekday",(1,"Monday"),"2024-02-05"),("to_day",(1,),"2024-02-01")])
def test_calendar_offsets_match_scalar_pydt(method,args,expected):
    x=Pddt(["2024-01-31"],unit="us")
    assert getattr(x.pddt if method == "replace" else x,method)(*args)[0]==pd.Timestamp(expected)
    assert getattr(x.pddt if method == "replace" else x,method)(*args)[0].to_pydatetime()==getattr(Pydt(2024,1,31),method)(*args)


def test_selection_names_and_row_offsets():
    x=Pddt(["2024-01-31","2024-04-30"],unit="us")
    assert x.to_year([1,-1],month=["February","March"],day=31).strftime("%Y-%m-%d").tolist()==["2025-02-28","2023-03-31"]
    assert x.to_quarter([1,-1],month=[1,3]).strftime("%Y-%m-%d").tolist()==["2024-04-30","2024-03-30"]
    assert x.to_weekday([0,1],weekday=["Monday","Friday"]).day.tolist()==[29,10]
    with pytest.raises(ValueError):x.to_weekday(0,weekday=7)
    with pytest.raises(TypeError):x.to_day(None)


def test_explicit_replace_policies_and_automatic_calendar_operations():
    x=Pddt(["2024-03-10 01:30"],tz="America/New_York")
    with pytest.raises(ValueError,match="does not exist"):x.pddt.replace(hour=2)
    assert x.pddt.replace(hour=2,nonexistent="shift_forward").hour.tolist()==[3]
    assert x.to_time(hour=2)[0].strftime("%H:%M")=="03:30"
    before=Pddt(["2024-03-09 02:30"],tz="America/New_York")
    assert before.add(days=1)[0].strftime("%H:%M")=="03:30"
    after=Pddt(["2024-03-10 03:30"],tz="America/New_York")
    assert after.to_time(hour=2)[0].strftime("%H:%M")=="01:30"
    skipped=Pddt(["2011-12-29 12:00"],tz="Pacific/Apia")
    with pytest.raises(ValueError,match="calendar day"):skipped.to_day(1)


def test_replacement_zone_is_wall_reinterpretation_and_none_removes_zone():
    x=Pddt(["2024-01-02 12:00"],tz="Asia/Shanghai")
    assert x.pddt.replace(tzinfo="UTC").hour.tolist()==[12]
    assert x.pddt.replace(tzinfo=None).hour.tolist()==[12]
    assert x.pddt.replace(tzinfo=None).tz is None


def test_empty_parameters_and_native_integer_columns_are_validated():
    x=Pddt([])
    assert len(x.pddt.replace(day=[]))==0
    with pytest.raises(TypeError):x.to_date(day=np.array([],dtype="float64"))
    with pytest.raises(TypeError):x.to_date(day=np.array([],dtype="datetime64[us]"))
    with pytest.raises(TypeError):x.add(days=None)
    with pytest.raises(ValueError):x.pddt.replace(day=[1])


def test_polars_parameters_share_the_same_integer_contract():
    pl=pytest.importorskip("polars")
    x=Pddt(["2024-01-02","2024-01-03"])
    assert x.to_date(day=pl.Series([4,5])).day.tolist()==[4,5]
    with pytest.raises(TypeError):x.to_date(day=pl.Series([None,5]))


def test_scalar_and_array_calendar_moves_do_not_skip_an_entire_missing_day():
    from zoneinfo import ZoneInfo
    scalar=Pydt(2011,12,29,12,tzinfo=ZoneInfo("Pacific/Apia"))
    with pytest.raises(ValueError,match="calendar day"):
        scalar.to_day(1)
    with pytest.raises(ValueError,match="calendar day"):
        Pddt([scalar]).to_day(1)


def test_explicit_replace_policies_remain_distinct_from_automatic_day_rule():
    x=Pddt(["2011-12-29 12:00"],tz="Pacific/Apia")
    assert x.pddt.replace(day=30,nonexistent="shift_forward")[0].day==31

# Every implemented SV01–SV04 numeric position is exercised as a scalar and
# as an equal-length target column. Query targets are covered separately in
# test_rewrite_queries.py, including scalar/column, names, and missing values.
_SV_POSITIONS=[]
for _method,_fields in [("replace","year month day hour minute second microsecond nanosecond"),("to_datetime","year month day hour minute second microsecond nanosecond"),("to_date","year month day"),("to_time","hour minute second microsecond nanosecond"),("add","years quarters months weeks days hours minutes seconds milliseconds microseconds nanoseconds"),("sub","years quarters months weeks days hours minutes seconds milliseconds microseconds nanoseconds"),("to_year","offset month day"),("to_quarter","offset month day"),("to_month","offset day"),("to_weekday","offset weekday"),("to_day","offset")]:
    _SV_POSITIONS.extend((_method,_field) for _field in _fields.split())
for _period,_fields in [("year","month day"),("quarter","month day"),("month","day"),("weekday","weekday")]:
    for _prefix in ["curr","prev","next"]:
        _SV_POSITIONS.extend((f"to_{_prefix}_{_period}",_field) for _field in _fields.split())

@pytest.mark.parametrize("method,field",_SV_POSITIONS)
def test_every_existing_column_numeric_position_rejects_bool_and_float(method,field):
    x=Pddt([None,None],unit="ns")
    base={"offset":0} if method in ["to_year","to_quarter","to_month","to_weekday","to_day"] else {}
    for bad in [True,1.0,[1.0,1.0],[True,True]]:
        kwargs={**base,field:bad}
        with pytest.raises(TypeError):getattr(x.pddt if method == "replace" else x,method)(**kwargs)

@pytest.mark.parametrize("method,field",_SV_POSITIONS)
def test_every_existing_column_numeric_position_has_scalar_and_row_routes(method,field):
    x=Pddt(["2024-01-02 03:04:05.000006001","2024-01-03 03:04:05.000006001"],unit="ns")
    value=2025 if field=="year" else 1
    base={"offset":0} if method in ["to_year","to_quarter","to_month","to_weekday","to_day"] else {}
    a=getattr(x.pddt if method == "replace" else x,method)(**{**base,field:value})
    b=getattr(x.pddt if method == "replace" else x,method)(**{**base,field:[value,value]})
    assert a.asi8.tolist()==b.asi8.tolist()
    assert b.unit=="ns"
