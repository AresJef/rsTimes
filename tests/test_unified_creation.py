"""Strict Pydt construction and automatic calendar-target selection."""
from datetime import date,datetime,time,timedelta,timezone,tzinfo
from zoneinfo import ZoneInfo
import pickle
import numpy as np
import pytest
from rstimes import Configs,Delta,Pydt,parse_str
from rstimes.pydt import _restore_pydt

NY=ZoneInfo('America/New_York')
GAP=datetime(2024,3,10,2,30,tzinfo=NY)
WALL=(datetime(2024,3,10,2,30)-datetime(1970,1,1)).total_seconds()

@pytest.mark.parametrize('fold',[0,1])
@pytest.mark.parametrize('class_name',['base','child'])
def test_explicit_missing_time_rejected_for_both_folds(fold,class_name):
    class Child(Pydt):
        pass
    cls=Pydt if class_name=='base' else Child
    with pytest.raises(ValueError,match='does not exist'):
        cls(2024,3,10,2,30,tzinfo=NY,fold=fold)

@pytest.mark.parametrize('factory',[
    lambda:Pydt.fromdatetime(GAP),
    lambda:Pydt.combine(date(2024,3,10),time(2,30),tz=NY),
    lambda:Pydt.fromseconds(WALL,tz=NY),
    lambda:Pydt.frommicroseconds(int(WALL*1000000),tz=NY),
    lambda:Pydt.fromdatetime64(np.datetime64('2024-03-10T02:30'),tz=NY),
    lambda:Pydt(2024,3,10,1,30,tzinfo=NY).replace(hour=2),
    lambda:Pydt(2024,3,10,1,30,tzinfo=NY).__replace__(hour=2),
    lambda:Pydt(2024,3,10,2,30).tz_localize(NY),
    lambda:_restore_pydt(Pydt,1,(2024,3,10,2,30,0,0),NY,0),
])
def test_all_explicit_factory_paths_share_strict_rule(factory):
    with pytest.raises(ValueError,match='does not exist'):
        factory()

@pytest.mark.parametrize('strict',[True,False])
def test_parser_target_owns_the_existence_rule(strict):
    cfg=Configs();cfg.add_tzone('America/New_York')
    text='2024-03-10 02:30 America/New_York'
    assert parse_str(text,cfg=cfg,ignoretz=False,strict=strict).hour==2
    with pytest.raises(ValueError,match='does not exist'):
        parse_str(text,cfg=cfg,ignoretz=False,strict=strict,dtclass=Pydt)
    with pytest.raises(ValueError,match='does not exist'):
        Pydt.parse(text,cfg=cfg,ignoretz=False,strict=strict)

@pytest.mark.parametrize('fold',[0,1])
def test_fold_only_selects_repeated_time(fold):
    result=Pydt(2024,11,3,1,30,tzinfo=NY,fold=fold)
    assert result.fold==fold
    assert result.utcoffset()==timedelta(hours=-4-fold)
    assert pickle.loads(pickle.dumps(result))==result
    assert pickle.loads(pickle.dumps(result)).fold==fold

@pytest.mark.parametrize('zone',[None,timezone.utc,timezone(timedelta(hours=8))])
def test_ordinary_zones_keep_all_local_clock_values(zone):
    result=Pydt(2024,3,10,2,30,tzinfo=zone)
    assert (result.hour,result.minute,result.tzinfo)==(2,30,zone)
    assert result.replace(minute=None) is result
    assert result.to_time(hour=0).hour==0


def test_custom_timezone_constructor_is_not_needlessly_probed():
    class Custom(tzinfo):
        def utcoffset(self,value):
            raise AssertionError('not needed for constructing a date')
    zone=Custom()
    assert Pydt(2024,1,2,tzinfo=zone).tzinfo is zone

