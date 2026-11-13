"""Remaining public output families, without repeating calendar matrices."""
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt,Pydt

@pytest.mark.parametrize('name',['year','quarter','month','day','hour','minute','second','microsecond','nanosecond','weekday','date','time','timetz','is_leap_year','days_in_month'])
def test_standard_properties_follow_pandas(name):
    values=np.array(['2024-02-29 12:34:56.123456','2024-05-08 09:10:11'],dtype='datetime64[us]')
    x=Pddt(values);ref=pd.DatetimeIndex(values)
    np.testing.assert_array_equal(np.asarray(getattr(x,name)),np.asarray(getattr(ref,name)))

def test_output_and_timezone_families():
    x=Pddt(['2024-02-29 12:34:56.123456'],tz='Asia/Shanghai',name='sample')
    base=pd.DatetimeIndex(x)
    assert x.strftime('%Y-%m-%d').tolist()==['2024-02-29']
    assert x.ctime()[0]=='Thu Feb 29 12:34:56 2024'
    assert x.month_name().tolist()==base.month_name().tolist()
    assert x.weekday_name().tolist()==base.day_name().tolist()
    assert x.isoyear()[0]==2024 and x.isoweek()[0]==9 and x.isoweekday()[0]==4
    assert x.day_of_month()[0]==29 and x.is_quarter(1)[0] and x.is_day(29)[0]
    assert x.millisecond[0]==123 and isinstance(x.tz_available,set)
    assert x.timedf().iloc[0].tm_hour==12 and x.utctimedf().iloc[0].tm_hour==4
    assert x.astimezone('UTC').hour[0]==4 and x.tz_switch('UTC',naive=True).hour[0]==4
    assert x.tz_convert('UTC').is_utc() and isinstance(x.is_local(),bool)
    assert x.timestamp()[0]==x.toseconds(utc=True)[0]
    assert isinstance(x.datetime()[0],Pydt)
    assert x.is_past()[0] and not x.is_future()[0]

def test_unix_factory_timezones_and_python_subclass_results():
    assert Pddt.fromtimestamp(0,size=1,tz='Asia/Shanghai').hour[0]==8
    assert Pddt.utcfromtimestamp(0,size=1).is_utc()
    class Child(Pddt):pass
    x=Child(['2024-01-01','2024-01-02'])
    assert isinstance(x[:1],Child) and isinstance(x.to_month(1),Child)
    assert isinstance(x.as_unit('ns'),Child)
