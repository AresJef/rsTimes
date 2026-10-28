"""Important supported-use parser repairs and their existing correct controls."""

import ast
from datetime import date, datetime, timedelta, timezone
from itertools import permutations
from pathlib import Path
from zoneinfo import available_timezones

import pytest

from rstimes import Configs, Pydt, parse, parse_str, parse_to_epoch
import rstimes.parser as parser_module


ENTRIES = (parse_str, parse, parse_to_epoch, Pydt.parse)


def expected_for(entry, value):
    """Encode an independently specified datetime for the integer exit."""
    if entry is parse_to_epoch:
        base = value.replace(tzinfo=None) - datetime(1970, 1, 1)
        offset = value.utcoffset() or timedelta(0)
        return (base - offset) // timedelta(microseconds=1)
    return value


@pytest.mark.parametrize("order", list(permutations("ymd")))
@pytest.mark.parametrize("sep", ["-", "/", " "])
@pytest.mark.parametrize("isoformat", [False, True])
@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("prefix", ["", "2024-02-14 ", "2024-01-02 12:34:56 "])
def test_complete_named_calendar_commits_roles_together(order, sep, isoformat, strict, prefix):
    fields = {"y": "2024", "m": "Feb", "d": "14"}
    text = prefix + sep.join(fields[k] for k in order)
    if strict and prefix.startswith("2024-01-02"):
        with pytest.raises(ValueError, match="month|day"):
            parse_str(text, isoformat=isoformat, strict=True)
    else:
        clock = (12, 34, 56) if "12:34:56" in prefix else (0, 0, 0)
        assert parse_str(text, isoformat=isoformat, strict=strict) == datetime(2024, 2, 14, *clock)


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("isoformat", [False, True])
@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("text, expected", [
    ("2024-Jan-001", datetime(2024, 1, 1)),
    ("001-Jan-2024", datetime(2024, 1, 1)),
    ("2024-014-Feb", datetime(2024, 2, 14)),
    ("Jan-001-2024", datetime(2024, 1, 1)),
])
def test_complete_named_calendar_keeps_written_day(entry, isoformat, strict, text, expected):
    actual = entry(text, default=datetime(2024, 6, 15), isoformat=isoformat, strict=strict)
    assert actual == expected_for(entry, expected)


@pytest.mark.parametrize("text", ["2024-Jan-32", "32-Jan-2024", "Jan-32-2024"])
@pytest.mark.parametrize("isoformat", [False, True])
def test_named_calendar_range_reports_day_not_a_replacement_year(text, isoformat):
    assert parse_str(text, default=date(2024, 6, 15), isoformat=isoformat) == datetime(2024, 1, 31)
    with pytest.raises(ValueError, match="day"):
        parse_str(text, default=date(2024, 6, 15), isoformat=isoformat, strict=True)


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("isoformat", [False, True])
@pytest.mark.parametrize("strict", [False, True])
def test_repeated_calendar_never_creates_a_clock_or_timezone(entry, isoformat, strict):
    actual = entry("2024-01-02 2024-Jan-02", ignoretz=False, isoformat=isoformat, strict=strict)
    assert actual == expected_for(entry, datetime(2024, 1, 2))
    if entry is not parse_to_epoch:
        assert actual.tzinfo is None


@pytest.mark.parametrize("isoformat", [False, True])
def test_changed_complete_calendar_obeys_existing_strict_policy(isoformat):
    assert parse_str("2024-01-02 2025-Feb-03", isoformat=isoformat) == datetime(2025, 2, 3)
    with pytest.raises(ValueError, match="year"):
        parse_str("2024-01-02 2025-Jan-02", strict=True, isoformat=isoformat)


@pytest.mark.parametrize("strict", [False, True])
def test_named_calendar_uses_configured_months_and_leaves_real_timezone(strict):
    cfg = Configs()
    cfg.add_month("auditmonth", 2)
    expected = datetime(2024, 2, 14, 12, 34, 56, tzinfo=timezone(timedelta(hours=8)))
    actual = parse_str("2024-014-auditmonth 12:34:56 +08:00", cfg=cfg, strict=strict, ignoretz=False)
    assert actual == expected and actual.utcoffset() == timedelta(hours=8)


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("isoformat", [False, True])
@pytest.mark.parametrize("tail, clock", [
    ("12:00 1 PM", (13, 0, 0)),
    ("12:00 1h30", (1, 30, 0)),
    ("12:00 30m15", (12, 30, 15)),
    ("12:00 1h30.5", (1, 30, 30)),
])
def test_explicit_clock_tail_is_not_filtered_out(entry, isoformat, tail, clock):
    expected = datetime(2024, 1, 2, *clock)
    assert entry("2024-01-02 " + tail, isoformat=isoformat) == expected_for(entry, expected)


