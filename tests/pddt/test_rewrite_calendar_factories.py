"""P07 actual source roles, wide calendar fields and once-read broadcasting."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt, Pydt


def test_real_date_factories_keep_their_distinct_timezone_meanings():
    source=datetime(2024,5,7,12,34,56,123456,tzinfo=timezone(timedelta(hours=8)))
    day=Pddt.fromdate(source,size=2)
    assert day.tzinfo is None and day.hour.tolist()==[0,0]
    assert day.year.tolist()==[2024,2024] and day.day.tolist()==[7,7]
    midnight=Pddt.fromdate(source,size=1,tz="UTC")
    assert midnight.tzinfo is timezone.utc and midnight.hour.tolist()==[0]
    original=Pddt.fromdatetime(source,size=1)
    replacement=Pddt.fromdatetime(source,size=1,tz="UTC")
    converted=Pddt([source],tz="UTC")
    assert original.hour.tolist()==[12] and original.asi8[0]==pd.Timestamp(source).as_unit("us").asm8.view("i8")
    assert replacement.hour.tolist()==[12] and replacement.tzinfo is timezone.utc
    assert converted.hour.tolist()==[4]
    assert replacement.microsecond.tolist()==[123456]


def test_timestamp_nanoseconds_and_wide_years_are_not_lost():
    source=pd.Timestamp("2024-05-07T12:34:56.123456789+08:00")
    result=Pddt.fromdatetime(source,size=3,tz="UTC")
    assert result.unit=="ns" and result.nanosecond.tolist()==[789]*3
    assert result.hour.tolist()==[12]*3
    with pytest.raises(ValueError):Pddt.fromdatetime(source,size=1,unit="us")
    wide=pd.Timestamp(np.datetime64("25000-05-07","us"))
    assert Pddt.fromdatetime([wide]).year.tolist()==[25000]
    assert Pddt.fromdate([wide]).year.tolist()==[25000]


@pytest.mark.parametrize("method,bad",[("fromdate","2024-05-07"),("fromdate",np.datetime64("2024-05-07")),("fromdatetime",date(2024,5,7)),("fromdatetime64",datetime(2024,5,7)),("fromdatetime64",1)])
def test_dedicated_source_roles_reject_unrelated_inputs(method,bad):
    with pytest.raises(TypeError):getattr(Pddt,method)(bad,size=1)


def test_numpy_factory_respects_multiplier_endian_and_naive_attachment():
    source=np.array([1,2,np.iinfo("i8").min],dtype="i8").view("datetime64[3ms]").astype(">M8[3ms]")
    result=Pddt.fromdatetime64(source,tz="Asia/Shanghai")
    assert result.unit=="ms" and result.tzinfo.key=="Asia/Shanghai"
    assert result.asi8.tolist()==[3-8*3600*1000,6-8*3600*1000,np.iinfo("i8").min]
    assert Pddt.fromdatetime64(np.datetime64(123,"ns"),size=2).asi8.tolist()==[123,123]
    with pytest.raises(ValueError):Pddt.fromdatetime64(np.datetime64(123,"ns"),size=2,unit="us")


def test_native_pandas_and_polars_sources_preserve_zone_or_replace_clock():
    source=pd.DatetimeIndex(["2024-05-07T12:34:56.123456789+08:00",None],name="events")
    for data in (source,pd.Series(source,name="events"),source.array):
        result=Pddt.fromdatetime(data)
        assert result.asi8.tolist()==source.asi8.tolist() and result.unit==source.unit
        replaced=Pddt.fromdatetime(data,tz="UTC")
        assert replaced.hour[0]==12 and replaced.nanosecond[0]==789 and replaced.isna()[1]
        days=Pddt.fromdate(data)
        assert days.tzinfo is None and days.hour[0]==0 and days.isna()[1]
    pl=pytest.importorskip("polars")
    column=pl.Series("events",[1_234_567_891,None],dtype=pl.Datetime("ns","UTC"))
    assert Pddt.fromdatetime(column).asi8.tolist()==[1_234_567_891,np.iinfo("i8").min]
    dates=pl.Series([date(2024,5,7),None])
    assert Pddt.fromdate(dates).day.tolist()[0]==7
    with pytest.raises(TypeError):Pddt.fromdatetime(dates)


def test_date_factory_regional_reinterpretation_uses_array_policy():
    source=datetime(2024,11,3,1,30,tzinfo=ZoneInfo("America/New_York"),fold=1)
    kept=Pddt.fromdatetime(source,size=1)
    assert kept.asi8[0]==pd.Timestamp(source).as_unit("us").asm8.view("i8")
    with pytest.raises(ValueError):Pddt.fromdatetime(source,size=1,tz="America/New_York")
    chosen=Pddt.fromdatetime(source,size=1,tz="America/New_York",ambiguous=True)
    assert chosen.asi8[0]!=kept.asi8[0]


@pytest.mark.parametrize("ordinal,expected",[(1,"0001-01-01"),(0,"0000-12-31"),(-1,"0000-12-30"),(-365,"0000-01-01")])
def test_ordinal_zero_and_negative_are_real_days(ordinal,expected):
    result=Pddt.fromordinal(ordinal,size=2)
    assert result.unit=="us" and result.asi8.tolist()==[int(np.datetime64(expected,"us").view("i8"))]*2


@pytest.mark.parametrize("year",[-401,-400,-1,0,1,2020,2021,10000])
def test_day_of_year_and_iso_calendar_wide_gregorian_expected(year):
    end=Pddt.fromdayofyear(year,999,size=1)
    assert (end.year[0],end.month[0],end.day[0])==(year,12,31)
    if 1<=year<=9999:
        scalar=Pydt.fromisocalendar(year,999,999)
        iso=Pddt.fromisocalendar(year,999,999,size=1)
        assert (iso.year[0],iso.month[0],iso.day[0])==(scalar.year,scalar.month,scalar.day)
    jan4=int(np.datetime64(f"{year:04d}-01-04","D").view("i8"))
    monday=jan4-(jan4+3)%7
    first=Pddt.fromisocalendar(year,1,1,size=1)
    assert first.asi8[0]==monday*86400*1_000_000


def test_multiple_calendar_columns_are_positional_equal_length_and_scalar_broadcast():
    result=Pddt.fromisocalendar(pd.Series([2020,2021],index=[10,5]),[53,99],7)
    assert result.year.tolist()==[2021,2022] and result.day.tolist()==[3,2]
    with pytest.raises(ValueError):Pddt.fromisocalendar([2020],[1,2],1)
    with pytest.raises(ValueError):Pddt.fromdayofyear([2024],1,size=1)
    with pytest.raises(ValueError):Pddt.fromordinal(1)
    assert Pddt.fromdayofyear((y for y in [2023,2024]),60).day.tolist()==[1,29]


def test_integer_components_are_read_once_and_missing_masks_are_independent():
    class Year:
        reads=0
        def __index__(self):self.reads+=1;return 2024
    year=Year()
    result=Pddt.fromdayofyear(year,[1,2,3])
    assert result.day.tolist()==[1,2,3] and year.reads==1
    result=Pddt.fromdayofyear(pd.array([2024,None],dtype="Int64"),[60,1])
    assert result.day[0]==29 and result.isna()[1]
    with pytest.raises(ValueError):Pddt.fromdayofyear([None],[0])
    with pytest.raises(ValueError):Pddt.fromisocalendar(2024,0,1,size=0)
    for bad in (True,np.bool_(False),2024.0,"2024"):
        with pytest.raises(TypeError):Pddt.fromdayofyear(bad,1,size=1)


def test_calendar_capacity_and_safe_scalar_reservation_do_not_wrap():
    with pytest.raises(OverflowError):Pddt.fromdayofyear(2500,1,size=1,unit="ns")
    with pytest.raises(OverflowError):Pddt.fromordinal(1,size=1<<60)
    assert Pddt.fromisocalendar(2020,53,7,size=1).day.tolist()==[3]
    assert Pddt.fromisocalendar(2021,53,7,size=1).year.tolist()==[2022]


def test_extended_float_nan_does_not_bypass_integer_source_roles():
    if np.longdouble in (np.float16,np.float32,np.float64):
        pytest.skip("this platform aliases longdouble to an admitted float type")
    for source in (np.longdouble("nan"),np.array([np.longdouble("nan")],dtype=np.longdouble)):
        with pytest.raises(TypeError):Pddt.frommicroseconds(source,**({"size":1}if np.isscalar(source)else{}))
        with pytest.raises(TypeError):Pddt.fromdayofyear(source,1,**({"size":1}if np.isscalar(source)else{}))
