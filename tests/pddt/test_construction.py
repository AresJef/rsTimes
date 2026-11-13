"""Construction compares values, precision and timezone, with explicit changes."""
import json
from pathlib import Path
from datetime import date, datetime
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt, Configs

@pytest.mark.parametrize('data',[
 [],[None,None],[pd.NaT],['2024-01-02'],['2024-01-02 12:34:56.123456'],
 ['2024-01-02 12:34:56.123456789'],['2024-01-02 12:34:56.123456000'],
 ['2024-01-02 12:34:56','2024-01-02 12:34:56.123456789'],
 [0,1,-1],[0.,1.5],[datetime(2024,1,2)],[date(2024,1,2)],
 ['2024-01-02T12:34:56+08:00'],
])
def test_default_follows_pandas3(data):
    if pd.__version__.split('.')[0]!='3':pytest.skip('reference environment only')
    # P05.2: bare numeric construction requires integral ticks, unlike pandas coercion.
    if data==[0.,1.5]:
        with pytest.raises(ValueError):Pddt(data)
        return
    result=Pddt(data);expected=pd.DatetimeIndex(data)
    assert result.unit==expected.unit
    assert str(result.tz)==str(expected.tz)
    np.testing.assert_array_equal(result.asi8,expected.asi8)

@pytest.mark.parametrize('unit',['s','ms','us','ns'])
def test_explicit_unit_parse_is_direct(unit):
    x=Pddt(['2024-01-02 12:34:56'],unit=unit)
    assert x.unit==unit
    assert x[0]==pd.Timestamp('2024-01-02 12:34:56')
    x=Pddt([0,1,-1],unit=unit)
    assert x.asi8.tolist()==[0,1,-1]

@pytest.mark.parametrize('unit',['s','ms','us'])
def test_lossy_constructor_is_rejected(unit):
    with pytest.raises(ValueError,match='precision|preserve|lossless|represent'):
        Pddt(['2024-01-02 12:34:56.123456789'],unit=unit)

@pytest.mark.parametrize('unit',['s','ms','us','ns'])
def test_typed_array_unit_conversion_preserves_instant(unit):
    source=np.array(['2024-01-02','NaT'],dtype='datetime64[s]')
    result=Pddt(source,unit=unit)
    assert result.unit==unit
    assert result[0]==pd.Timestamp('2024-01-02')
    assert pd.isna(result[1])

def test_cfg_is_not_bypassed_by_standard_parser():
    cfg=Configs();cfg.add_month('mymonth',2)
    result=Pddt(['29 mymonth 2024'],cfg=cfg)
    assert result[0]==pd.Timestamp('2024-02-29')

def test_readonly_buffer_owner_and_copy():
    data=np.array(['2024-01-02'],dtype='datetime64[us]')
    reused=Pddt(data,copy=False);copied=Pddt(data,copy=True)
    assert np.shares_memory(data,reused.asi8)
    assert not np.shares_memory(data,copied.asi8)

def test_mixed_timezones_require_explicit_utc():
    values=['2024-01-01T12:00+01:00','2024-07-01T12:00+02:00']
    with pytest.raises(ValueError,match='timezone|tz'):Pddt(values)
    result=Pddt(values,tz='UTC')
    assert result.hour.tolist()==[11,10]
    assert str(result.tz)=='UTC'

@pytest.mark.parametrize('unit',['ms','us','ns'])
def test_polars_unit_timezone_nulls_and_chunks(unit):
    pl=pytest.importorskip('polars')
    values=pl.concat([pl.Series('time',[0,None],dtype=pl.Datetime(unit,'Europe/Paris')),pl.Series('time',[1],dtype=pl.Datetime(unit,'Europe/Paris'))],rechunk=False)
    result=Pddt(values)
    assert result.unit==unit
    assert str(result.tz)=='Europe/Paris'
    assert result.asi8.tolist()==[0,np.iinfo(np.int64).min,1]

@pytest.mark.parametrize('data',[['2024-01-02'],np.array(['2024-01-02'],dtype='datetime64[us]')])
def test_constructor_rejects_unhashable_name(data):
    with pytest.raises(TypeError,match='hashable'):
        Pddt(data,name=[])

@pytest.mark.parametrize('unit',['ms','us','ns'])
@pytest.mark.parametrize('zone',[None,'Europe/Paris'])
@pytest.mark.parametrize('copy',[False,True])
def test_polars_without_nulls_keeps_unit_timezone_and_owner(unit,zone,copy):
    pl=pytest.importorskip('polars')
    data=pl.concat([pl.Series('time',[0],dtype=pl.Datetime(unit,zone)),
                    pl.Series('time',[1],dtype=pl.Datetime(unit,zone))],rechunk=False)
    result=Pddt(data,copy=copy)
    del data
    assert result.unit==unit and result.asi8.tolist()==[0,1]
    assert str(result.tz)==str(zone)
