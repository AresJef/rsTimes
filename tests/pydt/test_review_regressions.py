"""Regressions for observed native-field and subclass protocol mistakes."""
from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo
import pytest
from cytimes import Pydt as Original
from rstimes import Pydt

@pytest.mark.parametrize('name', ['is_first_of', 'is_last_of', 'is_start_of', 'is_end_of'])
@pytest.mark.parametrize('unit', [None, '', 'invalid', 'Y', 'Q', 'M', 'W', 'D', 'h', 'min', 's', 'ms', 'us', 'ns', 'December', 'Mon'])
@pytest.mark.parametrize('fields', [(9999,12,31,23,59,59,999999),(1,1,1,0,0,0,0),(2024,3,1,0,0,0,0)])
def test_predicates_read_fields_only(name, unit, fields):
    if unit is None:
        for cls in (Pydt,Original):
            with pytest.raises(TypeError): getattr(cls(*fields),name)(unit)
    elif unit in ('', 'invalid') or name in ('is_first_of', 'is_last_of') and unit not in ('Y', 'Q', 'M', 'W', 'December'):
        with pytest.raises(ValueError): getattr(Pydt(*fields), name)(unit)
    else:
        assert getattr(Pydt(*fields), name)(unit) is getattr(Original(*fields), name)(unit)

def test_predicates_do_not_call_child_constructor_or_timezone():
    class Broken(tzinfo):
        def utcoffset(self, dt): raise AssertionError('no timezone callback')
    class Child(Pydt):
        calls=0
        def __new__(cls,*args,**kwargs):
            cls.calls+=1
            return super().__new__(cls,*args,**kwargs)
    value=Child(2024,1,1,tzinfo=Broken())
    for name in ['is_first_of','is_last_of']:
        getattr(value,name)('M')
    for name in ['is_start_of','is_end_of']:
        with pytest.raises(AssertionError, match='no timezone callback'):
            getattr(value,name)('M')
    assert Child.calls==1

def test_custom_timezone_carrier_bypasses_child_constructor():
    class Fixed(tzinfo):
        def utcoffset(self,dt): return timedelta(hours=2)
        def dst(self,dt): return timedelta(0)
    class Child(Pydt):
        def __new__(cls,year,month,day,hour=0,*args,**kwargs):
            if hour==8: raise ValueError('UTC intermediate must not call this')
            return super().__new__(cls,year,month,day,hour,*args,**kwargs)
    p=Child(2024,5,7,10,tzinfo=Fixed())
    result=p.to_day(1)
    assert type(result) is Child and (result.day,result.hour)==(8,10)

@pytest.mark.parametrize('value',[2.9,object()])
def test_object_selectors_keep_int_or_name_contract(value):
    p=Pydt(2024,5,7)
    with pytest.raises(TypeError): p.to_year(0,month=value)
    with pytest.raises(TypeError): p.to_weekday(0,weekday=value)
    with pytest.raises(TypeError): p.to_quarter(0,month=value)

def test_public_error_boundaries():
    p=Pydt(2024,1,1)
    with pytest.raises(ValueError) as info: p.diff('not a date','D')
    assert info.value.__cause__ is None
    for method in (p.month_name,p.weekday_name):
        with pytest.raises(ValueError) as info: method('not-a-real-locale')
        assert info.value.__cause__ is None

def test_fast_conversion_same_timezone_keeps_fold_and_identity():
    p=Pydt(2024,1,1,tzinfo=timezone.utc,fold=1)
    assert p.tz_convert(timezone.utc) is p and p.fold==1
    zone=ZoneInfo('America/New_York')
    q=Pydt(2024,11,3,1,30,tzinfo=zone,fold=1)
    assert q.tz_convert(zone) is q
    assert q.tz_convert('UTC').timestamp()==q.timestamp()
