"""Independent expectations for the approved Parser behavior revision."""
from datetime import date, datetime, timedelta, timezone
import copy
import pickle

import pytest

from rstimes import Configs, parse_str as parse
from rstimes.errors import ParseError


@pytest.mark.parametrize("isoformat", [True, False])
@pytest.mark.parametrize("offset", ["+08:00", "-05:30"])
@pytest.mark.parametrize("ignoretz", [True, False])
@pytest.mark.parametrize("strict", [False, True])
def test_minute_precision_offset_keeps_clock(isoformat, offset, ignoretz, strict):
    seconds = 28800 if offset == "+08:00" else -19800
    expected = datetime(2024, 5, 7, 15, 30)
    if not ignoretz:
        expected = expected.replace(tzinfo=timezone(timedelta(seconds=seconds)))
    assert parse("2024-05-07T15:30" + offset,
                 isoformat=isoformat, ignoretz=ignoretz, strict=strict) == expected


def test_strict_follows_isoformat_and_defaults_to_false():
    value = datetime(2024, 5, 7)
    assert parse("2024-05-07") == value
    assert parse("2024-05-07", strict=False) == value
    assert parse("2024-05-07", strict=True) == value
    assert parse("2024-05-07", None, None, None, True, True, False, None, None) == value


@pytest.mark.parametrize("text,expected,field", [
    ("2024-01-02 12:99", datetime(2024, 1, 2, 12, 59), "minute"),
    ("2024-01-02 25:30", datetime(2024, 1, 2, 23, 30), "hour"),
    ("2024-01-02 12:30:99", datetime(2024, 1, 2, 12, 30, 59), "second"),
    ("2024-02-30", datetime(2024, 2, 29), "day"),
    ("2024-13-40", datetime(2024, 12, 31), "month"),
    ("2024-00-00", None, "month"),
    ("0000-01-02", None, "year"),
])
@pytest.mark.parametrize("isoformat", [False, True])
def test_explicit_invalid_fields_clamp_or_raise(text, expected, field, isoformat):
    if expected is None:
        with pytest.raises(ValueError, match=field): parse(text, isoformat=isoformat)
    else:
        assert parse(text, isoformat=isoformat) == expected
    with pytest.raises(ValueError, match=field):
        parse(text, isoformat=isoformat, strict=True)


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("fallback", [date(2024, 1, 31), datetime(2024, 1, 31, 18, 45, tzinfo=timezone.utc)])
def test_default_day_can_clip_in_both_modes(strict, fallback):
    assert parse("February 2024", default=fallback, strict=strict) == datetime(2024, 2, 29)


@pytest.mark.parametrize("fallback,short,year", [
    (date(2000, 1, 1), "70", 1970),
    (date(2026, 1, 1), "70", 2070),
    (date(2026, 1, 1), "75", 2075),
    (datetime(2026, 1, 1, 23), "76", 1976),
])
def test_short_year_uses_default_reference(fallback, short, year):
    assert parse("01/01/" + short, default=fallback, yearfirst=False) == datetime(year, 1, 1)


def test_short_year_errors_explain_valid_usage():
    with pytest.raises(ParseError, match="strict=False.*default"):
        parse("01/01/70", strict=True, default=date(2000, 1, 1))
    with pytest.raises(ParseError, match="default.*four-digit"):
        parse("01/01/70", strict=False)
    assert parse("May 7", default=date(2024, 1, 1), strict=True) == datetime(2024, 5, 7)


def test_calendar_year_is_not_a_clock_before_a_skip_word():
    assert parse("2 de agosto de 2023 a las 12:01", default=date(1, 1, 1), yearfirst=False) == datetime(2023, 8, 2, 12, 1)


