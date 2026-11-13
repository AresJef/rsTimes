"""Real interface gaps identified in the independent review."""
from datetime import date,datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt

@pytest.mark.parametrize('unit',[None,'s','ms','us','ns'])
def test_integer_nat_is_missing_at_construction_only(unit):
    result=Pddt([-2**63],unit=unit)
    assert result.isna().tolist()==[True]
    assert result.unit==('ns' if unit is None else unit)

@pytest.mark.parametrize('hours',[0,8])
@pytest.mark.parametrize('reverse',[False,True])
def test_same_fixed_zone_across_datetime_and_text(hours,reverse):
    tz=timezone(timedelta(hours=hours))
    text='2024-01-02T00:00:00'+('Z' if hours==0 else '+08:00')
    values=[datetime(2024,1,1,tzinfo=tz),text]
    if reverse:values.reverse()
    result=Pddt(values)
    assert result.tz is not None and len(result)==2
    assert [v.hour for v in result]==[0,0]

@pytest.mark.parametrize('container',[pd.Series,pd.Index])
def test_text_container_keeps_name(container):
    assert Pddt(container(['2024-01-01'],name='sample')).name=='sample'
    assert Pddt(container(['2024-01-01'],name='sample'),name='other').name=='other'

def test_predicate_does_not_construct_an_unrelated_dst_time():
    x=Pddt(['2024-03-06 02:30',None],tz='America/New_York')
    assert x.is_last_of('W').tolist()==[False,False]
    assert x.is_start_of('Sunday').tolist()==[False,False]
    values=[datetime(2024,11,3,1,30,tzinfo=ZoneInfo('America/New_York'),fold=f) for f in [0,1]]
    assert Pddt(values).is_last_of('W').tolist()==[True,True]

def test_named_weekday_boundaries_finish_before_timezone_localization():
    x=Pddt(['2024-03-06 02:30'],tz='America/New_York')
    assert x.to_start_of('Sunday')[0]==pd.Timestamp('2024-03-10 00:00',tz='America/New_York')
    assert x.to_end_of('Friday')[0]==pd.Timestamp('2024-03-08 23:59:59.999999',tz='America/New_York')
    y=Pddt(['2024-03-10 00:00'],tz='America/New_York')
    assert y.is_start_of('Sunday').tolist()==[True]

def test_predicate_near_ns_boundary_does_not_need_out_of_range_result():
    x=Pddt(np.array([-2**63+1,2**63-1],dtype='i8').view('datetime64[ns]'))
    assert x.is_start_of('Y').tolist()==[False,False]
    assert x.is_end_of('Y').tolist()==[False,False]

@pytest.mark.parametrize('start,expected',[(date(2024,1,1),'s'),(np.datetime64('2024-01-01','s'),'s'),(np.datetime64('2024-01-01','ms'),'ms')])
def test_range_keeps_endpoint_unit(start,expected):
    assert Pddt.date_range(start,periods=2).unit==expected

@pytest.mark.parametrize('frequency,unit',[('ms','ms'),('us','us'),('ns','ns'),('500ns','ns')])
def test_range_frequency_raises_resolution_when_needed(frequency,unit):
    x=Pddt.date_range(date(2024,1,1),periods=2,freq=frequency)
    assert x.unit==unit
    assert x.asi8[1]-x.asi8[0]==(500 if frequency=='500ns' else 1)

def test_strptime_wide_date_does_not_pass_through_nanoseconds():
    for data,kw in [('1000-01-01',{'size':1}),(['1000-01-01'],{})]:
        x=Pddt.strptime(data,'%Y-%m-%d',unit='us',**kw)
        assert x.unit=='us' and x[0].year==1000

@pytest.mark.parametrize('method,kwargs',[(Pddt.utcnow,{}),(Pddt.now,{'tz':'Asia/Shanghai'}),(Pddt.combine,{'date':date(2024,1,1),'time':'12:30','tz':'Asia/Shanghai'})])
def test_empty_named_construction_retains_timezone(method,kwargs):
    x=method(size=0,**kwargs)
    assert len(x)==0 and x.tz is not None

def test_native_transform_accepts_real_strided_supported_unit():
    data=np.arange(12,dtype='i8').view('datetime64[us]')[::2]
    x=Pddt(data)
    assert np.shares_memory(data,x.asi8)
    assert x.asi8.strides==(16,)
    assert x.to_day(1)[0]==pd.Timestamp('1970-01-02')

def test_range_custom_offset_can_require_microseconds():
    x=Pddt.date_range(date(2024,1,1),periods=2,freq=pd.DateOffset(microseconds=1))
    assert x.unit=='us' and x.asi8[1]-x.asi8[0]==1

def test_tz_switch_none_preserves_wall_time_like_existing_pydt():
    naive=Pddt(['2024-01-01 12:00'])
    assert naive.tz_switch(None) is naive
    aware=Pddt(['2024-01-01 12:00'],tz='Asia/Shanghai')
    result=aware.tz_switch(None)
    assert result.tz is None and result.hour.tolist()==[12]

def test_numpy_booleans_are_rejected_like_python_booleans():
    with pytest.raises(TypeError):Pddt(np.array([True],dtype=bool))

@pytest.mark.parametrize('method,unit',[('fromseconds','s'),('frommicroseconds','us')])
def test_numpy_integer_named_construction_does_not_round_through_float(method,unit):
    value=2**53+1
    result=getattr(Pddt,method)(np.array([value],dtype='i8'),unit=unit)
    assert result.asi8.tolist()==[value]

@pytest.mark.parametrize('values,expected',[
    pytest.param([-2**63,None],'ns',id='values0-s'),
    pytest.param([-float(2**63)],'ns',id='values1-s'),([float('nan')],'s'),
    ([np.datetime64('NaT','ms')],'ms'),([np.datetime64('NaT','us')],'us'),([np.datetime64('NaT','ns')],'ns'),
    (np.array([float('nan')]),'ns'),(pd.Series([float('nan')]),'ns')])
def test_missing_source_resolution_follows_fixed_pandas3(values,expected):
    x=Pddt(values)
    assert x.unit==expected and x.isna().all()

@pytest.mark.parametrize('freq,unit',[('1000ns','ns'),('1000ms','ms'),('1000000us','us')])
def test_range_frequency_keeps_declared_precision(freq,unit):
    assert Pddt.date_range(date(2024,1,1),periods=2,freq=freq).unit==unit

def test_calendar_finite_float_truncation_and_size_distinction():
    x=Pddt(['2024-01-31 12:34:56'])
    # P04/P11: calendar quantities and absolute fields are integer protocol only.
    for operation in (lambda:x.add(months=1.9,days=-1.9),lambda:x.pddt.replace(month=2.9,hour=9.9),lambda:x.to_year(1.9)):
        with pytest.raises(TypeError):operation()
    with pytest.raises(TypeError):Pddt.now(1.9)
    for value in ('2',float('nan'),float('inf')):
        with pytest.raises(TypeError):x.add(days=value)

@pytest.mark.parametrize('unit',['s','ms','us','ns'])
@pytest.mark.parametrize('zone',[None,'UTC'])
def test_diff_reuses_standard_datetime_index_without_changing_results(unit,zone):
    x=Pddt(['2024-01-03',None],tz=zone,unit='us')
    other=pd.DatetimeIndex(['2024-01-01',None],tz=zone).as_unit(unit)
    result=x.diff(other,'s')
    assert result[0]==172800 and pd.isna(result[1])
    assert result.tolist()==x.diff(Pddt(other),'s').tolist()
