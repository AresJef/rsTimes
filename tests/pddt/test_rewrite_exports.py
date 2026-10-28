from datetime import date,datetime,timedelta,timezone,tzinfo
from zoneinfo import ZoneInfo
import random
import struct
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt,Pydt

@pytest.mark.parametrize('unit,scale',[('s',10**9),('ms',10**6),('us',1000),('ns',1)])
def test_seconds_are_single_rounded_from_complete_integer_coordinates(unit,scale):
    r=random.Random(72)
    ticks=[0,1,-1,2**53-1,2**53,2**53+1,2**63-1,-2**63+1]
    ticks += [r.randrange(-2**63+1,2**63) for _ in range(512)]
    x=Pddt(np.array(ticks,dtype='int64').view(f'datetime64[{unit}]'))
    actual=x.toseconds().to_numpy()
    expected=[(tick*scale)/10**9 for tick in ticks]
    assert actual.tobytes()==np.array(expected,dtype='float64').tobytes()


def test_clock_coordinates_utc_coordinates_and_explicit_microsecond_cut():
    x=Pddt(['1970-01-01 08:00',None],tz='Asia/Shanghai')
    assert x.toseconds()[0]==28800.0 and x.toseconds(utc=True)[0]==0.0
    assert x.tomicroseconds()[0]==28800000000 and x.tomicroseconds(utc=True)[0]==0
    assert pd.isna(x.toseconds()[1]) and pd.isna(x.tomicroseconds()[1])
    assert Pddt([np.datetime64(-1,'ns')]).tomicroseconds().tolist()==[-1]
    for value in [None,1,'false']:
        with pytest.raises(TypeError):x.toseconds(value)
        with pytest.raises(TypeError):x.tomicroseconds(value)
    assert x.toseconds(np.bool_(True))[0]==0


def test_timestamp_naive_uses_one_local_zone_and_aware_does_not(monkeypatch,request):
    import rstimes._localization as local
    local.named_timezone.cache_clear();request.addfinalizer(local.named_timezone.cache_clear)
    calls=[]
    def zone():calls.append(1);return timezone(timedelta(hours=8))
    monkeypatch.setattr(local,'local_timezone',zone)
    assert Pddt([None]).timestamp().isna().all() and not calls
    aware=Pddt(['1970-01-01 08:00'],tz='Asia/Shanghai')
    assert aware.timestamp().tolist()==[0.0] and not calls
    x=Pddt(['1970-01-01 08:00:00.000000001','1970-01-01 08:00:01'])
    assert x.timestamp().tolist()==[1e-9,1.0] and calls==[1]


def test_timestamp_missing_and_ambiguous_local_values_need_explicit_policy(monkeypatch,request):
    import rstimes._localization as local
    local.named_timezone.cache_clear();request.addfinalizer(local.named_timezone.cache_clear)
    monkeypatch.setattr(local,'local_timezone',lambda:ZoneInfo('America/New_York'))
    for value in ['2024-03-10 02:30','2024-11-03 01:30']:
        with pytest.raises(ValueError,match='tz_localize'):Pddt([value]).timestamp()


_KEYS=['tm_year','tm_mon','tm_mday','tm_hour','tm_min','tm_sec','tm_wday','tm_yday','tm_isdst']
_DTYPES=['Int64','Int8','Int8','Int8','Int8','Int8','Int8','Int16','Int8']
@pytest.mark.parametrize('data',[[],[None],['2024-02-29 12:34:56',None]])
def test_time_tables_keep_nine_ordered_nullable_types_even_when_empty(data):
    for name in ['timedf','utctimedf']:
        result=getattr(Pddt(data,name='ignored'),name)()
        assert list(result.columns)==_KEYS
        assert [str(v) for v in result.dtypes]==_DTYPES
        assert result.index.equals(pd.RangeIndex(len(data)))
        if data:
            assert result.iloc[-1].isna().all()
        if len(data)==2:
            assert result.iloc[0].tolist()==[2024,2,29,12,34,56,3,60,-1 if name=='timedf' else 0]


@pytest.mark.parametrize('zone,expected',[(None,-1),(timezone.utc,-1),(ZoneInfo('UTC'),0),(timezone(timedelta(hours=8)),-1)])
def test_table_dst_none_is_different_from_real_zero(zone,expected):
    x=Pddt(['2024-01-01'],tz=zone)
    assert x.timedf().tm_isdst.tolist()==[expected]
    assert x.utctimedf().tm_isdst.tolist()==[0]


def test_local_vs_utc_tables_and_dst_original_callback():
    x=Pddt(['2024-01-01','2024-07-01'],tz='America/New_York')
    assert x.timedf().tm_isdst.tolist()==[0,1]
    assert x.utctimedf().tm_hour.tolist()==[5,4]
    error=RuntimeError('original DST callback')
    class Zone(tzinfo):
        fail=False
        def utcoffset(self,value):return timedelta(0)
        def dst(self,value):
            if self.fail:raise error
            return -timedelta(hours=1)
        def tzname(self,value):return 'CUSTOM'
        def fromutc(self,value):return value
    zone=Zone();x=Pddt(['2024-01-01'],tz=zone)
    assert x.timedf().tm_isdst.tolist()==[1]
    zone.fail=True
    assert x.utctimedf().tm_isdst.tolist()==[0]
    with pytest.raises(RuntimeError) as caught:x.timedf()
    assert caught.value is error