@pytest.mark.parametrize('isoformat', [False, True])
@pytest.mark.parametrize('strict', [False, True])
@pytest.mark.parametrize('text,expected', [
    ('0001-02-03', datetime(1, 2, 3)),
    ('00010203', datetime(1, 2, 3)),
    ('00010203123456', datetime(1, 2, 3, 12, 34, 56)),
    ('0001', datetime(1, 5, 7)),
])
def test_written_four_digit_year_is_not_a_short_year(text, expected, isoformat, strict):
    assert parse(text, default=date(2026, 5, 7), isoformat=isoformat, strict=strict) == expected


@pytest.mark.parametrize("text,expected", [
    ("2024-01-02 1h 1h", datetime(2024, 1, 2, 1)),
    ("2024-01-02 15h 3 pm", datetime(2024, 1, 2, 15)),
    ("2024-01-02 15h 3:00 pm", datetime(2024, 1, 2, 15)),
    ("Jan 2 2024 Jan 2 2024", datetime(2024, 1, 2)),
    ("2024-01-02 2024-01-02", datetime(2024, 1, 2)),
    ("2024-01-02T12:30 1s", datetime(2024, 1, 2, 12, 30, 1)),
])
def test_equivalent_repeated_fields_are_accepted(text, expected):
    assert parse(text, strict=True) == expected


@pytest.mark.parametrize("text,expected,field", [
    ("2024-01-02 1h 2h", datetime(2024, 1, 2, 2), "hour"),
    ("2024-01-02 3m 4m", datetime(2024, 1, 2, 0, 4), "minute"),
    ("2024-01-02 5s 6s", datetime(2024, 1, 2, 0, 0, 6), "second"),
    ("Jan 2 2024 Feb 2 2024", datetime(2024, 2, 2), "month"),
    ("2024-01-02 2025-01-03", datetime(2025, 1, 3), "year"),
    ("2024-01-02 2024-01-03", datetime(2024, 1, 3), "day"),
    ("2024-01-02T01:00:00 2h", datetime(2024, 1, 2, 2), "hour"),
])
def test_conflicts_raise_or_use_last_value(text, expected, field):
    assert parse(text) == expected
    with pytest.raises(ParseError, match=field):
        parse(text, strict=True)


def test_weekday_checks_explicit_dates_and_preserves_inference():
    with pytest.raises(ValueError, match="weekday"):
        parse("Mon 2024-01-02", strict=True)
    assert parse("Mon 2024-01-02") == datetime(2024, 1, 1)
    assert parse("Tue 2024-01-02", strict=True) == datetime(2024, 1, 2)
    assert parse("Mon", default=date(2024, 1, 2), strict=True) == datetime(2024, 1, 1)


@pytest.mark.parametrize("strict", [False, True])
def test_strict_does_not_require_recognizing_unknown_words(strict):
    assert parse("2024-01-02 banana", strict=strict) == datetime(2024, 1, 2)
    assert parse("2024-01-02 12:00:00 LCL", ignoretz=False, strict=strict) == datetime(2024, 1, 2, 12)


@pytest.mark.parametrize("method,value", [("month", 1.9), ("weekday", 1.0), ("hms", 1.5), ("ampm", 0.5), ("tzoffset", 5.5)])
def test_config_numeric_entries_do_not_truncate(method, value):
    cfg = Configs()
    with pytest.raises(TypeError):
        getattr(cfg, "add_" + method)("customalias", value)
    with pytest.raises(TypeError):
        getattr(cfg, "set_" + method)({"customalias": value})
    before = cfg.__reduce__()[2]
    state = cfg.__reduce__()[2]
    index = {"tzoffset": 3, "month": 4, "weekday": 5, "hms": 6, "ampm": 7}[method]
    state[4][index]["customalias"] = value
    with pytest.raises(TypeError):
        cfg.__setstate__(state)
    assert cfg.__reduce__()[2] == before


@pytest.mark.parametrize("offset", [-86400, 86400])
def test_timezone_endpoints_rejected_at_configuration(offset):
    cfg = Configs()
    before = cfg.tzoffset
    with pytest.raises(ValueError):
        cfg.add_tzoffset("customzone", seconds=offset)
    with pytest.raises(ValueError):
        cfg.set_tzoffset({"customzone": offset})
    assert cfg.tzoffset == before