@pytest.mark.parametrize("isoformat", [False, True])
@pytest.mark.parametrize("tail, field", [("12:00 1 PM", "hour"), ("01:00 1h30", "minute")])
def test_explicit_clock_tail_preserves_strict_conflicts(isoformat, tail, field):
    with pytest.raises(ValueError, match=field):
        parse_str("2024-01-02 " + tail, isoformat=isoformat, strict=True)


@pytest.mark.parametrize("isoformat", [False, True])
@pytest.mark.parametrize("tail, expected", [("13:00 1 PM", datetime(2024, 1, 2, 13)),
                                          ("01:30 1h30", datetime(2024, 1, 2, 1, 30))])
def test_equivalent_clock_tail_is_accepted(isoformat, tail, expected):
    assert parse_str("2024-01-02 " + tail, isoformat=isoformat, strict=True) == expected


@pytest.mark.parametrize("isoformat", [False, True])
def test_clock_tail_uses_existing_ampm_alias_and_boundaries(isoformat):
    cfg = Configs()
    cfg.add_ampm("afternoon", 1)
    assert parse_str("2024-01-02 12:00 1 afternoon", cfg=cfg, isoformat=isoformat) == datetime(2024, 1, 2, 13)
    assert parse_str("2024-01-02 0 PM", isoformat=isoformat) == datetime(2024, 1, 2, 13)
    with pytest.raises(ValueError, match="hour"):
        parse_str("2024-01-02 0 PM", isoformat=isoformat, strict=True)


def test_pydt_direct_callers_share_the_repaired_calendar_and_clock():
    obj = Pydt(2024, 1, 2, 13)
    text = "2024-01-02 12:00 1 PM"
    assert obj.diff(text, "h") == 0
    assert obj - text == timedelta(0)
    assert Pydt.combine(date(2024, 1, 2), text) == obj
    assert Pydt.combine(date(2024, 1, 2), "12:00 1 PM") == obj
    assert Pydt.combine("2024-01-02 2024-Jan-02", "13:00") == obj
    assert Pydt(2024, 1, 2) - "2024-01-02 2024-Jan-02" == timedelta(0)


@pytest.mark.parametrize("cls", [Pydt, type("PlainChild", (Pydt,), {})])
def test_available_timezone_property_is_real_and_returns_an_independent_set(cls):
    value = cls(2024, 1, 1)
    actual = value.tz_available
    assert isinstance(actual, set) and all(isinstance(name, str) for name in actual)
    assert actual == available_timezones()
    actual.clear()
    assert value.tz_available == available_timezones()


@pytest.mark.parametrize("flag, value", [("yearfirst", False), ("dayfirst", True)])
def test_configs_stub_agrees_with_readonly_runtime_flags(flag, value):
    node = next(n for n in ast.parse(Path(parser_module.__file__).with_suffix(".pyi").read_text()).body
                if isinstance(n, ast.ClassDef) and n.name == "Configs")
    setters = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == flag
               and any(ast.unparse(d) == flag + ".setter" for d in n.decorator_list)]
    assert setters == []
    with pytest.raises(AttributeError):
        setattr(Configs(), flag, value)


@pytest.mark.parametrize("text, kwargs, expected", [
    ("2024-01-02 12:34:56", {}, datetime(2024, 1, 2, 12, 34, 56)),
    ("2024-01-02 12:34:56 99", {}, datetime(2024, 1, 2, 12, 34, 56)),
    ("2024-01-02 123456", {}, datetime(2024, 1, 2, 12, 34, 56)),
    ("Jan 2024", {"default": date(2024, 6, 15)}, datetime(2024, 1, 15)),
    ("Jan 24", {"default": date(2024, 6, 15)}, datetime(2024, 1, 24)),
    ("2024-01-32", {}, datetime(2024, 1, 31)),
    ("2024-01-001", {}, datetime(2024, 1, 1)),
    ("2024-014", {"strict": True}, datetime(2024, 1, 14)),
    ("2024-014 Feb", {}, datetime(2024, 2, 14)),
    ("03/04/2024", {"cfg": Configs(), "yearfirst": False, "dayfirst": True}, datetime(2024, 4, 3)),
])
def test_existing_correct_parser_controls(text, kwargs, expected):
    assert parse_str(text, **kwargs) == expected


def test_existing_ordinal_conflict_and_configs_constructor_remain_correct():
    with pytest.raises(ValueError, match="month"):
        parse_str("2024-014 Feb", strict=True)
    cfg = Configs(yearfirst=False, dayfirst=True)
    assert (cfg.yearfirst, cfg.dayfirst) == (False, True)
    assert parse_to_epoch("1970-01-01 00:00:00.000001") == 1
    assert parse("2024-01-02") == Pydt.parse("2024-01-02") == datetime(2024, 1, 2)
