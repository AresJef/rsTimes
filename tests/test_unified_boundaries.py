"""Period meaning, rounding direction and the exact approved Snap vocabulary."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import re
import pytest
from rstimes import Pydt

@pytest.mark.parametrize('method',['round','ceil','floor'])
def test_rounding_uses_freq_keyword_only(method):
    value=Pydt(2024,5,7,12,34,56,123456)
    assert getattr(value,method)(freq='s')==getattr(value,method)('s')
    with pytest.raises(TypeError):getattr(value,method)(unit='s')

@pytest.mark.parametrize('method',['is_first_of','is_last_of','is_start_of','is_end_of'])
@pytest.mark.parametrize('unit',['','unknown'])
def test_boundary_query_unknown_name_is_error(method,unit):
    with pytest.raises(ValueError):getattr(Pydt(2024,1,1),method)(unit)

@pytest.mark.parametrize('method',['is_first_of','is_last_of','is_start_of','is_end_of'])
@pytest.mark.parametrize('unit',[None,0,False])
def test_boundary_query_nonstring_is_type_error(method,unit):
    with pytest.raises(TypeError):getattr(Pydt(2024,1,1),method)(unit)

@pytest.mark.parametrize('unit',['Y','Q','M','W','D','h','m','s','ms','us','Monday','April'])
@pytest.mark.parametrize('end',[False,True])
def test_boundary_query_and_transform_share_meaning(unit,end):
    value=Pydt(2024,5,7,12,34,56,123456)
    transform=value.to_end_of if end else value.to_start_of
    query_name='is_end_of' if end else 'is_start_of'
    result=transform(unit)
    assert getattr(result,query_name)(unit) is True
    assert getattr(value,query_name)(unit) is (result==value)

@pytest.mark.parametrize('fold',[0,1])
def test_repeated_time_rounding_preserves_direction(fold):
    value=Pydt(2024,11,3,1,30,tzinfo='America/New_York',fold=fold)
    assert value.floor('h').timestamp()<=value.timestamp()
    assert value.ceil('h').timestamp()>=value.timestamp()
    assert value.floor('h').fold==fold


def test_half_hour_gap_keeps_frequency_alignment():
    zone=ZoneInfo('Australia/Lord_Howe')
    value=Pydt(2024,10,6,2,45,tzinfo=zone)
    result=value.floor('h')
    assert result.hour==1 and result.minute==0
    assert result.timestamp()<=value.timestamp()
    value=Pydt(2024,10,6,1,45,tzinfo=zone)
    result=value.ceil('h')
    assert result.hour==3 and result.minute==0
    assert result.timestamp()>=value.timestamp()


def test_midnight_gap_starts_at_first_existing_time_in_the_same_date():
    value=Pydt(2023,4,28,12,tzinfo='Africa/Cairo')
    result=value.to_start_of('D')
    assert (result.year,result.month,result.day,result.hour)==(2023,4,28,1)
    assert result.is_start_of('D') is True
    assert value.is_start_of('D') is False
    assert value.normalize()==result
    assert value.to_end_of('D').is_end_of('D') is True


def test_entire_missing_named_day_is_an_explicit_error():
    value=Pydt(2011,12,29,12,tzinfo='Pacific/Apia')
    with pytest.raises(ValueError,match='period has no existing'):
        value.to_start_of('Friday')

@pytest.mark.parametrize('unit,expected',[
    ('Y',datetime(2024,1,1)),('Q',datetime(2024,7,1)),('M',datetime(2024,6,1)),
    ('W',datetime(2024,6,3)),('D',datetime(2024,6,1)),('h',datetime(2024,6,1,10)),
    ('m',datetime(2024,6,1,10,21)),('min',datetime(2024,6,1,10,21)),
    ('s',datetime(2024,6,1,10,20,30)),('ms',datetime(2024,6,1,10,20,30,123000)),
    ('us',datetime(2024,6,1,10,20,30,123456)),
])
def test_all_snap_periods(unit,expected):
    value=Pydt(2024,6,1,10,20,30,123456)
    assert value.snap(unit)==expected


def test_snap_ties_go_later_while_round_ties_go_even():
    value=Pydt(2024,1,2,12,30)
    assert value.snap('h').hour==13
    assert value.round('h').hour==12
    assert Pydt(2024,1,2,0,0,0,500000).snap().second==1

@pytest.mark.parametrize('unit',['15min','hours','', 'unknown'])
def test_snap_rejects_unapproved_units(unit):
    with pytest.raises(ValueError):Pydt(2024,1,2).snap(unit)

@pytest.mark.parametrize('unit',[None,0,1.0])
def test_snap_unit_must_be_string(unit):
    with pytest.raises(TypeError):Pydt(2024,1,2).snap(unit)


def test_snap_preserves_child_type_without_probe_constructor_calls():
    class Child(Pydt):
        calls=0
        def __new__(cls,*args,**kwargs):
            cls.calls+=1
            return super().__new__(cls,*args,**kwargs)
    value=Child(2024,1,2,12,30,tzinfo='America/New_York')
    result=value.snap('h')
    assert type(result) is Child and result.hour==13
    assert Child.calls==2
    assert result.snap('h') is result


def test_snap_regional_effective_starts_and_missing_day_skip():
    value=Pydt(2024,10,6,2,40,tzinfo='Australia/Lord_Howe')
    assert (value.snap('h').hour,value.snap('h').minute)==(2,30)
    value=Pydt(2011,12,29,12,tzinfo='Pacific/Apia')
    result=value.snap('D')
    assert (result.year,result.month,result.day)==(2011,12,31)
    assert result.tzinfo is value.tzinfo


def test_snap_all_554_stored_names_use_the_frozen_vocabulary():
    # This fixture is the user-approved input list, independent of runtime Configs.
    text=(Path(__file__).with_name('data')/'snap_names.md').read_text().split('## 附录A', 1)[1]
    value=Pydt(2024,6,15,12)
    sections=[row.strip('|').split('|', 1) for row in text.splitlines() if row.startswith('|')]
    weekdays={'星期一':0,'星期二':1,'星期三':2,'星期四':3,'星期五':4,'星期六':5,'星期日':6}
    counted=0
    for section in sections:
        heading=section[0]
        names=re.findall(r'`([^`]+)`', section[1]) if len(section) == 2 else []
        if heading in weekdays:
            for name in names:
                result=value.snap(name)
                assert result.weekday()==weekdays[heading]
                assert result.hour==result.minute==result.second==result.microsecond==0
                assert abs(result-value)<=timedelta(days=4)
                counted+=1
        elif re.fullmatch(r'\d+月',heading):
            month=int(heading[:-1])
            for name in names:
                result=value.snap(name)
                assert result.month==month and result.day==1 and result.hour==0
                options=[datetime(year,month,1) for year in [2023,2024,2025]]
                expected=min(options,key=lambda candidate:(abs(candidate-value),-candidate.toordinal()))
                assert result==expected
                counted+=1
    assert counted==554


@pytest.mark.parametrize('fold',[0,1])
def test_snap_repeated_clock_boundary_uses_actual_distance(fold):
    value=Pydt(2024,11,3,1,10,tzinfo='America/New_York',fold=fold)
    result=value.snap('h')
    assert result.hour==1 and result.minute==0 and result.fold==fold
    assert value.timestamp()-result.timestamp()==600
    assert result.snap('h') is result


def test_snap_can_select_the_later_repeat_before_wall_clock_next_hour():
    value=Pydt(2024,11,3,1,50,tzinfo='America/New_York',fold=0)
    result=value.snap('h')
    assert (result.hour,result.minute,result.fold)==(1,0,1)
    assert result.timestamp()-value.timestamp()==600
