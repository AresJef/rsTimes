"""Protect parserinfo vocabulary migration through public Configs and parse calls."""
import copy
import pickle
from datetime import date, datetime, timedelta
from itertools import product

import pytest
from dateutil.parser import parserinfo
from rstimes import Configs, parse_str

TABLES = ("JUMP", "PERTAIN", "UTCZONE", "TZOFFSET", "MONTHS", "WEEKDAYS", "HMS", "AMPM")
NAMES = ("jump", "pertain", "utc", "tzoffset", "month", "weekday", "hms", "ampm")
INDEXED = ("MONTHS", "WEEKDAYS", "HMS", "AMPM")
DEFAULT = date(2024, 1, 1)


def import_info(info):
    """Use the public factory; isolated mutation checks replace this test helper."""
    return Configs.from_parserinfo(info)


def info_with(**changes):
    """Edit a valid source instance without dateutil pre-validating our fixtures."""
    info = parserinfo()
    for name, value in changes.items():
        setattr(info, name, value)
    return info


def parse(text, cfg, **kwargs):
    """Fix the reference date so tests never depend on the machine's current year."""
    return parse_str(text, cfg=cfg, default=DEFAULT, **kwargs)


def state(cfg):
    """Include every imported table and both calendar-order flags."""
    return cfg.yearfirst, cfg.dayfirst, tuple(getattr(cfg, name) for name in NAMES)


def expected_tables(info):
    """Describe table positions independently of the candidate's native lookup."""
    result = [set(info.JUMP), set(info.PERTAIN), {word.lower() for word in info.UTCZONE},
              dict(info.TZOFFSET)]
    for name, shift in (("MONTHS", 1), ("WEEKDAYS", 0), ("HMS", 0), ("AMPM", 0)):
        result.append({word.lower(): index + shift
                       for index, row in enumerate(getattr(info, name))
                       for word in ((row,) if isinstance(row, str) else row)})
    return tuple(result)


@pytest.mark.parametrize("yearfirst,dayfirst", product((False, True), repeat=2))
def test_standard_tables_and_calendar_order_are_imported(yearfirst, dayfirst):
    info = parserinfo(yearfirst=yearfirst, dayfirst=dayfirst)
    cfg = import_info(info)
    assert state(cfg) == (yearfirst, dayfirst, expected_tables(info))
    expected = {(False, False): (2005, 3, 4), (False, True): (2005, 4, 3),
                (True, False): (2003, 4, 5), (True, True): (2003, 5, 4)}
    assert parse("03/04/05", cfg, isoformat=False) == datetime(*expected[yearfirst, dayfirst])


STANDARD = parserinfo()
ALIASES = [(name, word.lower(), index + (name == "MONTHS"))
           for name in INDEXED for index, row in enumerate(getattr(STANDARD, name))
           for word in dict.fromkeys(row)]
ALIASES += [("UTCZONE", word, 0) for word in ("utc", "gmt", "z")]


@pytest.mark.parametrize("name,token,value", ALIASES)
@pytest.mark.parametrize("case", ("lower", "title", "upper"))
@pytest.mark.parametrize("isoformat", (False, True))
def test_every_standard_alias_reaches_the_correct_field(name, token, value, case, isoformat):
    cfg = import_info(parserinfo())
    word = getattr(token, case)()
    if name == "MONTHS":
        assert parse(f"14 {word} 2024", cfg, isoformat=isoformat) == datetime(2024, value, 14)
    elif name == "WEEKDAYS":
        assert parse(word, cfg, isoformat=isoformat) == datetime(2024, 1, 1) + timedelta(days=value)
    elif name == "HMS":
        clock = [0, 0, 0]
        clock[value] = 2
        assert parse(f"2024-01-02 2{word}", cfg, isoformat=isoformat) == datetime(2024, 1, 2, *clock)
    elif name == "AMPM":
        assert parse(f"2024-01-02 2{word}", cfg, isoformat=isoformat) == datetime(2024, 1, 2, 2 + value * 12)
    else:
        assert parse(f"2024-01-02 12:30 {word}", cfg, isoformat=isoformat, ignoretz=False).utcoffset() == timedelta(0)


@pytest.mark.parametrize("name,namespace,token,text,expected", [
    ("MONTHS", "month", "qqmonth", "14 qqmonth 2024", datetime(2024, 2, 14)),
    ("WEEKDAYS", "weekday", "qqday", "qqday", datetime(2024, 1, 2)),
    ("HMS", "hms", "qqminute", "2qqminute", datetime(2024, 1, 1, 0, 2)),
    ("AMPM", "ampm", "qqpm", "2qqpm", datetime(2024, 1, 1, 14)),
])
@pytest.mark.parametrize("shape", ("str", "tuple", "list", "set", "iterator"))
def test_whole_string_and_existing_alias_row_forms(name, namespace, token, text, expected, shape):
    row = {"str": lambda: token, "tuple": lambda: (token,), "list": lambda: [token],
           "set": lambda: {token}, "iterator": lambda: iter([token])}[shape]()
    cfg = import_info(info_with(**{name: [(), row]}))
    assert getattr(cfg, namespace)[token] == (2 if name == "MONTHS" else 1)
    assert parse(text, cfg) == expected


