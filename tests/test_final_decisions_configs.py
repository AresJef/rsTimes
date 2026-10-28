"""F12: import one observed table and reject aliases the lexer cannot read."""

import copy
import pickle
from datetime import datetime, timezone

import pytest
import numpy as np
from dateutil.parser import parserinfo

from rstimes import Configs, Pydt, parse, parse_str, parse_to_epoch


TRUTH_POSITIONS = [
    (entry, option)
    for entry in ('parse_str', 'parse', 'parse_to_epoch', 'Pydt.parse')
    for option in ('yearfirst', 'dayfirst', 'ignoretz', 'isoformat', 'strict')
] + [
    (entry, option)
    for entry in ('Configs', 'Configs.from_parserinfo')
    for option in ('yearfirst', 'dayfirst')
] + [
    ('Pydt.tomicroseconds', 'utc'), ('Pydt.toseconds', 'utc'),
    ('Pydt.diff', 'absolute'), ('Pydt.tz_switch', 'naive'),
]


def call_truth_option(entry, option, value):
    if entry == 'Configs':
        return Configs(**{option: value})
    if entry == 'Configs.from_parserinfo':
        info = parserinfo()
        setattr(info, option, value)
        return Configs.from_parserinfo(info)
    if entry in ('Pydt.tomicroseconds', 'Pydt.toseconds'):
        return getattr(Pydt(2024, 5, 7), entry.split('.')[1])(utc=value)
    if entry == 'Pydt.diff':
        return Pydt(2024, 5, 7).diff(datetime(2024, 5, 8), 'D', absolute=value)
    if entry == 'Pydt.tz_switch':
        return Pydt(2024, 5, 7, tzinfo='UTC').tz_switch('UTC', naive=value)
    function = {'parse_str': parse_str, 'parse': parse,
                'parse_to_epoch': parse_to_epoch, 'Pydt.parse': Pydt.parse}[entry]
    return function('2024-05-07', **{option: value})


@pytest.mark.parametrize('entry,option', TRUTH_POSITIONS)
@pytest.mark.parametrize('text', ['False', '', b'False', bytearray(b'False')])
def test_all_truth_options_reject_text_before_conversion(entry, option, text):
    with pytest.raises(TypeError):
        call_truth_option(entry, option, text)


@pytest.mark.parametrize('entry,option', TRUTH_POSITIONS)
@pytest.mark.parametrize('kind', [
    'false', 'true', 'zero', 'one', 'none', 'empty', 'list',
    'numpy_false', 'numpy_true', 'custom_false', 'custom_true', 'length',
])
def test_boolean_options_accept_only_actual_boolean_scalars(entry, option, kind):
    calls = []
    class Truth:
        def __bool__(self):
            calls.append('bool')
            return kind == 'custom_true'
    class Length:
        def __len__(self):
            calls.append('len')
            return 1
    values = dict(false=False, true=True, zero=0, one=1, none=None,
                  empty=[], list=[1], numpy_false=np.bool_(False), numpy_true=np.bool_(True))
    value = Truth() if kind.startswith('custom_') else Length() if kind == 'length' else values[kind]
    none_follows_configuration = (kind == 'none' and option in ('yearfirst', 'dayfirst')
                                  and entry in ('parse_str', 'parse', 'parse_to_epoch', 'Pydt.parse'))
    if kind not in ('false', 'true', 'numpy_false', 'numpy_true') and not none_follows_configuration:
        with pytest.raises(TypeError):
            call_truth_option(entry, option, value)
        assert calls == []
        return
    wanted = option == 'yearfirst' if none_follows_configuration else kind in ('true', 'numpy_true')
    result = call_truth_option(entry, option, value)
    assert calls == []
    if isinstance(result, Configs):
        assert getattr(result, option) is wanted
        expected = datetime(2024, 7, 5) if option == 'dayfirst' and wanted else datetime(2024, 5, 7)
        assert parse_str('2024-05-07', cfg=result, isoformat=False) == expected
    else:
        assert result == call_truth_option(entry, option, wanted)


