"""Approved internal-query, sealed-class and snapshot contracts."""
import copy
import pickle
from datetime import datetime
import pytest
from rstimes import Configs, parse_str as parse

QUERIES=('is_jump','is_pertain','is_utc','is_tz','is_month','is_weekday','is_hms','is_ampm','get_tz_offset','get_month','get_weekday','get_hms','get_ampm')
NAMES=('jump','pertain','utc','tzoffset','month','weekday','hms','ampm')

def view(cfg):return cfg.yearfirst,cfg.dayfirst,tuple(getattr(cfg,n) for n in NAMES)

@pytest.mark.parametrize('name',QUERIES)
def test_queries_are_not_python_attributes(name):
    assert not hasattr(Configs,name)
    assert not hasattr(Configs(),name)

def test_configs_cannot_be_subclassed():
    with pytest.raises(TypeError):
        type('UserConfigs',(Configs,),{})

def test_normal_custom_rules_and_datetime_subclass_remain_supported():
    cfg=Configs();cfg.add_month('harvest',10)
    class Child(datetime):pass
    value=parse('14 harvest 2026',cfg=cfg,dtclass=Child)
    assert type(value) is Child and value==datetime(2026,10,14)

def test_state_is_versioned_and_independent():
    cfg=Configs();before=view(cfg);state=cfg.__reduce__()[2]
    assert state[:2]==('rstimes.Configs',2)
    state[4][4]['changed_snapshot']=12
    assert view(cfg)==before

@pytest.mark.parametrize('protocol',range(pickle.HIGHEST_PROTOCOL+1))
def test_new_pickle_roundtrip_and_original_sharing(protocol):
    cfg=Configs(False,True);cfg.add_month('harvest',10);alias=copy.copy(cfg)
    restored=pickle.loads(pickle.dumps(cfg,protocol=protocol))
    assert view(restored)==view(cfg)
    cfg.add_month('later',11)
    assert 'later' not in alias.month and 'later' not in restored.month
    assert parse('14 harvest 2026',cfg=restored)==datetime(2026,10,14)


def test_restore_detaches_inputs_and_rebuilds_case_variants():
    cfg=Configs(False,True);state=cfg.__reduce__()[2]
    state[4][4]['harvest']=10
    restored=Configs();restored.__setstate__(state)
    for word in ('harvest','HARVEST','Harvest'):
        assert parse('14 '+word+' 2026',cfg=restored)==datetime(2026,10,14)
    state[4][4]['harvest']=11
    assert restored.month['harvest']==10
    assert restored.yearfirst is False and restored.dayfirst is True

@pytest.mark.parametrize('kind',['layout','version','flags','namespace_type','token_type','value_type','value_range','conflict'])
def test_invalid_restore_leaves_complete_original_unchanged(kind):
    cfg=Configs(False,True);cfg.add_month('harvest',10);before=view(cfg)
    state=list(Configs(True,False).__reduce__()[2]);names=list(state[4])
    if kind=='layout':state=tuple([None]*19)
    elif kind=='version':state[1]=99
    elif kind=='flags':state[2]=1
    elif kind=='namespace_type':names[4]=[]
    elif kind=='token_type':names[4][None]=1
    elif kind=='value_type':names[4]['bad']=object()
    elif kind=='value_range':names[4]['bad']=13
    elif kind=='conflict':names[4]['mon']=1
    if kind!='layout':state[4]=tuple(names)
    with pytest.raises((TypeError,ValueError,OverflowError)):cfg.__setstate__(tuple(state))
    assert view(cfg)==before
    assert parse('14 harvest 2026',cfg=cfg)==datetime(2026,10,14)

@pytest.mark.parametrize('index,value',[(3,86401),(4,13),(5,7),(6,3),(7,2)])
def test_restore_validates_each_mapped_namespace_range(index,value):
    cfg=Configs();before=view(cfg);state=cfg.__reduce__()[2]
    state[4][index]['invalidstate']=value
    with pytest.raises(ValueError):cfg.__setstate__(state)
    assert view(cfg)==before

def test_deepcopy_and_snapshot_do_not_detach_shallow_copies():
    cfg=Configs();alias=copy.copy(cfg);deep=copy.deepcopy(cfg);state=cfg.__reduce__()[2]
    cfg.add_month('harvest',10)
    assert 'harvest' not in alias.month and 'harvest' not in deep.month
    assert 'harvest' not in state[4][4]
    cfg.set_month({'season':11})
    assert 'season' not in alias.month and 'harvest' not in alias.month

@pytest.mark.parametrize('operation',['clear_settings','reset_settings'])
def test_restored_rules_can_be_modified_normally(operation):
    cfg=pickle.loads(pickle.dumps(Configs(False,True)));cfg.add_month('harvest',10)
    assert getattr(cfg,operation)()
    assert 'harvest' not in cfg.month
    assert cfg.yearfirst is False and cfg.dayfirst is True

def test_custom_configuration_cannot_change_library_defaults():
    cfg=Configs();cfg.set_month({'October':1})
    assert parse('14 October 2026',cfg=cfg)==datetime(2026,1,14)
    assert parse('14 October 2026')==datetime(2026,10,14)


def test_old_parser2_pickle_is_rejected_explicitly():
    from pathlib import Path
    old=Path(__file__).with_name('data')/'configs-parser2.pkl'
    with pytest.raises(ValueError,match='legacy|format|version'):
        pickle.loads(old.read_bytes())

def test_unknown_huge_state_version_is_value_error():
    cfg=Configs();before=view(cfg);state=list(cfg.__reduce__()[2]);state[1]=10**100
    with pytest.raises(ValueError,match='version'):cfg.__setstate__(tuple(state))
    assert view(cfg)==before

@pytest.mark.parametrize('token',['école','custöm','wordhere'])
def test_pickle_restores_special_unicode_rules(token):
    cfg=Configs();cfg.add_jump(token)
    restored=pickle.loads(pickle.dumps(cfg))
    assert view(restored)==view(cfg)
    assert restored.del_jump(token.upper())
    assert token.lower() not in restored.jump
