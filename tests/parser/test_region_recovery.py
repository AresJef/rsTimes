"""Region integration contracts with independent clock and integer expectations."""
import copy
import json
import pickle
import warnings
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import pytest
from rstimes import Configs, Pddt, Pydt, parse, parse_str, parse_to_epoch

ROOT=next(parent for parent in Path(__file__).resolve().parents if (parent/"Cargo.toml").is_file())
INPUTS=json.loads((Path(__file__).with_name('data')/'region_inputs.json').read_text(encoding='utf-8'))['rows']

@pytest.mark.parametrize('row',INPUTS,ids=lambda x:x['id'])
@pytest.mark.parametrize('fn',[parse_str,parse])
def test_fixed_region_and_strict_expectations(row,fn):
    cfg=Configs();cfg.set_tzone(set(row['regions']))
    kw=dict(row['kwargs'],cfg=cfg)
    if row['default'] is not None:
        v=row['default'];kw['default']=datetime(*v[:7],fold=v[7])
    out=fn(row['text'],**kw);offset=out.utcoffset()
    actual=dict(fields=[getattr(out,k) for k in ('year','month','day','hour','minute','second','microsecond')],fold=out.fold,zone_key=getattr(out.tzinfo,'key',None),offset_seconds=None if offset is None else int(offset.total_seconds()))
    expected=dict(row['expected'])
    if row['id']=='Z07': expected.update(fields=[2024,3,10,2,30,0,0],fold=0,offset_seconds=-18000)
    if row['id']=='Z08': expected.update(fields=[2024,10,6,2,15,0,0],fold=0,offset_seconds=37800)
    assert actual==expected

@pytest.mark.parametrize('fold',[0,1])
@pytest.mark.parametrize('zone,text,hour',[('America/New_York','2024-11-03 01:30:00.123456789',1),('Australia/Lord_Howe','2024-04-07 01:45:00.123456789',1)])
def test_fold_and_nanos_are_shared_with_epoch(zone,text,hour,fold):
    cfg=Configs();cfg.add_tzone(zone);default=datetime(2024,1,1,fold=fold)
    local=datetime.fromisoformat(text[:26]).replace(tzinfo=ZoneInfo(zone),fold=fold)
    utc=local.astimezone(timezone.utc);delta=utc.replace(tzinfo=None)-datetime(1970,1,1)
    expected=((delta.days*86400+delta.seconds)*1000000+delta.microseconds)*1000+789
    assert parse_to_epoch(text+' '+zone,'ns',cfg=cfg,default=default,strict=True)==expected
    assert parse_str(text+' '+zone,cfg=cfg,ignoretz=False,default=default,strict=True).fold==fold

@pytest.mark.parametrize('zone,text,forward,backward',[('America/New_York','2024-03-10 02:30',(3,30),(1,30)),('Australia/Lord_Howe','2024-10-06 02:15',(2,45),(1,45))])
def test_gap_resolution_and_strict_error(zone,text,forward,backward):
 cfg=Configs();cfg.add_tzone(zone)
 fields=datetime.fromisoformat(text)
 for strict in (False,True):
  for default in (None,datetime(2024,1,1,fold=0),datetime(2024,1,1,fold=1)):
   out=parse_str(text+' '+zone,cfg=cfg,ignoretz=False,default=default,strict=strict)
   assert out.replace(tzinfo=None)==fields
   assert out.fold==(default.fold if default is not None else 0)
   with pytest.raises(ValueError,match='exist'):
    parse_str(text+' '+zone,cfg=cfg,ignoretz=False,default=default,strict=strict,dtclass=Pydt)

@pytest.mark.parametrize('default',[None,date(2024,1,1)])
def test_repeated_time_requests_datetime_default(default):
 cfg=Configs();cfg.add_tzone('America/New_York')
 out=parse_str('2024-11-03 01:30 America/New_York',cfg=cfg,ignoretz=False,strict=True,default=default)
 assert out.fold==0 and out.utcoffset()==timedelta(hours=-4)

@pytest.mark.parametrize('fn',[parse_str,parse])
def test_constructor_called_once_with_resolved_fields(fn):
    cfg=Configs();cfg.add_tzone('Asia/Shanghai');calls=[]
    class Child(datetime):pass
    def factory(**kwargs):calls.append(kwargs);cfg.set_tzone(None);return Child(**kwargs)
    out=fn('2024-01-02 12:00 Asia/Shanghai',cfg=cfg,ignoretz=False,dtclass=factory)
    assert type(out) is Child and out.utcoffset()==timedelta(hours=8) and len(calls)==1
    assert not cfg.tzone