@pytest.mark.parametrize('entry,option', TRUTH_POSITIONS)
@pytest.mark.parametrize('error_class', [RuntimeError, TypeError])
def test_boolean_options_reject_objects_without_calling_their_truth_hook(entry, option, error_class):
    error = error_class('truth source failed')
    error.detail = object()
    detail = error.detail
    calls = []
    class Truth:
        def __bool__(self):
            calls.append('bool')
            raise error
    with pytest.raises(TypeError) as caught:
        call_truth_option(entry, option, Truth())
    assert caught.value is not error and error.args == ('truth source failed',)
    assert error.detail is detail and calls == []


@pytest.mark.parametrize('entry,option', TRUTH_POSITIONS)
@pytest.mark.parametrize('base', [str, bytes, bytearray])
def test_real_text_subclasses_are_rejected_without_a_truth_callback(entry, option, base):
    class Text(base):
        def __bool__(self):
            pytest.fail('text must be rejected before its truth callback')
    value = Text('False' if base is str else b'False')
    with pytest.raises(TypeError):
        call_truth_option(entry, option, value)


def test_imported_flags_reject_unknown_truth_before_reading_the_next_flag():
    calls = []
    class Flag:
        def __init__(self, name, result):
            self.name, self.result = name, result
        def __bool__(self):
            calls.append('truth ' + self.name)
            return self.result
    class Info(parserinfo):
        @property
        def yearfirst(self):
            calls.append('read yearfirst')
            return Flag('yearfirst', True)
        @yearfirst.setter
        def yearfirst(self, value):
            pass
        @property
        def dayfirst(self):
            calls.append('read dayfirst')
            return Flag('dayfirst', False)
        @dayfirst.setter
        def dayfirst(self, value):
            pass
    info = Info()
    calls.clear()
    with pytest.raises(TypeError):
        Configs.from_parserinfo(info)
    assert calls == ['read yearfirst']


def test_parserinfo_string_rows_remain_whole_words():
    class Info(parserinfo):
        MONTHS = ["qqq", *parserinfo.MONTHS[1:]]
        WEEKDAYS = ["qqday", *parserinfo.WEEKDAYS[1:]]
        HMS = ["qqhour", *parserinfo.HMS[1:]]
        AMPM = ["qqam", *parserinfo.AMPM[1:]]

    cfg = Configs.from_parserinfo(Info())
    assert cfg.month["qqq"] == 1 and "q" not in cfg.month
    assert cfg.weekday["qqday"] == 0
    assert cfg.hms["qqhour"] == 0
    assert cfg.ampm["qqam"] == 0
    assert parse_str("14 qqq 2024", cfg=cfg) == datetime(2024, 1, 14)


def test_parserinfo_reads_each_table_once_in_original_order():
    names = ["JUMP", "PERTAIN", "UTCZONE", "TZOFFSET", "MONTHS", "WEEKDAYS", "HMS", "AMPM"]
    calls = []

    class Info(parserinfo):
        armed = False

        def __getattribute__(self, name):
            if name in names and object.__getattribute__(self, "armed"):
                calls.append(name)
                if calls.count(name) != 1:
                    raise AssertionError("table was read a second time")
            return super().__getattribute__(name)

    info = Info()
    info.armed = True
    Configs.from_parserinfo(info)
    assert calls == names


def test_parserinfo_displayed_class_does_not_authorize_import():
    class Pretender:
        __class__ = parserinfo

    with pytest.raises(TypeError):
        Configs.from_parserinfo(Pretender())


@pytest.mark.parametrize("name, value", [("jump", None), ("pertain", None), ("utc", None),
                                         ("tzoffset", 3600), ("month", 1), ("weekday", 0),
                                         ("hms", 0), ("ampm", 0)])
