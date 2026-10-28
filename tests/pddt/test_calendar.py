"""Batch calendar behavior with independent Gregorian and pandas expectations."""
from datetime import datetime, timedelta
import warnings
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt

@pytest.mark.parametrize('unit',['s','ms','us','ns'])
@pytest.mark.parametrize('year,month,day',[(1900,2,28),(2000,2,29),(2023,1,31),(2024,12,31)])
def test_month_year_and_day_moves(unit,year,month,day):
    x=Pddt([f'{year:04}-{month:02}-{day:02} 12:34:56'],unit=unit)
    for months in [-13,-1,0,1,13]:
        expected=pd.Timestamp(year,month,day,12,34,56)+pd.DateOffset(months=months)
        assert x.to_month(months)[0]==expected
        assert x.add(months=months)[0]==expected
    assert x.to_day(3)[0]==pd.Timestamp(year,month,day,12,34,56)+pd.Timedelta(days=3)

@pytest.mark.parametrize('unit',['s','ms','us','ns'])
def test_clipped_absolute_fields_and_nat(unit):
    x=Pddt(['2024-01-31 12:34:56',None],unit=unit)
    # P11: invalid explicit fields are rejected; convenient selection still clamps month-end.
    with pytest.raises(ValueError):x.replace(month=2,hour=50,minute=99)
    with pytest.raises(ValueError):x.replace(month=2)
    y=x.to_date(month=2).to_time(hour=23,minute=59)
    assert y[0]==pd.Timestamp('2024-02-29 23:59:56')
    assert pd.isna(y[1])
    assert y.unit==unit

@pytest.mark.parametrize('period,first,last',[
 ('Y','2024-01-01','2024-12-31'),('Q','2024-04-01','2024-06-30'),
 ('M','2024-05-01','2024-05-31'),('W','2024-05-06','2024-05-12')])
def test_period_boundaries_keep_or_replace_clock(period,first,last):
    x=Pddt(['2024-05-08 12:34:56.123456789'])
    assert x.to_first_of(period)[0]==pd.Timestamp(first+' 12:34:56.123456789')
    assert x.to_last_of(period)[0]==pd.Timestamp(last+' 12:34:56.123456789')
    assert x.to_start_of(period)[0]==pd.Timestamp(first)
    assert x.to_end_of(period)[0]==pd.Timestamp(last+' 23:59:59.999999999')

@pytest.mark.parametrize('precision',[0,1,3,6,7,8,9,10])
def test_fractional_precision(precision):
    x=Pddt(['2024-01-02 12:34:56.123456789'])
    step=10**max(0,9-precision)
    assert x.fsp(precision).asi8[0]==x.asi8[0]//step*step

def test_nanosecond_boundary_is_checked_as_an_instant():
    x=Pddt(['2262-04-11 00:00:00.123456789'])
    result=x.add(nanoseconds=1)
    assert result.unit=='ns'
    assert result.asi8[0]==x.asi8[0]+1

def test_whole_array_downgrade_warns_only_if_precision_is_lost():
    x=Pddt(['2024-01-01 00:00:00.123456789','2262-01-01 00:00:00'])
    # P05.3: existing objects never automatically change unit.
    with pytest.raises(OverflowError):x.add(years=1)
    assert x.unit=='ns'
    result=x.as_unit('us').add(years=1)
    assert result.unit=='us' and result[0]==pd.Timestamp('2025-01-01 00:00:00.123456')
    with pytest.raises(OverflowError):Pddt(['2262-01-01'],unit='ns').add(years=1)

def test_microsecond_wide_year_does_not_use_python_datetime():
    x=Pddt(np.array(['12000-01-31'],dtype='datetime64[us]'))
    assert str(x.to_month(1)[0]).startswith('12000-02-29')

def test_dst_calendar_adjustment_requires_explicit_choice():
    x=Pddt(['2024-03-09 02:30'],tz='America/New_York')
    # P10/P11: automatic calendar operations and explicit strict replacement differ.
    assert x.to_day(1)[0]==pd.Timestamp('2024-03-10 03:30',tz='America/New_York')
    with pytest.raises(ValueError):x.replace(day=10)
    result=x.replace(day=10,nonexistent='shift_forward')
    assert result.hour[0]==3 and result.minute[0]==0

def test_strided_int_input_is_processed_safely():
    data=np.arange(12,dtype='i8').view('datetime64[D]')[::2]
    result=Pddt(data).to_day(1)
    assert result[0]==pd.Timestamp('1970-01-02')

@pytest.mark.parametrize('kind',['Y','Q','M','W','D','h','m','s','ms','us','ns'])
def test_diff_counts_boundaries_and_keeps_missing(kind):
    x=Pddt(['2024-01-02 00:00:00.000000001',None])
    y=Pddt(['2024-01-01 23:59:59.999999999',None])
    result=x.diff(y,kind)
    assert result[0]==(2 if kind=='ns' else 1 if kind not in ('Y','Q','M','W') else 0)
    assert pd.isna(result[1])

def test_diff_inclusive_and_checked_overflow():
    x=Pddt(['2024-01-01'])
    assert x.diff(x,'D',inclusive='both')[0]==1
    assert x.diff(x,'D',inclusive='neither')[0]==-1
    a=Pddt(np.array([np.iinfo('i8').max],dtype='i8').view('datetime64[us]'))
    b=Pddt(np.array([-np.iinfo('i8').max],dtype='i8').view('datetime64[us]'))
    with pytest.raises(OverflowError):a.diff(b,'us')

def test_calendar_cache_is_correct_for_shuffled_and_repeated_days():
    rng=np.random.default_rng(2718)
    ticks=np.datetime64('2024-01-28','ns').astype('i8')+rng.integers(0,8*86400000000000,size=128,dtype='i8')
    data=np.concatenate([ticks,np.sort(ticks)])
    x=Pddt(data.view('datetime64[ns]'))
    if not pd.__version__.startswith('2.3.'):
        pytest.skip('fixed official comparison environment')
    from cytimes import Pddt as Original
    y=Original(data.view('datetime64[ns]'))
    for action in [lambda z:z.add(months=1,days=2,microseconds=-3),lambda z:z.replace(month=2,day=28,hour=9),lambda z:z.to_end_of('M')]:
        np.testing.assert_array_equal(action(x).asi8,action(y).asi8)

def test_valid_nanosecond_lower_boundary_does_not_degrade_for_midnight_intermediate():
    source=np.array([np.iinfo('i8').min+1],dtype='i8').view('datetime64[ns]')
    x=Pddt(source)
    same=x.to_month(0)
    assert same.unit=='ns' and same.asi8[0]==x.asi8[0]
    later=x.to_time(hour=1)
    assert later.unit=='ns' and later[0].hour==1