def custom_info():
    """Supply each vocabulary with a meaningful custom rule."""
    return info_with(JUMP=[" ", ";", "qskip"], PERTAIN=["qof"], UTCZONE=["QUTC"],
                     TZOFFSET={"QZONE": 28800, "QNEG": -19800, "QSEC": 1},
                     MONTHS=[("qjan", "qjanuary"), "qfeb"], WEEKDAYS=["qmon", "qtue"],
                     HMS=["qhour", "qminute", "qsecond"], AMPM=["qam", "qpm"])


@pytest.mark.parametrize("case", ("lower", "title", "upper"))
@pytest.mark.parametrize("isoformat", (False, True))
def test_custom_tables_work_together(case, isoformat):
    cfg = import_info(custom_info())
    word = lambda text: getattr(text, case)()
    assert cfg.jump == {" ", ";", "qskip"}
    assert parse(f"14 {word('qfeb')} 2024 2{word('qhour')} 3{word('qminute')} 4{word('qsecond')}",
                 cfg, isoformat=isoformat) == datetime(2024, 2, 14, 2, 3, 4)
    assert parse(word("qtue"), cfg, isoformat=isoformat) == datetime(2024, 1, 2)
    assert parse(f"14 qfeb 2024 2{word('qpm')}", cfg, isoformat=isoformat) == datetime(2024, 2, 14, 14)
    assert parse(f"qjan {word('qof')} 05", cfg, isoformat=isoformat) == datetime(2005, 1, 1)
    for token, seconds in (("qutc", 0), ("qzone", 28800), ("qneg", -19800), ("qsec", 1)):
        assert parse(f"2024-01-02 12:30 {word(token)}", cfg, isoformat=isoformat,
                     ignoretz=False).utcoffset() == timedelta(seconds=seconds)


@pytest.mark.parametrize("operation", ("copy", "deepcopy", "pickle"))
def test_imported_rules_are_detached_and_survive_copy_and_pickle(operation):
    info = custom_info()
    cfg = import_info(info)
    snapshot = state(cfg)
    info.MONTHS[1] = "changed"
    info.TZOFFSET["QZONE"] = 0
    info.dayfirst = True
    assert state(cfg) == snapshot
    clone = {"copy": copy.copy, "deepcopy": copy.deepcopy,
             "pickle": lambda value: pickle.loads(pickle.dumps(value))}[operation](cfg)
    assert state(clone) == snapshot
    assert parse("14 qfeb 2024 12:30 QZONE", clone, ignoretz=False).utcoffset() == timedelta(hours=8)
    clone.add_month("qnew", 3)
    assert "qnew" not in cfg.month
    cfg.add_month("qadded", 3)
    assert info.MONTHS == [("qjan", "qjanuary"), "changed"]


OUTER_FORMS = [(name, shape, subclass)
               for name in TABLES
               for shape in ((list, tuple, set) if name in TABLES[:3] else
                             (dict,) if name == "TZOFFSET" else (list, tuple))
               for subclass in (False, True)]


@pytest.mark.parametrize("name,shape,subclass", OUTER_FORMS)
def test_supported_outer_containers_and_real_subclasses(name, shape, subclass):
    original = parserinfo()
    cls = type("Container", (shape,), {}) if subclass else shape
    table = cls(getattr(original, name))
    cfg = import_info(info_with(**{name: table}))
    assert tuple(getattr(cfg, item) for item in NAMES) == expected_tables(original)


@pytest.mark.parametrize("name", TABLES)
def test_none_skips_only_that_table_without_restoring_defaults(name):
    reference = import_info(parserinfo())
    cfg = import_info(info_with(**{name: None}))
    index = TABLES.index(name)
    assert getattr(cfg, NAMES[index]) == (set() if index < 3 else {})
    for position, namespace in enumerate(NAMES):
        if position != index:
            assert getattr(cfg, namespace) == getattr(reference, namespace)
    assert parse("2024-01-02T12:30", cfg) == datetime(2024, 1, 2, 12, 30)


BAD_OUTERS = [(name, kind) for name in TABLES for kind in
              ("str", "bytes", "int", "frozenset", "generator", "wrong_empty", "fake_list")]
BAD_OUTERS += [(name, "set") for name in TABLES[3:]]


@pytest.mark.parametrize("name,kind", BAD_OUTERS)
def test_unsupported_outer_containers_raise_contextual_typeerror_without_iteration(name, kind):
    calls = []
    def values():
        calls.append("consumed")
        yield "qqword"
    class Pretender:
        __class__ = list
    bad = {"str": "", "bytes": b"", "int": 0, "frozenset": frozenset(), "set": set(),
           "generator": values(), "wrong_empty": {} if name != "TZOFFSET" else [],
           "fake_list": Pretender()}[kind]
    with pytest.raises(TypeError) as error:
        import_info(info_with(**{name: bad}))
    message = str(error.value)
    assert "from_parserinfo" in message and name in message
    assert repr(bad) in message if kind in ("str", "int") else type(bad).__name__ in message
    assert "None" in message
    assert calls == []