@pytest.mark.parametrize("token", ["word-other", "UTC+8", "a.m.", "word123", "İ"])
def test_unreadable_generated_aliases_reject_without_partial_edit(name, value, token):
    cfg = Configs()
    before = cfg.__reduce__()
    add = getattr(cfg, "add_" + name)
    args = (token,) if value is None else (token, value)
    if name == "tzoffset":
        args = (token,)
        kwargs = {"seconds": value}
    else:
        kwargs = {}
    with pytest.raises(ValueError, match="Token"):
        add(*args, **kwargs)
    assert cfg.__reduce__() == before
    replacement = {token} if value is None else {token: value}
    with pytest.raises(ValueError):
        getattr(cfg, "set_" + name)(replacement)
    assert cfg.__reduce__() == before


def test_valid_aliases_copy_and_restore_with_same_meaning():
    cfg = Configs()
    cfg.add_month("qqmonth", 2)
    cfg.add_tzoffset("ZZONE", hours=8)
    cfg.add_jump(";")
    cfg.add_jump(" ")
    for restored in [copy.copy(cfg), copy.deepcopy(cfg), pickle.loads(pickle.dumps(cfg))]:
        for token in ["qqmonth", "QQMONTH", "Qqmonth"]:
            result = parse_str(f"14 {token} 2024 12:00 ZZONE", cfg=restored, ignoretz=False)
            assert (result.month, result.day, result.utcoffset().total_seconds()) == (2, 14, 28800)



@pytest.mark.parametrize("token", ["custöm\ud800", "word99'here", "one-two99three'four", "A_B C.D", "école\ud800"])
def test_old_unreadable_word_fixtures_are_explicitly_rejected(token):
    cfg = Configs()
    before = cfg.jump
    with pytest.raises(ValueError):
        cfg.add_jump(token)
    assert cfg.jump == before


@pytest.mark.parametrize('namespace,alias,text,expected', [
    ('hms', 'w', '2024-01-02 5w', datetime(2024, 1, 2, 5)),
    ('hms', 'week', '2024-01-02 5week', datetime(2024, 1, 2, 5)),
    ('hms', 'é', '2024-01-02 5é', datetime(2024, 1, 2, 5)),
    ('month', 'w', '14 w 2024', datetime(2024, 5, 14)),
    ('month', 'w', '2024 w 14', datetime(2024, 5, 14)),
    ('month', 'w', 'w 14 2024', datetime(2024, 5, 14)),
    ('month', 'mymonth', '14 mymonth 2024', datetime(2024, 5, 14)),
])
@pytest.mark.parametrize('origin', ['direct', 'copy', 'pickle'])
@pytest.mark.parametrize('entry', [parse_str, parse, parse_to_epoch])
@pytest.mark.parametrize('isoformat', [False, True])
@pytest.mark.parametrize('strict', [False, True])
@pytest.mark.parametrize('default', [None, datetime(2024, 1, 1)])
def test_incomplete_iso_lookahead_preserves_registered_alias(
    namespace, alias, text, expected, origin, entry, isoformat, strict, default,
):
    cfg = Configs()
    getattr(cfg, 'add_' + namespace)(alias, 0 if namespace == 'hms' else 5)
    if origin == 'copy':
        cfg = copy.copy(cfg)
    elif origin == 'pickle':
        cfg = pickle.loads(pickle.dumps(cfg))
    options = dict(cfg=cfg, strict=strict, isoformat=isoformat, default=default)
    if entry is parse_to_epoch:
        options['unit'] = 's'
        elapsed = expected - datetime(1970, 1, 1)
        expected = elapsed.days * 86400 + elapsed.seconds
    assert entry(text, **options) == expected


@pytest.mark.parametrize('token', [':', '/', '-', '.', ',', '+', '_', '@', 'W', 'T', 'Z', 'customunit'])
@pytest.mark.parametrize('flag', [0, 1, 2])
@pytest.mark.parametrize('mode', ['add', 'set'])
@pytest.mark.parametrize('entry', [parse_str, parse, parse_to_epoch])
@pytest.mark.parametrize('strict', [False, True])
def test_hms_alias_has_its_declared_role_or_is_rejected(token, flag, mode, entry, strict):
    cfg = Configs()
    cfg.clear_settings()
    before = cfg.__reduce__()
    def edit():
        return cfg.add_hms(token, flag) if mode == 'add' else cfg.set_hms({token: flag})
    if token == ':' and flag != 0:
        with pytest.raises(ValueError, match=':'):
            edit()
        assert cfg.__reduce__() == before
        return
    edit()
    clock = [0, 0, 0]
    clock[flag] = 5
    expected = datetime(2024, 1, 2, *clock)
    options = dict(cfg=cfg, strict=strict)
    if entry is parse_to_epoch:
        options['unit'] = 's'
        elapsed = expected - datetime(1970, 1, 1)
        expected = elapsed.days * 86400 + elapsed.seconds
    assert entry('2024-01-02 5' + token, **options) == expected