@pytest.mark.parametrize('name,zone',[('Asia/Shanghai',ZoneInfo('Asia/Shanghai')),('UTC',timezone.utc)])
def test_replace_timezone_names_and_none(name,zone):
    result=Pydt(2024,1,2,12,fold=1).replace(tzinfo=name,fold=None)
    assert result.tzinfo==zone
    assert (result.hour,result.fold)==(12,1)
    assert result.replace(tzinfo=None).tzinfo is None

@pytest.mark.parametrize('fold',[0,1])
def test_instant_factories_preserve_the_actual_occurrence(fold):
    expected=datetime(2024,11,3,1,30,tzinfo=NY,fold=fold)
    result=Pydt.fromtimestamp(expected.timestamp(),tz=NY)
    assert (result.hour,result.minute,result.fold)==(1,30,fold)
    assert result.timestamp()==expected.timestamp()
    converted=Pydt.fromdatetime(expected.astimezone(timezone.utc)).tz_convert(NY)
    assert converted.timestamp()==expected.timestamp()
    assert converted.fold==fold

@pytest.mark.parametrize('start,operation,expected',[
    ((2024,3,9,2,30),lambda x:x.add(days=1),(2024,3,10,3,30)),
    ((2024,3,11,2,30),lambda x:x.sub(days=1),(2024,3,10,1,30)),
    ((2024,11,2,1,30),lambda x:x.to_tomorrow(),(2024,11,3,1,30)),
    ((2024,11,4,1,30),lambda x:x.to_yesterday(),(2024,11,3,1,30)),
])
def test_calendar_targets_are_selected_before_strict_construction(start,operation,expected):
    source=Pydt(*start,tzinfo=NY)
    result=operation(source)
    assert (result.year,result.month,result.day,result.hour,result.minute)==expected
    if result.month==11:
        assert result.utcoffset()==source.utcoffset()

@pytest.mark.parametrize('cls_kind',['base','child'])
def test_delta_calendar_paths_select_valid_target_before_public_construction(cls_kind):
    class Child(Pydt):
        def __new__(cls,**fields):
            return super().__new__(cls,**fields)
    cls=Pydt if cls_kind=='base' else Child
    value=cls(year=2024,month=3,day=9,hour=2,minute=30,tzinfo=NY)
    result=value+Delta(days=1)
    assert type(result) is cls
    assert (result.day,result.hour,result.minute)==(10,3,30)

@pytest.mark.parametrize('factory',[
    lambda:Pydt.fromdate(date(2019,9,8),tz='America/Santiago'),
    lambda:Pydt.fromordinal(date(2019,9,8).toordinal(),tz='America/Santiago'),
    lambda:Pydt.fromdayofyear(2019,251,tz='America/Santiago'),
    lambda:Pydt.fromisocalendar(2019,36,7,tz='America/Santiago'),
])
def test_midnight_factories_also_share_strict_creation(factory):
    with pytest.raises(ValueError,match='does not exist'):
        factory()


def test_arbitrary_zoneinfo_file_key_does_not_bypass_regional_validation():
    from pathlib import Path
    from zoneinfo import TZPATH
    path=next((Path(root)/'America/New_York' for root in TZPATH if (Path(root)/'America/New_York').is_file()),None)
    if path is None:pytest.skip('system tzdata file unavailable')
    with path.open('rb') as stream:zone=ZoneInfo.from_file(stream,key='UTC')
    with pytest.raises(ValueError,match='does not exist'):
        Pydt(2024,3,10,2,30,tzinfo=zone)


def test_valid_custom_calendar_target_does_not_read_unused_source_offset():
    calls=[]
    class Custom(tzinfo):
        def utcoffset(self,value):
            calls.append(value.day)
            return timedelta(hours=2)
        def dst(self,value):
            return timedelta(0)
    value=Pydt(2024,5,7,15,30,tzinfo=Custom())
    result=value.to_day(1)
    assert (result.year,result.month,result.day,result.hour,result.minute)==(2024,5,8,15,30)
    assert calls and 7 not in calls
