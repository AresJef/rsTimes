"""Named construction, standard pandas behavior, and timezone-aware persistence."""
import copy,pickle
from datetime import date,datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt,Pydt

@pytest.mark.parametrize('name,value,expected',[
 ('fromordinal',719163,'1970-01-01'),('fromseconds',1.5,'1970-01-01 00:00:01.5'),
 ('frommicroseconds',1500000,'1970-01-01 00:00:01.5'),
 ('fromisocalendar',{'year':2024,'week':1,'day':1},'2024-01-01'),
 ('fromdayofyear',{'year':2024,'doy':60},'2024-02-29'),
 ('fromdate',date(2024,1,2),'2024-01-02'),
 ('fromdatetime',datetime(2024,1,2,3,4),'2024-01-02 03:04'),
 ('fromdatetime64',np.datetime64('2024-01-02','ms'),'2024-01-02'),
 ('fromisoformat','2024-01-02T12:34:56.123456789','2024-01-02 12:34:56.123456789')])
def test_named_scalar_and_empty(name,value,expected):
    factory=getattr(Pddt,name)
    # P07: component factories take explicit named columns, not row mappings.
    call=(lambda **kw:factory(year=value['year'],week=value['week'],weekday=value['day'],**kw)) if name=='fromisocalendar' else (lambda **kw:factory(year=value['year'],doy=value['doy'],**kw)) if name=='fromdayofyear' else (lambda **kw:factory(value,**kw))
    x=call(size=2)
    assert len(x)==2 and x[0]==pd.Timestamp(expected)
    empty=call(size=0)
    assert isinstance(empty,Pddt) and len(empty)==0
    with pytest.raises(ValueError):call()
    with pytest.raises(ValueError):call(size=-1)
    with pytest.raises(TypeError):call(size=1.5)

@pytest.mark.parametrize('text',['Jan 2 2024','2024-02-30','2024-01-02 12:99','2024/01/02'])
def test_fromisoformat_rejects_non_iso_or_invalid(text):
    with pytest.raises(Exception):Pddt.fromisoformat(text,size=1)

def test_iso_basic_and_week_dates():
    assert Pddt.fromisoformat('20240102',size=1)[0]==pd.Timestamp('2024-01-02')
    assert Pddt.fromisoformat('2024-W01-1',size=1)[0]==pd.Timestamp('2024-01-01')

def test_calendar_mapping_and_dataframe():
    x=Pddt.fromisocalendar([2020,2024],[53,1],[7,1])
    with pytest.raises(TypeError):Pddt.fromisocalendar(pd.DataFrame({'year':[2020],'week':[53],'day':[7]}))
    assert x[0]==pd.Timestamp('2021-01-03') and x[1]==pd.Timestamp('2024-01-01')
    y=Pddt.fromdayofyear([2023,2024],[500,60])
    assert y[0]==pd.Timestamp('2023-12-31') and y[1]==pd.Timestamp('2024-02-29')

def test_range_unit_inference_and_strptime():
    assert Pddt.date_range('2024-01-01',periods=2).unit=='us'
    assert Pddt.date_range('2024-01-01T00:00:00.123456789',periods=2).unit=='ns'
    for unit in ['s','ms','us','ns']:assert Pddt.date_range('2024-01-01',periods=2,unit=unit).unit==unit
    x=Pddt.strptime(['02/01/2024'],'%d/%m/%Y')
    assert x[0]==pd.Timestamp('2024-01-02') and x.unit=='us'

def test_now_combine_and_zero_size():
    for method in [Pddt.now,Pddt.utcnow,Pddt.today]:assert len(method(0))==0
    x=Pddt.combine(date(2024,1,2),'12:30',size=2)
    assert x[0]==pd.Timestamp('2024-01-02 12:30')
    assert str(Pddt.utcnow(1).tz)=='UTC'

def test_properties_and_iso_columns_follow_pandas():
    x=Pddt(['2024-02-29',None])
    base=pd.DatetimeIndex(x)
    assert isinstance(x.date,np.ndarray) and isinstance(x.time,np.ndarray)
    assert x.is_leap_year.tolist()==base.is_leap_year.tolist()
    assert list(x.isocalendar().columns)==['year','week','day']
    assert x.days_in_year()[0]==366
    assert pd.isna(x.days_in_year()[1])
    assert x.days_in_quarter()[0]==91
    assert x.day_of_quarter()[0]==60
    assert x.toordinal()[0]==date(2024,2,29).toordinal()