def test_final_object_exports_preserve_real_fold_and_target_precision():
    values=np.array(['2024-11-03T05:30:00.123456789','2024-11-03T06:30:00.123456789','NaT'],dtype='datetime64[ns]')
    x=Pddt(values,tz='UTC').tz_convert('America/New_York')
    output=x.datetime()
    assert output.dtype==object and all(type(v) is Pydt for v in output[:2])
    assert [v.fold for v in output[:2]]==[0,1]
    assert [v.microsecond for v in output[:2]]==[123456,123456]
    assert output[2] is pd.NaT
    assert [v.fold for v in x.time[:2]]==[0,1]
    assert all(v.tzinfo is None for v in x.time[:2])
    assert [v.fold for v in x.timetz[:2]]==[0,1]
    assert all(v.tzinfo is x.tz for v in x.timetz[:2])
    assert x.time[2] is pd.NaT and x.timetz[2] is pd.NaT
    assert x.date.tolist()==[date(2024,11,3),date(2024,11,3),pd.NaT]


def test_wide_date_queries_work_until_a_python_object_is_requested():
    x=Pddt(['0000-01-01'],unit='us')
    assert x.toordinal().tolist()==[-365]
    assert x.time[0].hour==0
    assert x.ctime().tolist()==['Sat Jan  1 00:00:00 0000']
    for name in ['datetime','date']:
        with pytest.raises(ValueError):
            value=getattr(x,name)
            if callable(value):value()


def test_naive_values_preserve_wall_coordinates_and_current_unit():
    x=Pddt(['1970-01-01 08:00:00.000000001',None],tz='Asia/Shanghai')
    assert x.values_naive.dtype==np.dtype('datetime64[ns]')
    assert x.values_naive.view('int64').tolist()==[28800000000001,np.iinfo('int64').min]
    fractional=Pddt([0],unit='ms',tz=timezone(timedelta(microseconds=500)))
    with pytest.raises(ValueError):fractional.values_naive
    assert fractional.as_unit('us').values_naive.view('int64').tolist()==[500]


@pytest.mark.parametrize('spec,clock',[('auto','12:30:45.123456789'),('h','12'),('hours','12'),('m','12:30'),('min','12:30'),('minutes','12:30'),('s','12:30:45'),('seconds','12:30:45'),('ms','12:30:45.123'),('milliseconds','12:30:45.123'),('us','12:30:45.123456'),('microseconds','12:30:45.123456'),('ns','12:30:45.123456789'),('nanoseconds','12:30:45.123456789')])
def test_iso_specs_and_unicode_separator(spec,clock):
    x=Pddt(['2024-01-01 12:30:45.123456789',None],name='when')
    output=x.isoformat(sep='日',timespec=spec)
    assert output[0]=='2024-01-01日'+clock and pd.isna(output[1]) and output.name=='when'


def test_iso_offset_precision_and_options_validation():
    x=Pddt([0],unit='ns',tz=timezone(timedelta(seconds=1,microseconds=2)))
    assert x.isoformat().tolist()==['1970-01-01T00:00:01.000002+00:00:01.000002']
    empty=Pddt([])
    for sep in ['', 'XX']:
        with pytest.raises(ValueError):empty.isoformat(sep=sep)
    for spec in ['H','M','bad']:
        with pytest.raises(ValueError):empty.isoformat(timespec=spec)
    with pytest.raises(TypeError):empty.isoformat(sep=None)
    with pytest.raises(TypeError):empty.isoformat(timespec=None)


def test_names_use_shared_cldr_and_actual_timezone_names():
    x=Pddt(['2024-01-01','2024-07-01',None],tz='America/New_York')
    assert x.tzname().tolist()==['EST','EDT',None]
    assert Pddt(['2024-01-01',None]).tzname().tolist()==[None,None]
    for locale in [None,'en_US','zh_CN','fr_FR']:
        assert x.month_name(locale)[0]==Pydt(2024,1,1).month_name(locale)
        assert x.weekday_name(locale)[0]==Pydt(2024,1,1).weekday_name(locale)
    with pytest.raises(ValueError):Pddt([]).month_name('unknown')
    with pytest.raises(TypeError):Pddt([]).weekday_name(1)


def test_ctime_and_complete_mature_strftime():
    x=Pddt(['2024-10-01 08:19:05.123456789',None])
    assert x.ctime()[0]=='Tue Oct  1 08:19:05 2024'
    assert x.strftime('')[0]==''
    assert x.strftime('%Y-%m-%d %j %V')[0]==datetime(2024,10,1).strftime('%Y-%m-%d %j %V')
    for value in [None,1,b'%Y']:
        with pytest.raises(TypeError):x.strftime(value)


def test_metadata_queries_keep_their_scalar_role(monkeypatch):
    import rstimes.pddt as module
    naive=Pddt([]);utc=Pddt([],tz='UTC')
    assert naive.tzinfo is None and not naive.is_utc() and not naive.is_local()
    assert utc.tzinfo is timezone.utc and utc.is_utc()
    assert isinstance(utc.tz_available,set)
    monkeypatch.setattr(module,'_local_timezone',lambda:utc.tz)
    assert utc.is_local()