def test_region_precedes_offset_and_ignored_region_requires_no_registration():
    cfg=Configs();cfg.add_tzone('Asia/Shanghai')
    assert parse_str('2024-01-02 12:00+01:00 [Asia/Shanghai]',cfg=cfg,ignoretz=False).utcoffset()==timedelta(hours=8)
    assert parse_str('2024-01-02 12:00 Asia/Shanghai')==datetime(2024,1,2,12)
    with pytest.raises(Exception,match='register'):parse_str('2024-01-02 12:00 Asia/Shanghai',ignoretz=False)

@pytest.mark.parametrize('protocol',range(pickle.HIGHEST_PROTOCOL+1))
def test_region_snapshot_roundtrips_independent(protocol):
    cfg=Configs();cfg.add_tzone('Asia/Shanghai');cfg.add_month('harvest',10)
    clone=pickle.loads(pickle.dumps(cfg,protocol=protocol));cfg.del_tzone('Asia/Shanghai')
    assert clone.tzone=={'Asia/Shanghai'} and clone.month['harvest']==10
    snap=clone.__reduce__()[2];snap[5].clear();assert clone.tzone=={'Asia/Shanghai'}


def test_current_v1_snapshot_is_read_without_regions():
    cfg=Configs();cfg.add_month('harvest',10);state=cfg.__reduce__()[2]
    target=Configs();target.add_tzone('Asia/Shanghai');target.__setstate__((state[0],1,*state[2:5]))
    assert target.month['harvest']==10 and not target.tzone


def test_restore_unavailable_zone_warns_and_warning_error_is_atomic(monkeypatch):
    import zoneinfo
    cfg=Configs();cfg.add_month('harvest',10);original=cfg.month
    state=list(Configs().__reduce__()[2]);state[5]={'Asia/Shanghai'}
    def unavailable(key):raise ZoneInfoNotFoundError(key)
    monkeypatch.setattr(zoneinfo,'ZoneInfo',unavailable)
    with warnings.catch_warnings():
        warnings.simplefilter('error',RuntimeWarning)
        with pytest.raises(RuntimeWarning):cfg.__setstate__(tuple(state))
    assert cfg.month==original and not cfg.tzone
    with pytest.warns(RuntimeWarning,match='unavailable'):cfg.__setstate__(tuple(state))
    assert cfg.tzone=={'Asia/Shanghai'}
    with pytest.raises(Exception,match='unavailable'):parse_str('2024-01-02 Asia/Shanghai',cfg=cfg,ignoretz=False)


def test_shared_pydt_pddt_region_and_nano_results():
    cfg=Configs();cfg.add_tzone('Asia/Shanghai');text='2024-01-02 12:00:00.123456789 Asia/Shanghai'
    assert Pydt.parse(text,cfg=cfg,ignoretz=False).tzinfo.key=='Asia/Shanghai'
    out=Pddt([text],cfg=cfg,unit='ns')
    assert out.asi8[0]==1704168000123456789 and str(out.tz)=='Asia/Shanghai'
    assert out[0].nanosecond==789


def test_pddt_region_localization_uses_explicit_array_policy():
 cfg=Configs();cfg.add_tzone('America/New_York')
 # P10: Parser yields local fields; the array selects its actual candidate.
 out=Pddt(['2024-11-03 01:30 America/New_York'],cfg=cfg,strict=True,ambiguous=False)
 assert out.hour[0]==1 and out[0].fold==1
 with pytest.raises(ValueError):
  Pddt(['2024-11-03 01:30 America/New_York'],cfg=cfg)


def test_only_new_public_config_names_exist():
    cfg=Configs()
    for namespace in ('jump','pertain','utc','month','weekday','hms','ampm','tzoffset','tzone'):
        for verb in ('add','del','set'):assert hasattr(cfg,verb+'_'+namespace)
    assert not hasattr(cfg,'tz')
    assert not any(hasattr(cfg,verb+'_'+n) for verb in ('remove','replace') for n in ('month','tz'))


@pytest.mark.parametrize("text", ["2024-05-07", "20240507", "2024-060", "2024-W09-4",
    "2024-05-07T12:34:56.123456789", "2024-05-07T12:34+05:30", "2024-05-07 12:99",
    "May 7, 2024 3:30 pm", "2024-05-07 at 15:30", "0001-01-01", "9999-12-31"])
def test_complete_iso_epoch_matches_shared_configured_route(text):
    # An explicit default configuration keeps this route on the shared scanner.
    assert parse_to_epoch(text, "ns") == parse_to_epoch(text, "ns", cfg=Configs())


def test_epoch_explicit_sort_callback_is_not_skipped_by_iso_shortcut():
    calls = []
    class Order:
        def __bool__(self):calls.append("year"); return True
    with pytest.raises(TypeError):
        parse_to_epoch("1970-01-01", "ns", yearfirst=Order())
    assert calls == []
