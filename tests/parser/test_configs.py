"""Configs namespace and state contracts against the frozen cyTimes reference."""
import copy
import pickle

import pytest
from cytimes.parser import Configs as ReferenceConfigs
from rstimes.parser import Configs

NAMES = ('jump', 'pertain', 'utc', 'tzoffset', 'month', 'weekday', 'hms', 'ampm')
from approved_behavior import ExpectedConfigs as ReferenceConfigs


def snapshot(cfg):
    return cfg.yearfirst, cfg.dayfirst, tuple(getattr(cfg, n) for n in NAMES)


@pytest.mark.parametrize('flags', [(True, False), (False, True), (True, True), (False, False)])
def test_defaults_and_repeated_initialization(flags):
    cfg, ref = Configs(*flags), ReferenceConfigs(*flags)
    assert snapshot(cfg) == snapshot(ref)
    assert cfg.order_hint() == ref.order_hint()
    original = snapshot(cfg)
    cfg.clear_settings()
    ref.clear_settings()
    cleared = snapshot(cfg)
    cfg.__init__(*flags)
    ref.__init__(*flags)
    assert snapshot(cfg) == snapshot(ref) == cleared
    cfg.reset_settings()
    ref.reset_settings()
    assert snapshot(cfg) == snapshot(ref) == original


@pytest.mark.parametrize('name,value', [('jump', None), ('pertain', None), ('utc', None), ('tzoffset', 3600), ('month', 12), ('weekday', 4), ('hms', 2), ('ampm', 1)])
def test_namespace_crud_and_case_variants(name, value):
    cfg, ref = Configs(), ReferenceConfigs()
    token = 'customword' if name == 'tzoffset' else 'custöm'
    for obj in (cfg, ref):
        add = getattr(obj, 'add_' + name)
        args = (token,) if value is None else (token,)
        if name == 'tzoffset':
            assert add(*args, seconds=value)
        elif value is None:
            assert add(*args)
        else:
            assert add(*args, value)
    assert getattr(cfg, name) == getattr(ref, name)
    assert snapshot(cfg) == snapshot(ref)
    for obj in (cfg, ref):
        assert getattr(obj, 'del_' + name)(token.upper())
        assert not getattr(obj, 'del_' + name)(token)
    assert snapshot(cfg) == snapshot(ref)


def test_shallow_copy_edits_remain_independent():
    for cls in (Configs,):
        cfg = cls()
        other = copy.copy(cfg)
        cfg.add_month('custommonth', 2)
        assert 'custommonth' not in other.month
        cfg.set_month({'newmonth': 3})
        assert 'custommonth' not in other.month
        assert 'custommonth' not in cfg.month
        cfg.clear_settings()
        assert 'custommonth' not in other.month




def test_copy_deepcopy_and_pickle_keep_rules():
    cfg = Configs(False, True)
    cfg.add_month('custommonth', 1)
    for clone in (copy.deepcopy(cfg), pickle.loads(pickle.dumps(cfg))):
        assert snapshot(clone) == snapshot(cfg)
        cfg.add_month('later', 2)
        assert 'later' not in clone.month
        cfg.del_month('later')






@pytest.mark.parametrize('token', ['anotherword', 'a' * 65, 'école'])
def test_optimized_token_shapes_keep_python_case_variants(token):
    cfg, ref = Configs(), ReferenceConfigs()
    for obj in (cfg, ref):
        obj.add_jump(token)
    assert cfg.jump == ref.jump
    assert cfg.del_jump(token) == ref.del_jump(token)


@pytest.mark.parametrize('name', NAMES)
def test_public_token_entry_reads_string_subclass_before_case_callbacks(name):
    # R06 explicitly replaces the old exact-str rejection contract. The
    # historical oracle retains its own interface; the answer here is builtin
    # stored text and the independently requested numeric code.
    calls = []
    class Token(str):
        def lower(self):
            calls.append('lower')
            return 'different'
    cfg = Configs()
    cfg.clear_settings()
    token = Token('custom')
    add = getattr(cfg, 'add_' + name)
    assert add(token, seconds=1) if name == 'tzoffset' else add(token) if name in NAMES[:3] else add(token, 1)
    expected = {'custom'} if name in NAMES[:3] else {'custom': 1}
    assert getattr(cfg, name) == expected
    assert getattr(cfg, 'del_' + name)(token)
    replacement = {token} if name in NAMES[:3] else {token: 1}
    assert getattr(cfg, 'set_' + name)(replacement)
    assert getattr(cfg, name) == expected
    assert calls == []




def test_failed_replace_keeps_existing_rules():
    for cls in (Configs, ReferenceConfigs):
        cfg=cls();before=snapshot(cfg)
        with pytest.raises(ValueError):cfg.set_month({'first':1,'invalid':13})
        assert snapshot(cfg)==before
