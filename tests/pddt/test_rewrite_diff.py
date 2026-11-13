from datetime import date,datetime,timedelta,timezone
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt,Pydt

@pytest.mark.parametrize('target',[1,np.int64(1),1.0,np.float32(1),[1],(1,),iter([1]),np.array([1]),pd.Series([1]),pd.Index([1]),pd.array([1],dtype='Int64')])
def test_numeric_targets_always_mean_seconds(target):
    result=Pddt([np.datetime64(2,'s')]).diff(target,'s')
    assert result.tolist()==[1] and str(result.dtype)=='int64' and result.name=='diff'

@pytest.mark.parametrize('target',[1e-9,[1e-9],np.array([1e-9]),pd.array([1e-9],dtype='Float64')])
def test_numeric_fraction_preserves_ns_before_diff(target):
    assert Pddt([np.datetime64(1,'ns')]).diff(target,'ns').tolist()==[0]

@pytest.mark.parametrize('unit',['Y','Q','M','W','D','h','m','min','s','ms','us'])
@pytest.mark.parametrize('tz',[None,timezone(timedelta(hours=8))])
def test_boundary_semantics_match_current_pydt(unit,tz):
    left=Pydt(2024,3,1,1,2,3,456789,tzinfo=tz)
    right=Pydt(2023,12,31,23,59,59,123456,tzinfo=tz)
    x=Pddt([left,None])
    for inclusive in ['one','both','neither']:
        for absolute in [False,True]:
            result=x.diff(right,unit,absolute,inclusive)
            assert result[0]==left.diff(right,unit,absolute,inclusive)
            assert pd.isna(result[1]) and str(result.dtype)=='Int64'


def test_negative_epoch_uses_floor_and_weeks_start_on_monday():
    x=Pddt([np.datetime64(-1,'ns')])
    for unit in ['s','ms','us','D','h','min']:
        assert x.diff(0,unit).tolist()==[-1]
    week=Pddt(['1970-01-04','1970-01-05'])
    assert week.diff('1969-12-29','W').tolist()==[0,1]


def test_current_left_unit_does_not_drop_finer_right_precision():
    x=Pddt([np.datetime64(1,'s')])
    assert x.diff(np.datetime64(1_000_000_001,'ns'),'ns').tolist()==[-1]
    assert x.diff('1970-01-01 00:00:01.000000001','ns').tolist()==[-1]
    assert x.unit=='s'


def test_full_int64_range_and_separate_missing_mask():
    minimum=np.iinfo('int64').min
    x=Pddt(np.array([minimum+1,minimum],dtype='int64').view('datetime64[ns]'))
    result=x.diff(np.datetime64(1,'ns'),'ns')
    assert result[0]==minimum and pd.isna(result[1]) and str(result.dtype)=='Int64'
    clean=x[:1].diff(np.datetime64(1,'ns'),'ns')
    assert clean.tolist()==[minimum] and str(clean.dtype)=='int64'
    with pytest.raises(OverflowError):x.diff(np.datetime64(2,'ns'),'ns')
    with pytest.raises(OverflowError):x.diff(np.datetime64(1,'ns'),'ns',absolute=True)


def test_wide_year_buckets_and_zero_year_are_native():
    x=Pddt(['0000-01-01','0001-01-01'])
    assert x.diff('0000-01-01','Y').tolist()==[0,1]
    x=Pddt(np.array(['3000000000-01-01'],dtype='datetime64[s]'))
    assert x.diff(0,'Y').tolist()==[3000000000-1970]


def test_aware_targets_use_utc_boundaries_and_different_display_regions():
    x=Pddt(['2024-01-01 00:00:00.000000001'],tz='Asia/Shanghai')
    rhs=pd.DatetimeIndex(['2023-12-31 16:00:00.000000001'],tz='UTC')
    assert x.diff(rhs,'ns').tolist()==[0]
    assert x.diff(rhs[0],'Y').tolist()==[0]
    for target in [0,[0],np.array([0]),'2024-01-01']:
        with pytest.raises(TypeError,match='naive.*aware'):x.diff(target,'s')
    with pytest.raises(TypeError):Pddt([None]).diff(rhs,'s')


@pytest.mark.parametrize('target',[None,float('nan'),pd.NA,pd.NaT,np.datetime64('NaT','ns')])
def test_missing_scalar_propagates(target):
    assert Pddt(['2024-01-01']).diff(target,'s').isna().all()


@pytest.mark.parametrize('target',[True,np.bool_(False),[True],1j,b'2024',bytearray(b'2024'),timedelta(1)])
def test_invalid_targets_are_not_silent_numeric_or_date_values(target):
    with pytest.raises(TypeError):Pddt(['2024-01-01']).diff(target,'s')


def test_shape_empty_validation_and_no_silent_bad_text():
    x=Pddt(['2024-01-01',None])
    with pytest.raises(ValueError):x.diff(['2024-01-01'],'s')
    with pytest.raises(ValueError):x.diff(np.array([['2024-01-01']]),'s')
    with pytest.raises(ValueError):x.diff(['2024-01-01','not-a-date'],'s')
    with pytest.raises(ValueError):Pddt([]).diff(0,'unknown')
    with pytest.raises(TypeError):Pddt([]).diff(True,'s')
    assert Pddt([]).diff([],'ns').empty


def test_scalar_index_protocol_is_read_once_and_no_child_is_constructed():
    calls=[]
    class Number:
        def __index__(self):calls.append(1);return 1
    class Child(Pddt):
        def __new__(cls,*args,**kwargs):calls.append('construct');return super().__new__(cls,*args,**kwargs)
    x=Child([np.datetime64(2,'s'),np.datetime64(3,'s')]);calls.clear()
    assert x.diff(Number(),'s').tolist()==[1,2]
    assert calls==[1]


def test_polars_columns_keep_ns_and_dates_with_positional_matching():
    pl=pytest.importorskip('polars')
    x=Pddt(['1970-01-01 00:00:00.000000001',None])
    ns=pl.Series([1,None],dtype=pl.Datetime('ns'))
    assert x.diff(ns,'ns').tolist()[0]==0
    assert pd.isna(x.diff(ns,'ns')[1])
    assert Pddt(['2024-01-02']).diff(pl.Series([date(2024,1,1)],dtype=pl.Date),'D').tolist()==[1]
