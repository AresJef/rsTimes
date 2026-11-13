"""Explicit expectations for the approved parser boundary and precision rules."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import pytest
import rstimes
from rstimes import Configs, parse, parse_str, parse_to_epoch

@pytest.mark.parametrize('entry', [parse_str, parse])
@pytest.mark.parametrize('text', ['9999-W52-7','9999W527'])
@pytest.mark.parametrize('isoformat',[True,False])
def test_computed_year_is_owned_by_target(entry,text,isoformat):
    seen={}
    def target(**fields):
        seen.update(fields)
        return None
    assert entry(text,dtclass=target,isoformat=isoformat) is None
    assert (seen['year'],seen['month'],seen['day']) == (10000,1,2)
    with pytest.raises(ValueError):
        entry(text,isoformat=isoformat)

@pytest.mark.parametrize('isoformat',[True,False])
def test_epoch_does_not_apply_python_calendar_or_int64_bounds(isoformat):
    expected=((datetime(9999,12,31)-datetime(1970,1,1)).days+2)*86400*10**9
    assert parse_to_epoch('9999-W52-7','ns',isoformat=isoformat)==expected
    assert expected > 2**63
    assert parse_to_epoch('00-01-02','ns',default=date(9999,1,1),isoformat=isoformat)==expected

def test_old_epoch_name_is_removed():
    assert not hasattr(rstimes,'parse_epoch')
    import rstimes.parser as module
    assert not hasattr(module,'parse_epoch')

@pytest.mark.parametrize('offset,expected', [('+0599',21540),('+05:99',21540),('+2400',82800),('+9900',82800),('-0599',-21540),('-05:99',-21540)])
@pytest.mark.parametrize('isoformat',[True,False])
def test_offset_components_clip_without_carry(offset,expected,isoformat):
    text='2024-01-02 12:34'+offset
    result=parse_str(text,ignoretz=False,isoformat=isoformat)
    assert result.utcoffset()==timedelta(seconds=expected)
    with pytest.raises(ValueError,match='timezone'):
        parse_str(text,ignoretz=False,isoformat=isoformat,strict=True)
    assert parse_str(text,ignoretz=True,isoformat=isoformat,strict=True).tzinfo is None

@pytest.mark.parametrize('isoformat',[True,False])
@pytest.mark.parametrize('offset,expected',[('+05:30:45.123456',19845123456),('-00:00:30',-30000000),('-00:00:00.123456',-123456),('+05:30:99.123456',19859123456)])
def test_full_offset_seconds_and_microseconds(offset,expected,isoformat):
    text='2024-01-02 12:34:56'+offset
    result=parse_str(text,ignoretz=False,isoformat=isoformat)
    assert result.utcoffset()==timedelta(microseconds=expected)
    wall=parse_to_epoch('2024-01-02 12:34:56','us')
    assert parse_to_epoch(text,'us',isoformat=isoformat)==wall-expected
    if '99' in offset:
        with pytest.raises(ValueError,match='second'):
            parse_str(text,ignoretz=False,isoformat=isoformat,strict=True)

@pytest.mark.parametrize('text,expected', [('2023-366',datetime(2023,12,31)),('2024-999',datetime(2024,12,31)),('2024-W53-7',datetime(2024,12,29)),('2024W997',datetime(2024,12,29)),('2024-W01-9',datetime(2024,1,7)),('2020-W53-7',datetime(2021,1,3))])
@pytest.mark.parametrize('isoformat',[True,False])
def test_raw_iso_range_rules(text,expected,isoformat):
    assert parse_str(text,isoformat=isoformat)==expected
    if text!='2020-W53-7':
        with pytest.raises(ValueError):
            parse_str(text,isoformat=isoformat,strict=True)
    else:
        assert parse_str(text,isoformat=isoformat,strict=True)==expected

@pytest.mark.parametrize('text',['2024-000','2024-W00-1','2024-W01-0'])
@pytest.mark.parametrize('strict',[True,False])
@pytest.mark.parametrize('isoformat',[True,False])
def test_iso_lower_bounds_are_not_omission(text,strict,isoformat):
    with pytest.raises(ValueError):
        parse_str(text,strict=strict,isoformat=isoformat)

@pytest.mark.parametrize('clock,expected',[('1.999h',(1,59,56,400000)),('1.999m',(0,1,59,940000)),('01:01.999',(1,1,59,940000)),('1.001h',(1,0,3,600000))])
@pytest.mark.parametrize('strict',[True,False])
@pytest.mark.parametrize('isoformat',[True,False])
def test_fractional_clock_converts_before_final_precision(clock,expected,strict,isoformat):
    text='2024-01-02 '+clock
    result=parse_str(text,strict=strict,isoformat=isoformat)
    assert (result.hour,result.minute,result.second,result.microsecond)==expected
    assert parse_to_epoch(text,'ns',strict=strict,isoformat=isoformat)==parse_to_epoch(datetime(2024,1,2,*expected),'ns')

@pytest.mark.parametrize('strict',[True,False])
@pytest.mark.parametrize('fold',[0,1])
def test_parser_passes_regional_wall_time_to_target(strict,fold):
    cfg=Configs();cfg.add_tzone('America/New_York')
    default=datetime(2024,1,1,fold=fold)
    result=parse_str('2024-03-10 02:30 America/New_York',cfg=cfg,ignoretz=False,strict=strict,default=default)
    assert (result.hour,result.minute,result.fold)==(2,30,fold)
    assert result.tzinfo==ZoneInfo('America/New_York')
    expected=datetime(2024,3,10,2,30,tzinfo=ZoneInfo('America/New_York'),fold=fold)
    assert parse_to_epoch('2024-03-10 02:30 America/New_York','us',cfg=cfg,default=default,strict=strict)==int(expected.timestamp())*1000000

def test_text_default_stored_fold_is_kept_for_plain_datetime():
    assert parse_str('2024-01-02',default=datetime(2000,1,1,fold=1)).fold==1

@pytest.mark.parametrize('short,year',[('00',0),('99',-1)])
def test_computed_year_below_one_is_not_clipped_or_an_absent_sentinel(short,year):
    import numpy as np
    seen={}
    def target(**fields):
        seen.update(fields)
    assert parse_str(short+'-01-02',default=date(1,1,1),dtclass=target) is None
    assert seen['year']==year
    expected=int(np.datetime64(f'{year:05d}-01-02','D').astype('int64'))*86400000000
    assert parse_to_epoch(short+'-01-02','us',default=date(1,1,1))==expected
