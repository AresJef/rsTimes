"""F15-F18: real timezone adapters and validated UTC consumers."""

from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from rstimes import Delta, Pydt, parse_to_epoch


class Child(Pydt):
    pass


class Constant(tzinfo):
    def __init__(self, amount):
        self.amount = amount

    def utcoffset(self, value):
        return self.amount

    def dst(self, value):
        return timedelta(0)


class CustomUTC(tzinfo):
    def utcoffset(self, value): return timedelta(0)
    def dst(self, value): return timedelta(0)
    def fromutc(self, value): return value


@pytest.mark.parametrize("cls", [Pydt, Child])
@pytest.mark.parametrize("route", ["epoch", "as_utc", "as_custom", "convert", "convert_custom", "switch", "utc_dict", "offset"])
@pytest.mark.parametrize("amount", [pd.Timedelta(np.timedelta64(86400000000000, "s")),
                                     pd.Timedelta(np.timedelta64(-86400000000000, "s")),
                                     timedelta(days=2),
                                     pd.Timedelta(-86400000000000 + 1, "ns")])
def test_every_utc_consumer_rejects_original_or_reduced_offset_boundary(cls, route, amount):
    value = cls(2024, 1, 1, 12, 30, tzinfo=Constant(amount))
    calls = {"epoch": lambda: parse_to_epoch(value),
             "as_utc": lambda: value.astimezone(timezone.utc),
             "as_custom": lambda: value.astimezone(CustomUTC()),
             "convert": lambda: value.tz_convert(timezone.utc),
             "convert_custom": lambda: value.tz_convert(CustomUTC()),
             "switch": lambda: value.tz_switch(timezone.utc),
             "utc_dict": value.utctimedict, "offset": value.utcoffset_seconds}
    with pytest.raises(ValueError):
        calls[route]()


@pytest.mark.parametrize("cls", [Pydt, Child])
@pytest.mark.parametrize("amount", [timedelta(hours=2), pd.Timedelta(hours=2)])
def test_valid_utc_consumers_keep_clock_and_subclass(cls, amount):
    value = cls(2024, 1, 1, 12, 30, tzinfo=Constant(amount))
    for result in [value.astimezone(timezone.utc), value.astimezone(CustomUTC()),
                   value.tz_convert(timezone.utc), value.tz_switch(timezone.utc)]:
        assert type(result) is cls
        assert (result.hour, result.minute) == (10, 30)
    assert value.utctimedict()["tm_hour"] == 10
    assert value.utcoffset_seconds() == 7200


@pytest.mark.parametrize("cls", [Pydt, Child])
def test_instant_factories_validate_but_wall_factories_do_not_consume_offset(cls):
    zone = Constant(pd.Timedelta(np.timedelta64(86400000000000, "s")))
    for call in [lambda: cls.now(zone), lambda: cls.fromtimestamp(0, zone)]:
        with pytest.raises(ValueError): call()
    assert cls.fromseconds(0, zone).tzinfo is zone
    assert cls.frommicroseconds(0, zone).tzinfo is zone


@pytest.mark.parametrize("cls", [Pydt, Child])
@pytest.mark.parametrize("is_dst, fold", [(True, 0), (False, 1)])
def test_pytz_copy_preserves_selected_instant_and_explicit_replacement(cls, is_dst, fold):
    pytz = pytest.importorskip("pytz")
    zone = pytz.timezone("America/New_York")
    original = zone.localize(datetime(2024, 11, 3, 1, 30), is_dst=is_dst)
    result = cls.fromdatetime(original)
    assert type(result) is cls and type(result.tzinfo) is ZoneInfo
    assert result.fold == fold and result.timestamp() == original.timestamp()
    parsed = cls.parse(original)
    assert parsed.fold == fold and parsed.timestamp() == original.timestamp()
    combined = cls.combine(original.date(), original)
    assert combined.fold == fold and combined.timestamp() == original.timestamp()
    replaced = cls.fromdatetime(original, timezone.utc)
    assert replaced.hour == 1 and replaced.fold == original.fold


def test_real_pytz_child_is_adapted_even_in_application_module():
    pytz = pytest.importorskip("pytz")
    class ApplicationZone(pytz.tzinfo.StaticTzInfo):
        zone = "Asia/Shanghai"
        _utcoffset = timedelta(hours=8)
        _tzname = "CST"
    result = Pydt(2024, 1, 1, tzinfo=ApplicationZone())
    assert type(result.tzinfo) is ZoneInfo and result.tzinfo.key == "Asia/Shanghai"
    class OrdinaryZone(Constant):
        __module__ = "pytz.application"
    ordinary = OrdinaryZone(timedelta(hours=2))
    assert Pydt(2024, 1, 1, tzinfo=ordinary).tzinfo is ordinary
    with pytest.raises(ValueError):
        Pydt(2024, 1, 1, tzinfo=pytz.FixedOffset(120))


def test_none_offset_source_uses_strict_local_time(monkeypatch):
    import rstimes.pydt as module
    class NoneOffset(tzinfo):
        def utcoffset(self, value): return None
        def dst(self, value): return None
    monkeypatch.setattr(module, "_local_timezone", lambda: ZoneInfo("America/New_York"))
    gap = Pydt(2024, 3, 10, 2, 30, tzinfo=NoneOffset())
    with pytest.raises(ValueError, match="exist"):
        gap.astimezone(timezone.utc)
    repeated = Pydt(2024, 11, 3, 1, 30, tzinfo=NoneOffset(), fold=1)
    assert repeated.astimezone(timezone.utc) == datetime(2024, 11, 3, 6, 30, tzinfo=timezone.utc)


