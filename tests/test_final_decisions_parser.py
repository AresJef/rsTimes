"""Fixed approved parsing outcomes, including composed explicit fields."""

from datetime import date, datetime
from itertools import product

import pytest

from rstimes import Configs, parse_str, parse_to_epoch


def test_named_date_retains_the_configured_comma_role():
    cfg = Configs()
    cfg.del_jump(",")
    cfg.add_weekday(",", 0)
    text = "May 7, 2024"
    assert parse_str(text, cfg=cfg) == datetime(2024, 5, 6)
    with pytest.raises(ValueError):
        parse_str(text, cfg=cfg, strict=True)


@pytest.mark.parametrize("text, expected", [
    ("2024-01-100", datetime(2024, 1, 31)),
    ("2024-100-02", datetime(2024, 12, 2)),
    ("2024-01-02 12:30:100", datetime(2024, 1, 2, 12, 30, 59)),
    ("2024-01-02 100:30:45", datetime(2024, 1, 2, 23, 30, 45)),
])
@pytest.mark.parametrize("isoformat", [False, True])
def test_complete_numeric_field_is_checked_before_clipping(text, expected, isoformat):
    assert parse_str(text, isoformat=isoformat) == expected
    with pytest.raises(ValueError):
        parse_str(text, isoformat=isoformat, strict=True)


@pytest.mark.parametrize("text, expected", [
    ("2024 Mar 14 0923", datetime(2024, 3, 14, 9, 23)),
    ("Mar 14 2024 123045", datetime(2024, 3, 14, 12, 30, 45)),
    ("2024-01-02 000001h", datetime(2024, 1, 2, 1)),
    ("000001h", datetime(2024, 1, 2, 1)),
    ("2024-01-02 000001.5h", datetime(2024, 1, 2, 1, 30)),
])
@pytest.mark.parametrize("isoformat", [False, True])
def test_explicit_context_selects_the_numeric_role(text, expected, isoformat):
    assert parse_str(text, default=date(2024, 1, 2), isoformat=isoformat) == expected


CALENDARS = [
    ("2024-01-02", (2024, 1, 2)), ("Jan 2 2024", (2024, 1, 2)),
    ("2 Jan 2024", (2024, 1, 2)), ("20240102", (2024, 1, 2)),
    ("2024-W01-2", (2024, 1, 2)), ("2024-002", (2024, 1, 2)),
    ("2024-01-03", (2024, 1, 3)), ("Jan 3 2024", (2024, 1, 3)),
    ("20240103", (2024, 1, 3)), ("2024-W01-3", (2024, 1, 3)),
    ("2024-003", (2024, 1, 3)), ("2024-02-02", (2024, 2, 2)),
    ("2025-01-02", (2025, 1, 2)),
]


@pytest.mark.parametrize("first, second", product(CALENDARS, repeat=2))
@pytest.mark.parametrize("strict, isoformat", product([False, True], repeat=2))
def test_repeated_calendars_compare_actual_dates(first, second, strict, isoformat):
    text = first[0] + " " + second[0]
    if strict and first[1] != second[1]:
        with pytest.raises(ValueError):
            parse_str(text, strict=True, isoformat=isoformat)
    else:
        assert parse_str(text, strict=strict, isoformat=isoformat) == datetime(*second[1])


@pytest.mark.parametrize("strict, isoformat", product([False, True], repeat=2))
def test_later_month_preserves_explicit_year_and_day(strict, isoformat):
    if strict:
        with pytest.raises(ValueError):
            parse_str("2024-01-02 Feb", strict=True, isoformat=isoformat)
    else:
        assert parse_str("2024-01-02 Feb", isoformat=isoformat) == datetime(2024, 2, 2)


def test_later_month_compares_after_dayfirst_resolves_numeric_roles():
    for strict in [False, True]:
        assert parse_str("2024-01-02 Feb", isoformat=False, dayfirst=True,
                         strict=strict) == datetime(2024, 2, 1)


@pytest.mark.parametrize("first, second", product(["12:30:45.1", "123045.1", "12h 30m 45.1s",
                                                   "12:30:45.2", "123045.2", "12h 30m 45.2s"], repeat=2))
@pytest.mark.parametrize("strict, isoformat", product([False, True], repeat=2))
def test_repeated_clock_fractions_share_conflict_rules(first, second, strict, isoformat):
    text = "2024-01-01 " + first + " " + second
    if strict and first[-1 if first[-1] != "s" else -2] != second[-1 if second[-1] != "s" else -2]:
        with pytest.raises(ValueError):
            parse_str(text, strict=True, isoformat=isoformat)
    else:
        microsecond = 100000 if ".1" in second else 200000
        assert parse_str(text, strict=strict, isoformat=isoformat) == datetime(2024, 1, 1, 12, 30, 45, microsecond)


@pytest.mark.parametrize("text, expected", [("99-W01-1", date(1999, 1, 4)),
                                           ("99-W52-7", date(2000, 1, 2)),
                                           ("99-001", date(1999, 1, 1))])
@pytest.mark.parametrize("isoformat", [False, True])
def test_iso_short_year_is_completed_before_calendar_conversion(text, expected, isoformat):
    assert parse_str(text, default=date(1999, 1, 1), isoformat=isoformat).date() == expected
    for default in (None, date(1999, 1, 1)):
        with pytest.raises(ValueError, match="year"):
            parse_str(text, strict=True, default=default, isoformat=isoformat)
    with pytest.raises(ValueError, match="default"):
        parse_str(text, isoformat=isoformat)


@pytest.mark.parametrize("year", [123456, 12345678, 1234567890])
@pytest.mark.parametrize("suffix", ["-001", "-W01-1"])
@pytest.mark.parametrize("isoformat", [False, True])
def test_long_iso_year_is_not_a_compact_calendar(year, suffix, isoformat):
    previous = year - 1
    ordinal = previous * 365 + previous // 4 - previous // 100 + previous // 400 + 1
    if suffix == "-W01-1":
        jan4 = ordinal + 3
        ordinal = jan4 - (jan4 - 1) % 7
    expected = (ordinal - 719163) * 86400000000
    assert parse_to_epoch(str(year) + suffix, isoformat=isoformat) == expected


@pytest.mark.parametrize("raw, am, pm", [(0, 1, 13), (1, 1, 13), (12, 0, 12), (13, 0, 12)])
@pytest.mark.parametrize("gap", ["", " "])
@pytest.mark.parametrize("isoformat", [False, True])
def test_ampm_uses_approved_twelve_hour_range(raw, am, pm, gap, isoformat):
    for flag, expected in [("AM", am), ("PM", pm)]:
        text = f"2024-01-01 {raw}{gap}{flag}"
        assert parse_str(text, isoformat=isoformat).hour == expected
        if raw in (0, 13):
            with pytest.raises(ValueError):
                parse_str(text, strict=True, isoformat=isoformat)


@pytest.mark.parametrize("input_unit, number", [("us", 1704067200000002), ("ms", 1704067200002)])
@pytest.mark.parametrize("sign", [-1, 1])
def test_integral_float_ticks_match_the_actual_integer(input_unit, number, sign):
    number *= sign
    assert parse_to_epoch(float(number), input_unit=input_unit, unit=input_unit) == number
