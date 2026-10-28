"""P07 dedicated ISO parsing and one-buffer date/clock combination."""
from datetime import date,datetime,time,timedelta,timezone
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt


@pytest.mark.parametrize("text",[
    "2024-01-02","20240102","2024-W01-2","2024W012","2024-W01",
    "2024-01-02T12","2024-01-02x12:30","2024-01-02☀12:30:12",
    "20240102T123012.123456","2024-01-02T12:30.5",
    "2024-01-02T12.5","2024-01-02T12:30:12,123456",
    "2024-01-02T12:30+08:00","2024-01-02T12:30-083012",
    "2024-01-02T12:30Z","2024-01-02T12:30+08",
])
def test_dedicated_iso_covers_standard_datetime_examples(text):
    expected=datetime.fromisoformat(text)
    result=Pddt.fromisoformat(text,size=2)
    actual=result[0]
    assert (actual.year,actual.month,actual.day,actual.hour,actual.minute,actual.second,actual.microsecond)==(
        expected.year,expected.month,expected.day,expected.hour,expected.minute,expected.second,expected.microsecond)
    assert actual.utcoffset()==expected.utcoffset()


@pytest.mark.parametrize("text,expected",[("2024-002","2024-01-02"),("2024002","2024-01-02"),("0000-001","0000-01-01"),("25000-05-07","25000-05-07")])
def test_iso_calendar_extensions_use_actual_calendar_without_datetime_capacity(text,expected):
    result=Pddt.fromisoformat(text,size=1)
    assert result.asi8[0]==np.datetime64(expected,"us").view("i8")


@pytest.mark.parametrize("bad",["Jan 2 2024","2024-02-30","2023-366","2024-W54-1","2024-W01-8","2024-01-02T24:00","2024-01-02T12:60","2024-01-02T12:30+24:00","2024-01-02T12:30trash","2024/01/02","2024-01-02T12:30.","2024-01-02 "])
def test_iso_invalid_values_do_not_fall_back_or_clamp(bad):
    with pytest.raises(ValueError):Pddt.fromisoformat([bad])


def test_iso_nanoseconds_missing_positions_units_and_atomic_failure():
    result=Pddt.fromisoformat(["2024-01-02T12:30:00.123456789+08:00",None,"NaT"])
    assert result.unit=="ns" and result.nanosecond[0]==789 and result.isna().tolist()==[False,True,True]
    assert Pddt.fromisoformat(["2024-01-02T12:30:00.123456000"]).unit=="ns"
    with pytest.raises(ValueError):Pddt.fromisoformat(["2024-01-02T12:30:00.123456789"],unit="us")
    with pytest.raises(ValueError):Pddt.fromisoformat(["2024-01-02T12:30Z","2024-01-02T12:30+08:00"])
    with pytest.raises(TypeError):Pddt.fromisoformat([datetime(2024,1,2)])


def test_iso_fractional_offset_keeps_actual_ticks_despite_pandas_scalar_display_limit():
    expected=datetime.fromisoformat("2024-01-02T12:30-083012.5")
    result=Pddt.fromisoformat("2024-01-02T12:30-083012.5",size=1)
    utc=expected.astimezone(timezone.utc).replace(tzinfo=None)-datetime(1970,1,1)
    ticks=utc.days*86400000000+utc.seconds*1000000+utc.microseconds
    assert result.asi8.tolist()==[ticks] and result.tzinfo.utcoffset(None)==expected.utcoffset()
    # pandas itself omits offset microseconds while displaying a scalar's local
    # clock; the true UTC storage and complete timezone metadata remain correct.
    reference=pd.DatetimeIndex([expected]).as_unit("us")
    assert result.asi8.tolist()==reference.asi8.tolist()


def test_combine_scalar_and_column_fields_do_not_inherit_date_zone_or_clock_date():
    dates=[datetime(2024,1,2,23,tzinfo=timezone(timedelta(hours=-5))),date(2024,1,3)]
    clock=pd.Timestamp("2000-05-07T12:34:56.123456789+08:00")
    result=Pddt.combine(dates,clock)
    assert result.year.tolist()==[2024,2024] and result.day.tolist()==[2,3]
    assert result.hour.tolist()==[12,12] and result.nanosecond.tolist()==[789,789]
    assert result.tzinfo.utcoffset(None)==timedelta(hours=8)
    replaced=Pddt.combine(dates,clock,tz="UTC")
    assert replaced.tzinfo is timezone.utc and replaced.hour.tolist()==[12,12]