@pytest.mark.parametrize("kind", ["base", "child", "dateutil", "wrapper"])
def test_calendar_target_keeps_matching_second_occurrence(kind):
    base = ZoneInfo("America/New_York")
    class Region(ZoneInfo): pass
    class Wrapper(tzinfo):
        def utcoffset(self, value):
            return base.utcoffset(datetime.replace(value, tzinfo=base))
        def dst(self, value):
            return base.dst(datetime.replace(value, tzinfo=base))
        def fromutc(self, value):
            returned = base.fromutc(datetime.replace(value, tzinfo=base))
            return datetime.replace(returned, tzinfo=self)
    if kind == "dateutil":
        from dateutil.tz import gettz
        zone = gettz("America/New_York")
    else:
        zone = {"base": base, "child": Region("America/New_York"), "wrapper": Wrapper()}[kind]
    value = Pydt(2024, 11, 3, 1, 30, tzinfo=zone, fold=1)
    for result in [value + Delta(minutes=1), value.add(minutes=1), value + timedelta(minutes=1)]:
        assert result.fold == 1 and (result.hour, result.minute) == (1, 31)
        assert result.utcoffset() == timedelta(hours=-5)
    unique = value.add(hours=2)
    assert unique.hour == 3 and unique.fold == 0


@pytest.mark.parametrize("source_fold", [0, 1])
def test_builtin_fromutc_calendar_target_uses_its_valid_occurrence(source_fold):
    class FoldOffset(tzinfo):
        def utcoffset(self, value):
            return timedelta(hours=1 if value.fold else 2)

        def dst(self, value):
            return timedelta(0)

    value = Pydt(2024, 5, 7, 15, 30, tzinfo=FoldOffset(), fold=source_fold)
    result = value.to_day(1)
    assert (result.day, result.hour, result.minute, result.fold) == (8, 15, 30, 0)


def test_calendar_reads_fromutc_after_the_offset_callback():
    class Changing(Constant):
        armed = False

        def utcoffset(self, value):
            if self.armed:
                def failed(value):
                    raise RuntimeError("updated fromutc")
                self.fromutc = failed
            return super().utcoffset(value)

    zone = Changing(timedelta(hours=2))
    value = Pydt(2024, 5, 7, 15, 30, tzinfo=zone)
    zone.armed = True
    with pytest.raises(RuntimeError, match="updated fromutc"):
        value.to_day(1)


@pytest.mark.parametrize("zone, fields, fold, unit, expected, expected_fold", [
    ("America/New_York", (2024, 11, 3, 1, 59, 50), 0, "m", (2024, 11, 3, 1, 0, 0), 1),
    ("America/New_York", (2024, 11, 3, 1, 59, 59, 700000), 0, "s", (2024, 11, 3, 1, 0, 0), 1),
    ("America/New_York", (2024, 11, 3, 1, 30), 0, "h", (2024, 11, 3, 1, 0, 0), 1),
    ("America/Havana", (2024, 11, 3, 0, 0), 1, "D", (2024, 11, 3, 0, 0, 0), 0),
    ("America/Havana", (2024, 11, 3, 0, 0), 1, "h", (2024, 11, 3, 0, 0, 0), 1),
    ("Australia/Lord_Howe", (2024, 10, 6, 1, 59, 50), 0, "h", (2024, 10, 6, 2, 30, 0), 0),
    ("Pacific/Apia", (2011, 12, 29, 23, 59, 50), 0, "D", (2011, 12, 31, 0, 0, 0), 0),
])
def test_snap_compares_real_adjacent_periods(zone, fields, fold, unit, expected, expected_fold):
    zone = ZoneInfo(zone)
    value = Pydt(*fields, tzinfo=zone, fold=fold)
    result = value.snap(unit)
    target = datetime(*expected, tzinfo=zone, fold=expected_fold)
    assert result.timestamp() == target.timestamp()
    assert (result.year, result.month, result.day, result.hour, result.minute, result.second) == expected
    assert result.fold == expected_fold
    if fields[:len(expected)] == expected and fold == expected_fold:
        assert result is value


@pytest.mark.parametrize("zone", [ZoneInfo("America/New_York"), Constant(None)])
@pytest.mark.parametrize("fold", [0, 1])
def test_boundary_queries_ignore_fold_when_it_is_not_a_different_instant(zone, fold):
    value = Pydt(2024, 1, 1, tzinfo=zone, fold=fold)
    for unit in ["Y", "Q", "M", "W", "D", "h", "m", "s", "ms", "us", "ns"]:
        assert value.is_start_of(unit)
        assert value.is_end_of(unit) is (unit in ("us", "ns"))
    assert value.snap("D") is value
    assert value.snap("us") is value and value.snap("ns") is value


def test_repeated_day_and_clock_periods_keep_distinct_boundary_meanings():
    zone = ZoneInfo("America/Havana")
    value = Pydt(2024, 11, 3, tzinfo=zone, fold=1)
    assert not value.is_start_of("D")
    assert value.to_start_of("D").fold == 0
    assert value.is_start_of("h")
    assert value.to_start_of("h") is value


