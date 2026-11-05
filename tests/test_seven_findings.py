"""Regressions for the seven approved corrections, using independent expectations."""
import copy
import pickle
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pytest
from rstimes import Configs, Delta, Pydt, parse, parse_str, parse_to_epoch


def test_config_callback_uses_input_snapshot():
    cfg = Configs()
    mapping = {}
    class Number:
        def __index__(self):
            mapping['later'] = 2
            return 1
    mapping['mymonth'] = Number()
    cfg.set_month(mapping)
    assert cfg.month == {'mymonth': 1}


def test_failed_config_conversion_does_not_commit():
    cfg = Configs()
    before = cfg.month
    class Number:
        def __index__(self):
            raise ValueError('conversion failed')
    with pytest.raises(ValueError, match='conversion failed'):
        cfg.set_month({'mymonth': 1, 'later': Number()})
    assert cfg.month == before


def test_config_rechecks_callback_namespace_changes():
    cfg = Configs()
    before = cfg.month
    class Number:
        def __index__(self):
            cfg.add_weekday('mymonth', 0)
            return 1
    with pytest.raises(ValueError):
        cfg.set_month({'mymonth': Number()})
    assert cfg.month == before
    assert cfg.weekday['mymonth'] == 0


def test_delta_slot_callback_uses_owned_snapshot():
    slots = {'payload': 1}
    class Child(Delta):
        __slots__ = ('payload', 'later')
        def __setattr__(self, key, value):
            if key == 'payload':
                slots['later'] = 2
            super().__setattr__(key, value)
    value = Child(days=1)
    old_hash = hash(value)
    value.__setstate__((None, slots))
    assert value.payload == 1
    assert not hasattr(value, 'later')
    assert value.days == 1 and hash(value) == old_hash


@pytest.mark.parametrize('entry', [parse_str, parse_to_epoch])
def test_weekday_year_carry_cannot_wrap(entry):
    with pytest.raises(OverflowError):
        entry('31 December 2147483647 Wed')


def test_supported_wide_year_still_reaches_target():
    seen = {}
    def target(**fields):
        seen.update(fields)
        return datetime(2000, 1, 1)
    parse_str('9999-12-31 Sat', dtclass=target)
    assert seen['year'] == 10000
    assert parse_to_epoch('9999-12-31 Sat', unit='s') == 253402300800


def test_unicode_expanded_forms_reject_conflicts():
    cfg = Configs()
    cfg.add_month('straße', 1)
    with pytest.raises(ValueError):
        cfg.add_weekday('strasse', 0)
    with pytest.raises(ValueError):
        cfg.add_month('strasse', 2)
    assert parse_str('14 STRASSE 2024', cfg=cfg) == datetime(2024, 1, 14)


def test_unicode_alias_deletion_and_restore_keep_same_rules():
    cfg = Configs()
    cfg.add_month('straße', 1)
    cfg.add_month('strasse', 1)
    cfg.del_month('strasse')
    for restored in (cfg, copy.copy(cfg), copy.deepcopy(cfg), pickle.loads(pickle.dumps(cfg))):
        for token in ('straße', 'Straße', 'STRASSE'):
            assert parse_str('14 '+token+' 2024', cfg=restored) == datetime(2024, 1, 14)


@pytest.mark.parametrize('unit,ticks', [('3D',1),('2h',1),('3us',1),('3ns',-334),('2M',1),('3Y',2)])
def test_numpy_multiplier_scalar_paths(unit,ticks):
    value = np.datetime64(ticks, unit)
    microseconds = int(value.astype('datetime64[us]').astype(np.int64))
    expected = datetime(1970, 1, 1) + timedelta(microseconds=microseconds)
    assert parse(value) == expected
    assert Pydt.fromdatetime64(value) == expected
    assert parse_to_epoch(value, unit='us') == microseconds
    assert parse_str('12:00', default=value).date() == expected.date()
    # GN07 preserves the original ns until Delta's datetime exit, which rounds
    # once to us. Parser and fromdatetime64 deliberately retain their own rules.
    original_ns=int(value.astype('datetime64[ns]').astype(np.int64))
    quotient,remainder=divmod(original_ns,1000)
    rounded=quotient+(remainder>500 or (remainder==500 and quotient%2))
    assert Delta(days=1) + value == datetime(1970,1,1)+timedelta(days=1,microseconds=rounded)