def test_combine_text_uses_shared_parser_and_no_temporary_pydt(monkeypatch):
    import rstimes.pydt as module
    def forbidden(*a,**kw):raise AssertionError("Pddt.combine must not construct a Pydt intermediate")
    monkeypatch.setattr(module.Pydt,"combine",forbidden)
    result=Pddt.combine(["2024-01-02","2024-01-03"],"12:30:00.123456789")
    assert result.day.tolist()==[2,3] and result.nanosecond.tolist()==[789,789]
    assert Pddt.combine("2024-01-02","12:30",size=1).hour.tolist()==[12]
    with pytest.raises(ValueError):Pddt.combine("unknown","12:30",size=1)
    with pytest.raises(ValueError):Pddt.combine("2024-01-02","unknown",size=1)


def test_combine_today_is_lazy_once_and_empty_or_missing_clocks_need_no_local_zone(monkeypatch):
    import rstimes.pddt as module
    calls=[]
    def local():calls.append(1);return timezone.utc
    monkeypatch.setattr(module,"_local_timezone",local)
    result=Pddt.combine(None,[time(12),time(13),time(14)])
    assert result.day.tolist()==[datetime.now(timezone.utc).day]*3 and calls==[1]
    calls.clear()
    assert Pddt.combine(None,[]).empty
    assert Pddt.combine(None,[pd.NaT,None]).isna().all()
    assert Pddt.combine(None,None,size=0).empty
    assert calls==[]


def test_combine_missing_collection_positions_and_positional_broadcast():
    result=Pddt.combine(pd.Series([date(2024,1,2),None],index=[8,1]),[time(12),time(13)])
    assert result.hour[0]==12 and result.isna()[1]
    assert Pddt.combine([date(2024,1,2),date(2024,1,3)],None).hour.tolist()==[0,0]
    with pytest.raises(ValueError):Pddt.combine([date(2024,1,2)],[time(12),time(13)])
    with pytest.raises(ValueError):Pddt.combine(date(2024,1,2),time(12))
    with pytest.raises(ValueError):Pddt.combine([date(2024,1,2)],time(12),size=1)


def test_native_time_columns_preserve_ns_null_chunks_and_only_time_role():
    pl=pytest.importorskip("polars")
    times=pl.concat([pl.Series([123_456_789],dtype=pl.Int64).cast(pl.Time),pl.Series([None],dtype=pl.Time)],rechunk=False)
    result=Pddt.combine(date(1970,1,1),times)
    assert result.unit=="ns" and result.asi8.tolist()==[123_456_789,np.iinfo("i8").min]
    with pytest.raises(ValueError):Pddt.combine(date(1970,1,1),times,unit="us")
    with pytest.raises(TypeError):Pddt.combine(times,time(12))
    with pytest.raises(TypeError):Pddt(times)


def test_combined_local_dates_apply_array_dst_instead_of_source_fold():
    clock=time(1,30,tzinfo=ZoneInfo("America/New_York"),fold=1)
    with pytest.raises(ValueError):Pddt.combine(date(2024,11,3),clock,size=1)
    early=Pddt.combine(date(2024,11,3),clock,size=1,ambiguous=True)
    late=Pddt.combine(date(2024,11,3),clock,size=1,ambiguous=False)
    assert late.asi8[0]-early.asi8[0]==3600*1_000_000
    with pytest.raises(ValueError):Pddt.combine(date(2024,3,10),time(2,30),size=1,tz="America/New_York")


def test_factory_child_constructs_once_from_complete_dates():
    class Child(Pddt):
        calls=[]
        def __new__(cls,data,**kw):
            cls.calls.append("new")
            return super().__new__(cls,data,**kw)
        def __init__(self,*a,**kw):self.calls.append("init")
    for factory,args,kwargs in [(Child.combine,([date(2024,1,2)],time(12)),{}),(Child.fromisoformat,("2024-01-02",),{"size":1}),(Child.fromdayofyear,(2024,[1,2]),{})]:
        Child.calls.clear();result=factory(*args,**kwargs)
        assert type(result)is Child and Child.calls==["new","init"]


def test_text_subclass_conversion_is_once_and_precedes_missing_marker_classification():
    class Text(str):
        reads=0
        def __str__(self):self.reads+=1;return "2024-01-02T12:30"
    value=Text("NaT")
    assert Pddt.fromisoformat(value,size=3).hour.tolist()==[12]*3 and value.reads==1
    value=Text("NaT")
    assert Pddt.combine([date(2024,5,7)]*3,value).hour.tolist()==[12]*3 and value.reads==1
