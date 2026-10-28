"""Fixed inputs and oracle serializers for the Config/parse acceptance suite."""
from datetime import date, datetime
import importlib
from pathlib import Path
EVIDENCE = Path(__file__).resolve().parents[1] / 'tasks/evidence/parser-function-rewrite/correctness'
NAMES = ('jump', 'pertain', 'utc', 'tz', 'month', 'weekday', 'hms', 'ampm')
TZ = {'AKDT': -8, 'AKST': -9, 'EST': -5, 'HST': -10, 'MST': -7, 'PST': -8, 'CDT': -5, 'EDT': -4, 'MDT': -6, 'PDT': -7}

def edit_method(cfg, action, namespace):
    """Map approved interface names without changing either native class."""
    modern = hasattr(cfg, 'tzoffset')
    name = 'tzoffset' if namespace == 'tz' and modern else namespace
    verb = {'remove': 'del', 'replace': 'set'}.get(action, action) if modern else action
    return getattr(cfg, verb + '_' + name)


def configured(cls):
    cfg = cls()
    for token, hours in TZ.items():
        edit_method(cfg, 'add', 'tz')(token, hours)
    return cfg

def normalize(text):
    text = str(text).replace('tzoffset=', 'tz=').replace('Configs.tzoffset', 'Configs.tz').replace('add_tzoffset', 'add_tz')
    if text.startswith('rstimes.errors.'):
        text = 'cytimes.errors.' + text[len('rstimes.errors.'):]
    text = text.replace('expected rstimes.parser.Configs,', 'expected cytimes.parser.Configs,')
    return text

def exception(exc, seen=None):
    seen = set() if seen is None else seen
    if exc is None or id(exc) in seen:
        return None
    seen.add(id(exc))
    return {'type': normalize(type(exc).__module__ + '.' + type(exc).__name__), 'message': normalize(str(exc)), 'cause': exception(exc.__cause__, seen), 'context': exception(exc.__context__, seen), 'suppress_context': exc.__suppress_context__}

def value(obj):
    if isinstance(obj, datetime):
        tz = obj.tzinfo
        return {'type': type(obj).__module__ + '.' + type(obj).__name__, 'fields': [obj.year, obj.month, obj.day, obj.hour, obj.minute, obj.second, obj.microsecond], 'fold': obj.fold, 'tztype': None if tz is None else type(tz).__module__ + '.' + type(tz).__name__, 'tzname': obj.tzname(), 'offset': None if obj.utcoffset() is None else obj.utcoffset().total_seconds(), 'text': str(obj)}
    if isinstance(obj, dict):
        return {str(k): value(v) for k, v in sorted(obj.items(), key=lambda item: str(item[0]))}
    if isinstance(obj, (set, frozenset)):
        return sorted(obj, key=repr)
    if isinstance(obj, (list, tuple)):
        return [value(v) for v in obj]
    return normalize(obj) if isinstance(obj, str) else obj

def outcome(call):
    try:
        return {'value': value(call())}
    except Exception as exc:
        return {'error': exception(exc)}
EXTRA_GROUPS = {'iso': ['2024-02-29T23:59:59.123456789', '1900-02-29', '2000-02-29', '2100-02-29', '0000-01-01', '9999-12-31T23:59:59', '10000-01-01', '20240229T235959', '2024-060', '2023-366', '2020-W53-7', '2021-W01-1', '2024W091', '2024-W00-1', '2024-W54-1', '2024-W09-0', '2024-W09-8', '2024-02', '2024-', '2024-02-29T', '2024-02-29T12:', '2024-02-29T12:34:', '2024-02-29 trailing words', '20240229junk', '2024-02-29T12:34:56+', '2024-02-29T24:00:00', '2024-02-29T23:60:00', '2024-02-29T23:59:60'], 'ymd': ['03/04/05', '31/12/99', '12/31/00', '49/01/02', '50/01/02', '75/01/02', '76/01/02', '77/01/02', '01/02/49', '01/02/50', '01/02/75', '01/02/76', '01/02/77', '2024 31 12', '31 2024 12', '12 31 2024', '2024/2/30', 'Feb 31 2024', 'February 2024', '29 February', 'Monday January 1 2024', 'Sunday December 31 2023'], 'time': ['12.5h', '12,5h', '1.25m', '1,25m', '1.123456789s', '1,123456789s', '23h59m59.9999999s', '00:00:00.0000001', '12:34.5', '12:34,5', '12:34:56.1234567', '12:34:56,1234567', '0 am', '0 pm', '12 AM', '12 PM', '13 PM', '24h', '60m', '60s', '1h 2h', '1m 2m', '1s 2s', '1 am pm'], 'tz': ['2024-06-15T12:00Z', '2024-06-15T12:00z', '2024-06-15T12:00+05', '2024-06-15T12:00-03', '2024-06-15T12:00+0530', '2024-06-15T12:00-0330', '2024-06-15T12:00+05:45', '2024-06-15T12:00+23:59', '2024-06-15T12:00+24:00', '2024-06-15T12:00+00:60', '15 June 2024 12:00 GMT+3', '15 June 2024 12:00 GMT-3', '15 June 2024 12:00 XYZ', '15 June 2024 12:00 EST', '15 June 2024 12:00 UTC', '15 June 2024 12:00 AKDT', '15 June 2024 12:00 (PST)', '2024-06-15T12:00+05:30:45'], 'lexical': ['29 février 2024', '29 Februar 2024', '29 febrero 2024', '29 febbraio 2024', '29 февраля 2024', '29 Şubat 2024', '29 février 2024 à 12h30', '2024年2月29日', '29\xa0February\xa02024', '29\tFebruary\t2024', '29\nFebruary\n2024', '  29 February 2024  ', '29...February...2024', '29-FEBRUARY-2024', '29-fEBRUARY-2024', 'on the 29th of February 2024', 'no date here', '', ' ', '\x00', '2024-02-29\x00', '12345678901234567890', '2024-02-29 ' + 'word ' * 200]}
EXTRA = [(category, text) for category, texts in EXTRA_GROUPS.items() for text in texts]