def test_timezone_components_and_confirmed_month_word():
    cfg = Configs()
    with pytest.raises(TypeError):
        cfg.add_tzoffset("customzone", hours=5.5)
    cfg.add_tzoffset("customzone", hours=5, minutes=30)
    assert cfg.tzoffset["customzone"] == 19800
    for word in ("haziran", "Haziran", "HAZIRAN"):
        assert parse("14 " + word + " 2024") == datetime(2024, 6, 14)


@pytest.mark.parametrize("name,value", [("jump", None), ("pertain", None), ("utc", None),
    ("tzoffset", 3600), ("month", 10), ("weekday", 0), ("hms", 0), ("ampm", 1)])
def test_shallow_copy_has_independent_editing(name, value):
    original = Configs(False, True)
    before = getattr(original, name)
    clone = copy.copy(original)
    method = getattr(clone, "add_" + name)
    if name == "tzoffset":
        method("customalias", seconds=value)
    elif value is None:
        method("customalias")
    else:
        method("customalias", value)
    assert "customalias" not in getattr(original, name)
    reverse = getattr(original, "add_" + name)
    if name == "tzoffset":
        reverse("originalalias", seconds=value)
    elif value is None:
        reverse("originalalias")
    else:
        reverse("originalalias", value)
    assert "originalalias" not in getattr(clone, name)
    getattr(original, "del_" + name)("originalalias")
    back = copy.copy(clone)
    getattr(clone, "del_" + name)("customalias")
    assert "customalias" in getattr(back, name)
    getattr(back, "set_" + name)(set() if value is None else {})
    assert getattr(original, name) == before


def test_deepcopy_pickle_and_ordering_stay_independent():
    cfg = Configs(False, True)
    cfg.add_month("harvest", 10)
    for clone in (copy.copy(cfg), copy.deepcopy(cfg), pickle.loads(pickle.dumps(cfg))):
        clone.__init__(True, False)
        clone.clear_settings()
        clone.reset_settings()
        assert cfg.yearfirst is False and cfg.dayfirst is True
        assert cfg.month["harvest"] == 10


@pytest.mark.parametrize("strict", [False, True])
def test_repeated_timezone_fields(strict):
    text = "2024-01-02 12:00:00 +01:00 +02:00"
    if strict:
        with pytest.raises(ParseError, match="timezone"):
            parse(text, ignoretz=False, strict=True)
    else:
        assert parse(text, ignoretz=False).utcoffset() == timedelta(hours=2)
    assert parse("2024-01-02 12:00:00 +01:00 +01:00", ignoretz=False, strict=strict).utcoffset() == timedelta(hours=1)


@pytest.mark.parametrize("text,expected", [
    ("Meet me at 3:01AM on December 3rd, 2003 at the AM/PM on Sunset", datetime(2003, 12, 3, 3, 1)),
    ("On June 8th, 2020, I am going to be the first man on Mars", datetime(2020, 6, 8)),
])
def test_prose_words_do_not_become_repeated_calendar_or_clock(text, expected):
    assert parse(text) == expected


def test_explicit_middle_year_keeps_its_calendar_role():
    for strict in (False, True):
        assert parse('31 2024 12', strict=strict) == datetime(2024, 12, 31)


def test_repeated_seconds_replace_fraction_and_validate_conflict():
    assert parse('2024-01-02 1.5s 1s') == datetime(2024, 1, 2, 0, 0, 1)
    with pytest.raises(ParseError, match='microsecond'):
        parse('2024-01-02 1.5s 1s', strict=True)
    assert parse('2024-01-02T12:00:01.5 1.5s', strict=True) == datetime(2024, 1, 2, 12, 0, 1, 500000)
    with pytest.raises(ParseError, match='microsecond'):
        parse('2024-01-02T12:00:01.5 1.25s', strict=True)