@pytest.mark.parametrize('kind', [np.datetime64,np.timedelta64])
@pytest.mark.parametrize('unit', ['Y','M','W','D','h','m','s','ms','us','ns','3D','2h','3us'])
def test_numpy_batch_matches_ordinary_dispatch(kind,unit):
    value = kind(1,unit)
    delta = Delta(days=1)
    try:
        expected = [value + delta]
    except Exception as error:
        with pytest.raises(type(error)):
            delta.apply_many([value])
    else:
        actual = delta.apply_many([value])
        assert actual == expected
        assert type(actual[0]) is type(expected[0])


class Region(ZoneInfo):
    pass


@pytest.mark.parametrize('fold', [0,1])
@pytest.mark.parametrize('entry', ['construct','replace','fromdatetime','combine','fromseconds'])
def test_regional_subtype_rejects_missing_time(entry,fold):
    zone = Region('America/New_York')
    if entry == 'construct':
        operation = lambda: Pydt(2024,3,10,2,30,tzinfo=zone,fold=fold)
    elif entry == 'replace':
        operation = lambda: Pydt(2024,3,9,2,30,tzinfo=zone).replace(day=10,fold=fold)
    elif entry == 'fromdatetime':
        operation = lambda: Pydt.fromdatetime(datetime(2024,3,10,2,30,tzinfo=zone,fold=fold))
    elif entry == 'combine':
        operation = lambda: Pydt.combine(date(2024,3,10),time(2,30,fold=fold),zone)
    else:
        operation = lambda: Pydt.fromseconds(1710037800,zone)
    with pytest.raises(ValueError, match='does not exist'):
        operation()


@pytest.mark.parametrize('fold', [0,1])
def test_regional_subtype_repeated_and_restored_values(fold):
    value=Pydt(2024,11,3,1,30,tzinfo=Region('America/New_York'),fold=fold)
    expected=datetime(2024,11,3,1,30,tzinfo=ZoneInfo('America/New_York'),fold=fold)
    assert value.timestamp()==expected.timestamp()
    restored=pickle.loads(pickle.dumps(value))
    assert restored.timestamp()==value.timestamp() and restored.fold==fold


@pytest.mark.parametrize('method', ['is_start_of','is_end_of'])
@pytest.mark.parametrize('fields,zone,name', [((2011,12,29,12),'Pacific/Apia','Friday'),((9999,12,31,12),'Asia/Shanghai','Sunday')])
def test_nonmatching_boundary_does_not_construct_absent_target(method,fields,zone,name):
    assert getattr(Pydt(*fields,tzinfo=zone),method)(name) is False


def test_absent_period_transform_still_fails():
    value=Pydt(2011,12,29,12,tzinfo='Pacific/Apia')
    with pytest.raises(ValueError):
        value.to_start_of('Friday')


@pytest.mark.parametrize("fields,zone", [((1,1,1),"Asia/Shanghai"),((9999,12,31),"America/New_York")])
def test_plain_regional_subtype_keeps_valid_local_range_edges(fields,zone):
    value=Pydt(*fields,tzinfo=Region(zone))
    assert (value.year,value.month,value.day)==fields


def test_overridden_regional_protocol_is_still_checked():
    calls=[]
    class Observed(ZoneInfo):
        def fromutc(self,value):
            calls.append(value)
            return super().fromutc(value)
    value=Pydt(2024,5,7,12,tzinfo=Observed("America/New_York"))
    assert calls and value.hour==12


@pytest.mark.parametrize("kind",[np.datetime64,np.timedelta64])
def test_multiplier_precision_conversion_can_use_wide_intermediate(kind):
    ticks=(1<<63)-1
    value=kind(ticks,"3ns")
    micros=(ticks*3)//1000
    if kind is np.datetime64:
        assert parse(value)==datetime(1970,1,1)+timedelta(microseconds=micros)
        assert parse_to_epoch(value,unit="us")==micros
    else:
        assert (Delta()+value).to_timedelta()==timedelta(microseconds=micros)