def test_pickle_and_copies_keep_value_unit_zone_name_frequency():
    x=Pddt.date_range('2024-01-01',periods=3,tz='Asia/Shanghai',unit='us',name='sample')
    for y in [copy.copy(x),copy.deepcopy(x),pickle.loads(pickle.dumps(x))]:
        assert type(y) is Pddt
        assert y.unit==x.unit and y.tz==x.tz and y.name==x.name and y.freq==x.freq
        np.testing.assert_array_equal(y.asi8,x.asi8)

def test_fold_kept_for_fsp_unit_and_pydt_output():
    values=[datetime(2024,11,3,1,30,0,123456,tzinfo=ZoneInfo('America/New_York'),fold=i) for i in [0,1]]
    x=Pddt(values)
    y=x.fsp(3)
    assert [v.fold for v in y]==[0,1]
    assert (y.asi8[1]-y.asi8[0])==3600000000
    out=x.datetime()
    assert all(type(v) is Pydt for v in out)
    assert [v.fold for v in out]==[0,1]
    assert [v.utcoffset() for v in out]==[timedelta(hours=-4),timedelta(hours=-5)]
    assert x.as_unit('ns').asi8.tolist()==[n*1000 for n in x.asi8]

def test_timezone_names_and_iso_output_keep_actual_information():
    x=Pddt(['2024-01-01 12:00','2024-07-01 12:00',None],tz='America/New_York')
    assert x.tzname().tolist()==['EST','EDT',None]
    y=Pddt(['2024-01-01 00:00:00.123456789'])
    assert y.isoformat()[0]=='2024-01-01T00:00:00.123456789'

def test_standard_round_and_legacy_alias():
    x=Pddt(['2024-01-02 12:34:56'])
    assert x.floor('15min')[0]==pd.Timestamp('2024-01-02 12:30')
    assert x.ceil(freq='min')[0]==pd.Timestamp('2024-01-02 12:35')
    with pytest.raises(TypeError):x.ceil(unit='m')
    with pytest.raises(TypeError):x.round('s',unit='s')

@pytest.mark.parametrize('zone',['UTC','Asia/Shanghai','America/New_York'])
@pytest.mark.parametrize('reverse',[False,True])
def test_mixed_naive_aware_localizes_only_naive_rows(zone,reverse):
    values=['2024-01-01','2024-01-02T00:00:00Z']
    if reverse:values.reverse()
    result=Pddt(values,tz=zone)
    expected=[pd.Timestamp(s).tz_localize(zone) if pd.Timestamp(s).tzinfo is None else pd.Timestamp(s).tz_convert(zone) for s in values]
    np.testing.assert_array_equal(result.asi8,[v.as_unit(result.unit).value//(1000 if result.unit=='us' else 1) for v in expected])
    assert isinstance(result.tz,timezone) if zone=='UTC' else isinstance(result.tz,ZoneInfo)

@pytest.mark.parametrize('unit',['s','ms','us','ns'])
def test_float_seconds_match_exact_ratio_rounding(unit):
    from fractions import Fraction
    denominator={'s':1,'ms':1000,'us':1000000,'ns':1000000000}[unit]
    values=np.array([0,1,-1,1000000001,-1000000001,2**53+1,-2**53-1,2**63-1,-2**63+1],dtype='i8')
    data=Pddt(values.view('datetime64['+unit+']'))
    expected=[float(Fraction(int(n),denominator)) for n in values]
    np.testing.assert_array_equal(data.toseconds().to_numpy(),expected)

@pytest.mark.parametrize('text',['2021-W53-1','2021W531','2023-366','2023366'])
def test_iso_only_rejects_nonexistent_week_or_ordinal_day(text):
    with pytest.raises(Exception):Pddt.fromisoformat(text,size=1)

@pytest.mark.parametrize('text',['2024-01-02T12','2024-01-02T1234','2024-01-02T12Z','2024-01-02T12+08:00','2024-01-02T1234.123456789'])
def test_iso_short_clock_forms_keep_existing_capability(text):
    expected=pd.Timestamp(text) if '.123' not in text else pd.Timestamp('2024-01-02T12:34:00.123456789')
    result=Pddt.fromisoformat(text,size=1)
    assert result[0]==expected