def parse_cases():
    cases = []
    for category, text in EXTRA:
        for iso, ignore in ((True, True), (True, False), (False, True), (False, False)):
            cases.append({'text': text, 'category': category, 'kwargs': {'isoformat': iso, 'ignoretz': ignore}})
    for text in EXTRA_GROUPS['ymd']:
        for year in (None, False, True):
            for day in (None, False, True):
                cases.append({'text': text, 'category': 'order', 'kwargs': {'yearfirst': year, 'dayfirst': day}})
    return cases

def parse_outcome(parse, cls, case):
    return outcome(lambda: parse(case['text'], default=date(2024, 1, 31), cfg=configured(cls), **case['kwargs']))

def config_state(cfg):
    return {'yearfirst': cfg.yearfirst, 'dayfirst': cfg.dayfirst, 'order_hint': cfg.order_hint(), 'repr': normalize(repr(cfg)), **{n: value(getattr(cfg, 'tzoffset' if n == 'tz' and hasattr(cfg, 'tzoffset') else n)) for n in NAMES}}

def config_transcript(cls, include_queries=True):
    records = []

    def record(label, cfg, call):
        records.append({'id': label, 'result': outcome(call), 'state': config_state(cfg)})
    for name in NAMES:
        cfg = cls()
        empty = set() if name in NAMES[:3] else {}
        add = edit_method(cfg, 'add', name)
        replace = edit_method(cfg, 'replace', name)
        args = ('zztest',) if name in NAMES[:3] else ('zztest', 1)
        record(name + ':empty', cfg, lambda: replace(empty))
        record(name + ':add', cfg, lambda: add(*args))
        record(name + ':duplicate', cfg, lambda: add(*args))
        if include_queries:
            for token in ('zztest', 'ZZTEST', 'Zztest', 'zZtest', 'absent', None, 3, ''):
                record(name + ':is:' + repr(token), cfg, lambda t=token: getattr(cfg, 'is_' + name)(t))
                getter = 'get_tz_offset' if name == 'tz' else 'get_' + name
                if hasattr(cfg, getter):
                    record(name + ':get:' + repr(token), cfg, lambda t=token: getattr(cfg, getter)(t))
        record(name + ':remove', cfg, lambda: edit_method(cfg, 'remove', name)('zztest'))
        record(name + ':remove-again', cfg, lambda: edit_method(cfg, 'remove', name)('zztest'))
        record(name + ':reset', cfg, lambda: replace(None))
        for token in ('mon', 'jan', None, 3, '', 'a b', 'a-b'):
            bad = (token,) if name in NAMES[:3] else (token, 1)
            record(name + ':bad-token:' + repr(token), cfg, lambda a=bad: add(*a))
        if name not in NAMES[:3]:
            for v in (-100000, -1, 0, 1, 2, 3, 6, 7, 12, 13, 86400, 1.9, True, None, '1', 2 ** 63):
                record(name + ':value:' + repr(v), cfg, lambda v=v: add('zzvalue', v))
            for mapping in ({'zzvalid': 1, 'zzinvalid': 100000}, {'zzvalid': 1, 'mon': 1}, [], {'zzvalid': None}):
                record(name + ':replace:' + repr(mapping), cfg, lambda m=mapping: replace(m))
        else:
            for tokens in ({'zzvalid', None}, ['zzvalid'], {'mon'}, 'abc'):
                record(name + ':replace:' + repr(value(tokens)), cfg, lambda t=tokens: replace(t))
        record(name + ':reinitialize', cfg, lambda: cfg.__init__(False, True))
        record(name + ':clear', cfg, cfg.clear_settings)
        record(name + ':reset-all', cfg, cfg.reset_settings)
    for yf in (False, True, None, 0, 1, [], [1]):
        for df in (False, True, None):
            records.append({'id': f'init:{yf!r}:{df!r}', 'result': outcome(lambda: config_state(cls(yf, df)))})
    from dateutil.parser import parserinfo
    for yf in (False, True):
        for df in (False, True):
            info = parserinfo(yearfirst=yf, dayfirst=df)
            records.append({'id': f'parserinfo:{yf}:{df}', 'result': outcome(lambda: config_state(cls.from_parserinfo(info)))})
    for attr, bad in [('JUMP', {'and', None}), ('MONTHS', [('one',), ('two', None)]), ('TZOFFSET', {'zztest': 100000}), ('UTCZONE', [None]), ('HMS', [('zzhour',), ('zzminute',), ('zzsecond',), ('zzfour',)])]:
        info = parserinfo()
        setattr(info, attr, bad)
        records.append({'id': 'parserinfo:' + attr, 'result': outcome(lambda: config_state(cls.from_parserinfo(info)))})
    records.append({'id': 'parserinfo:invalid', 'result': outcome(lambda: cls.from_parserinfo('bad'))})
    return records