@pytest.mark.parametrize('namespace,flag', [('hms', 1), ('hms', 2), ('ampm', 0), ('ampm', 1)])
@pytest.mark.parametrize('mode', ['add', 'set', 'parserinfo', 'restore'])
def test_incompatible_colon_role_is_rejected_atomically_in_all_config_entries(namespace, flag, mode):
    cfg = Configs()
    cfg.clear_settings()
    before = cfg.__reduce__()
    with pytest.raises(ValueError, match=':'):
        if mode == 'add':
            getattr(cfg, 'add_' + namespace)(':', flag)
        elif mode == 'set':
            getattr(cfg, 'set_' + namespace)({':': flag})
        elif mode == 'parserinfo':
            info = parserinfo()
            for name in ('JUMP', 'PERTAIN', 'UTCZONE', 'TZOFFSET', 'MONTHS', 'WEEKDAYS', 'HMS', 'AMPM'):
                setattr(info, name, None)
            aliases = [('safehour',), ('safeminute',), ('safesecond',)] if namespace == 'hms' else [('safeam',), ('safepm',)]
            aliases[flag] = (':',)
            setattr(info, namespace.upper(), aliases)
            Configs.from_parserinfo(info)
        else:
            state = list(before[2])
            owners = list(state[4])
            owners[6 if namespace == 'hms' else 7] = {':': flag}
            state[4] = tuple(owners)
            cfg.__setstate__(tuple(state))
    assert cfg.__reduce__() == before


@pytest.mark.parametrize('strict', [False, True])
@pytest.mark.parametrize('text,expected', [
    ('2024-W02-1', datetime(2024, 1, 8)),
    ('2024-W021', datetime(2024, 1, 8)),
    ('2024-014', datetime(2024, 1, 14)),
])
def test_complete_iso_calendar_still_precedes_registered_w(text, expected, strict):
    cfg = Configs()
    cfg.add_hms('w', 0)
    assert parse_str(text, strict=strict, cfg=cfg) == expected


def test_pydt_parse_uses_imported_week_letter_alias():
    info = parserinfo()
    info.HMS = [('w',), ('qqminute',), ('qqsecond',)]
    cfg = Configs.from_parserinfo(info)
    assert Pydt.parse('2024-01-02 5w', cfg=cfg) == datetime(2024, 1, 2, 5)


@pytest.mark.parametrize('namespace', ['month', 'weekday', 'utc'])
@pytest.mark.parametrize('token', [':', '.', '/', '_', 'w', 'rolealias'])
@pytest.mark.parametrize('origin', ['direct', 'copy', 'pickle'])
def test_usable_punctuation_aliases_keep_other_namespace_meanings(namespace, token, origin):
    cfg = Configs()
    cfg.clear_settings()
    if namespace == 'month':
        cfg.add_month(token, 5)
        text, expected = f'2024 {token} 14', datetime(2024, 5, 14)
    elif namespace == 'weekday':
        cfg.add_weekday(token, 1)
        text, expected = f'2024-05-07 {token}', datetime(2024, 5, 7)
    else:
        cfg.add_utc(token)
        text, expected = f'2024-05-07 12:34:56 {token}', datetime(2024, 5, 7, 12, 34, 56, tzinfo=timezone.utc)
    if origin == 'copy':
        cfg = copy.copy(cfg)
    elif origin == 'pickle':
        cfg = pickle.loads(pickle.dumps(cfg))
    assert parse_str(text, cfg=cfg, ignoretz=False) == expected