@pytest.mark.parametrize("name", TABLES)
def test_split_aliases_are_rejected_during_import(name):
    value = ["word-other"] if name in TABLES[:3] else (
        {"word-other": 3600} if name == "TZOFFSET" else [("word-other",)])
    with pytest.raises(ValueError):
        import_info(info_with(**{name: value}))


@pytest.mark.parametrize("name,limit", (("MONTHS", 12), ("WEEKDAYS", 7), ("HMS", 3), ("AMPM", 2)))
def test_indexed_table_positions_cannot_exceed_their_range(name, limit):
    with pytest.raises(ValueError):
        import_info(info_with(**{name: [()] * limit + [("qoverflow",)]}))


@pytest.mark.parametrize("value,error", ((86400, ValueError), (-86400, ValueError),
                                       (1.5, TypeError), ("3600", TypeError), (None, TypeError)))
def test_offset_values_keep_integer_and_range_validation(value, error):
    with pytest.raises(error):
        import_info(info_with(TZOFFSET={"QZONE": value}))


def test_cross_table_conflicts_are_not_silently_overwritten():
    with pytest.raises(ValueError):
        import_info(info_with(MONTHS=[("qcollision",)], WEEKDAYS=[("qcollision",)]))


@pytest.mark.parametrize("value", (None, 3, {}, "parserinfo"))
def test_wrong_source_type_is_rejected(value):
    with pytest.raises(TypeError):
        import_info(value)


def test_pretended_parserinfo_type_is_rejected():
    class Pretender:
        __class__ = parserinfo
    with pytest.raises(TypeError):
        import_info(Pretender())


def test_source_tables_are_read_and_iterated_once_in_order_then_detached():
    events = []
    class OnceList(list):
        def __init__(self, name, values):
            super().__init__(values)
            self.name = name
        def __iter__(self):
            events.append("iterate:" + self.name)
            assert events.count("iterate:" + self.name) == 1
            return super().__iter__()
    class ObservedInfo(parserinfo):
        armed = False
        def __getattribute__(self, name):
            if name in (*TABLES, "yearfirst", "dayfirst") and object.__getattribute__(self, "armed"):
                events.append("get:" + name)
            return super().__getattribute__(name)
    info = ObservedInfo()
    for name in TABLES:
        if name != "TZOFFSET":
            setattr(info, name, OnceList(name, getattr(info, name)))
    info.armed = True
    cfg = import_info(info)
    expected = ["get:yearfirst", "get:dayfirst"]
    for name in TABLES:
        expected.append("get:" + name)
        if name != "TZOFFSET":
            expected.append("iterate:" + name)
    assert events == expected
    events.clear()
    assert parse("14 Jan 2024", cfg) == datetime(2024, 1, 14)
    assert events == []


@pytest.mark.parametrize("fail_at", TABLES)
@pytest.mark.parametrize("failure", ("attribute", "iteration", "invalid_type"))
def test_failed_import_stops_before_reading_later_tables(fail_at, failure):
    calls = []
    class SentinelError(Exception):
        pass
    class BrokenList(list):
        def __iter__(self):
            raise SentinelError("iteration:" + fail_at)
    class BrokenDict(dict):
        def keys(self):
            raise SentinelError("iteration:" + fail_at)
        def __iter__(self):
            return super().__iter__()
    class BrokenInfo(parserinfo):
        armed = False
        def __getattribute__(self, name):
            if name in TABLES and object.__getattribute__(self, "armed"):
                calls.append(name)
                if name == fail_at and failure == "attribute":
                    raise SentinelError(name)
            return super().__getattribute__(name)
    info = BrokenInfo()
    if failure == "invalid_type":
        setattr(info, fail_at, 0)
    elif failure == "iteration":
        value = getattr(info, fail_at)
        setattr(info, fail_at, BrokenDict({"QZONE": 3600}) if fail_at == "TZOFFSET" else BrokenList(value))
    info.armed = True
    with pytest.raises(TypeError if failure == "invalid_type" else SentinelError):
        import_info(info)
    assert calls == list(TABLES[:TABLES.index(fail_at) + 1])


def test_custom_parserinfo_methods_are_not_migrated():
    class MethodsInfo(parserinfo):
        def month(self, name):
            raise AssertionError("custom month must not be imported")
        def convertyear(self, *args):
            raise AssertionError("custom year must not be imported")
        def validate(self, *args):
            raise AssertionError("custom validation must not be imported")
    cfg = import_info(MethodsInfo())
    assert parse("14 Jan 2024", cfg) == datetime(2024, 1, 14)