def copy_classes():
    """Load stable, importable class identities required by the pickle protocol."""
    import importlib.util
    import sys
    name = 'cytimes_config_copy_fixture'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, EVIDENCE / 'config_copy_fixture.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    module = sys.modules[name]
    return module

def config_copy_scenario(cls, operation, kind):
    import copy
    import pickle
    source = cls(False, True)
    for name in NAMES:
        token = 'zz' + name
        add = getattr(source, 'add_' + name)
        if name in NAMES[:3]:
            add(token)
        elif name == 'tz':
            add(token, seconds=123)
        else:
            add(token, 1)
    if kind != 'base':
        source.extra = {'nested': [['initial']]}
        if kind == 'subclass':
            source.alias = source.extra
    before = config_state(source)

    def perform():
        if operation == 'copy':
            return copy.copy(source)
        if operation == 'deepcopy':
            return copy.deepcopy(source)
        return pickle.loads(pickle.dumps(source, protocol=int(operation)))
    try:
        result = perform()
    except Exception as exc:
        return {'error': exception(exc), 'source_state': config_state(source)}
    records = {'same_type': type(result) is cls, 'distinct_object': result is not source, 'initial_state': config_state(result), 'initial_matches_source': config_state(result) == before, 'recognition': {name: getattr(result, 'is_' + name)('zz' + name) for name in NAMES}}
    result.add_month('zzcopy', 8)
    records['mutation_result_state'] = config_state(result)
    records['mutation_source_state'] = config_state(source)
    records['native_table_shared'] = source.is_month('zzcopy')
    records['namespace_sharing'] = {}
    for name in NAMES:
        token = 'zzcopy' + name
        add = getattr(result, 'add_' + name)
        if name in NAMES[:3]:
            add(token)
        elif name == 'tz':
            add(token, seconds=321)
        else:
            add(token, 1)
        records['namespace_sharing'][name] = getattr(source, 'is_' + name)(token)
    records['extra_present'] = hasattr(result, 'extra') if kind != 'base' else None
    if kind != 'base' and hasattr(result, 'extra'):
        records['extra_before'] = value(result.extra)
        records['extra_shared'] = result.extra is source.extra
        if kind == 'subclass':
            records['alias_preserved'] = result.extra is result.alias
        result.extra['nested'][0].append('changed')
        records['extra_result_after'] = value(result.extra)
        records['extra_source_after'] = value(source.extra)
    package = 'cytimes.parser' if cls.__module__.startswith('cytimes.parser') or cls.__name__.startswith('Baseline') else 'cytimes_rewrite'
    parse_api = importlib.import_module(package).parse
    records['copied_parse'] = outcome(lambda: parse_api('15 zzcopy 2024', cfg=result))
    records['source_parse'] = outcome(lambda: parse_api('15 zzcopy 2024', cfg=source))

    def labels(obj):
        if isinstance(obj, dict):
            return {key: labels(v) for key, v in obj.items()}
        if isinstance(obj, list):
            return [labels(v) for v in obj]
        if isinstance(obj, str):
            return obj.replace("<'BaselineSubclass'", "<'CopySubclass'").replace("<'RewrittenSubclass'", "<'CopySubclass'").replace("<'BaselineSlots'", "<'CopySlots'").replace("<'RewrittenSlots'", "<'CopySlots'")
        return obj
    return labels(records)
