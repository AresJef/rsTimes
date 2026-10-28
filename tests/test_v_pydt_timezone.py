"""Finite boundary selection and actual current timezone/DST protocols."""
from datetime import datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo
import pytest
import pandas as pd
import numpy as np
from rstimes import Pydt

@pytest.mark.parametrize('zone,source,unit,expected', [
 ('Africa/Monrovia',(1972,1,6,23,59,59),'min',(1972,1,7,0,44,30)),
 ('America/St_Johns',(1988,4,3,0,0,59),'h',(1988,4,3,2,1,0)),
])
def test_snap_includes_the_first_existing_part_of_a_period(zone, source, unit, expected):
    value=Pydt(*source,tzinfo=zone)
    result=value.snap(unit)
    assert (result.year,result.month,result.day,result.hour,result.minute,result.second)==expected
    assert result.tzinfo is value.tzinfo

@pytest.mark.parametrize('entry,arg', [
 ('to_start_of','D'),('to_end_of','D'),('is_start_of','D'),('is_end_of','D'),
 ('to_first_of','M'),('to_last_of','M'),('round','h'),('ceil','h'),('floor','h'),('snap','h'),
])
@pytest.mark.parametrize('year',[1,2024,9999])
def test_unmodified_zoneinfo_child_shares_standard_boundary_rules(entry,arg,year):
    class Region(ZoneInfo):
        pass
    plain=Pydt(year,3,5,12,34,56,tzinfo=ZoneInfo('Asia/Shanghai'))
    child=Pydt(year,3,5,12,34,56,tzinfo=Region('Asia/Shanghai'))
    left=getattr(plain,entry)(arg)
    right=getattr(child,entry)(arg)
    if type(left) is bool:
        assert left is right
    else:
        assert left.replace(tzinfo=None)==right.replace(tzinfo=None)
        assert right.tzinfo is child.tzinfo

@pytest.mark.parametrize('dynamic',[False,True])
def test_current_instance_and_dynamic_fromutc_are_not_skipped(dynamic):
    error=RuntimeError('fromutc callback failed')
    calls=[]
    def fail(value):
        calls.append(1)
        raise error
    if dynamic:
        class Region(ZoneInfo):
            def __getattribute__(self,name):
                if name=='fromutc':
                    return fail
                return super().__getattribute__(name)
    else:
        class Region(ZoneInfo):
            pass
    region=Region.no_cache('Asia/Shanghai')
    if not dynamic:
        region.fromutc=fail
    with pytest.raises(RuntimeError) as caught:
        Pydt(2024,1,2,tzinfo=region)
    assert caught.value is error and calls==[1]


def test_zoneinfo_instance_update_remains_observable():
    class Region(ZoneInfo):
        pass
    region=Region.no_cache('Asia/Shanghai')
    value=Pydt(2024,1,2,12,tzinfo=region)
    error=ValueError('updated fromutc')
    def fail(value):
        raise error
    region.fromutc=fail
    with pytest.raises(ValueError) as caught:
        value.to_start_of('D')
    assert caught.value is error

class Zone(tzinfo):
    def __init__(self,adjustment):
        self.adjustment=adjustment
        self.calls=0
    def utcoffset(self,value):
        return timedelta(hours=1)
    def dst(self,value):
        self.calls+=1
        return self.adjustment

class FalseDuration(timedelta):
    def __bool__(self):
        raise AssertionError('DST flags must read the duration, not bool')

@pytest.mark.parametrize('adjustment,flag',[
 (None,-1),(timedelta(0),0),(timedelta(hours=1),1),(timedelta(hours=-1),1),
 (FalseDuration(0),0),(FalseDuration(hours=1),1),
 (pd.Timedelta(1,'ns'),1),(pd.Timedelta(-1,'ns'),1),
])
@pytest.mark.parametrize('entry',['is_dst','dst','timedict','timetuple'])
def test_dst_uses_actual_duration_and_one_callback(adjustment,flag,entry):
    zone=Zone(adjustment)
    value=Pydt(2024,1,2,tzinfo=zone)
    zone.calls=0
    result=getattr(value,entry)()
    assert zone.calls==1
    if entry=='is_dst':
        assert result is (flag==1)
    elif entry=='dst':
        assert result is adjustment
    else:
        assert (result['tm_isdst'] if entry=='timedict' else result.tm_isdst)==flag

@pytest.mark.parametrize('adjustment',[
 timedelta(hours=24),timedelta(hours=-24),
 pd.Timedelta(np.timedelta64(86_400_000_000_000,'s')),
 pd.Timedelta(np.timedelta64(-86_400_000_000_000,'s')),
])
@pytest.mark.parametrize('entry',['is_dst','dst','timedict','timetuple'])
def test_dst_rejects_actual_out_of_range_duration(adjustment,entry):
    zone=Zone(adjustment)
    value=Pydt(2024,1,2,tzinfo=zone)
    zone.calls=0
    with pytest.raises(ValueError,match='dst.*24'):
        getattr(value,entry)()
    assert zone.calls==1


def test_utc_calendar_dictionary_does_not_consume_dst():
    zone=Zone(timedelta(hours=24))
    value=Pydt(2024,1,2,tzinfo=zone)
    zone.calls=0
    assert value.utctimedict()['tm_isdst']==0 and zone.calls==0


def test_zoneinfo_child_at_the_first_supported_day():
    class Region(ZoneInfo):
        pass
    value=Pydt(1,1,1,12,tzinfo=Region('Asia/Shanghai'))
    assert value.to_start_of('D').hour==0
    assert value.is_start_of('D') is False
