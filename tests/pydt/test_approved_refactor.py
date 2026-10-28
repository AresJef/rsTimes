"""Independent expectations for the approved D01-D44 behavior changes."""
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

import pytest

from rstimes import Pydt
from rstimes import Configs, parse_str


def test_utc_factories_return_aware_utc():
    assert Pydt.utcnow().tzinfo is timezone.utc
    assert Pydt.utcfromtimestamp(0) == datetime(1970, 1, 1, tzinfo=timezone.utc)


def test_date_factories_read_stored_fields():
    class Date(date):
        year = property(lambda self: 1900)
        month = property(lambda self: 1)
        day = property(lambda self: 1)

    class Datetime(datetime):
        year = property(lambda self: 1900)
        hour = property(lambda self: 0)
        tzinfo = property(lambda self: None)
        fold = property(lambda self: 0)

    class Time(time):
        hour = property(lambda self: 0)
        fold = property(lambda self: 0)

    assert Pydt.fromdate(Date(2024, 5, 7)) == datetime(2024, 5, 7)
    value = Datetime(2024, 5, 7, 12, tzinfo=timezone.utc, fold=1)
    result = Pydt.fromdatetime(value)
    assert (result.year, result.hour, result.tzinfo, result.fold) == (2024, 12, timezone.utc, 1)
    combined = Pydt.combine(Date(2024, 5, 7), Time(12, fold=1))
    assert (combined.year, combined.month, combined.day, combined.hour, combined.fold) == (2024, 5, 7, 12, 1)


@pytest.mark.parametrize("day", range(6, 13))
def test_weekday_method_matches_datetime_and_official_value(day):
    from cytimes import Pydt as Official

    class Child(Pydt):
        pass

    value = Pydt(2024, 5, day)
    expected = datetime(2024, 5, day).weekday()
    assert callable(value.weekday)
    assert value.weekday() == expected
    assert value.weekday() == Official(2024, 5, day).weekday
    assert Child(2024, 5, day).weekday() == expected


def test_replace_unchanged_preserves_identity_and_avoids_child_constructor():
    class Child(Pydt):
        calls = 0

        def __new__(cls, *args, **kwargs):
            cls.calls += 1
            return super().__new__(cls, *args, **kwargs)

    value = Child(2024, 5, 7, tzinfo=timezone.utc, fold=1)
    assert value.replace() is value
    assert value.replace(year=2024, tzinfo=timezone.utc, fold=1) is value
    assert Child.calls == 1
    changed = value.replace(day=8)
    assert type(changed) is Child and changed.day == 8 and Child.calls == 2


@pytest.mark.parametrize("changes, error", [
    ({"year": "2024"}, TypeError), ({"hour": 12.0}, TypeError),
    ({"day": 0}, ValueError), ({"day": 32}, ValueError),
    ({"fold": 2}, ValueError), ({"fold": "0"}, TypeError),
    ({"year": 0}, ValueError), ({"year": 10000}, ValueError),
    ({"year": 10**100, "tzinfo": "UTC"}, OverflowError),
])
def test_replace_validates_even_for_unchanged_values(changes, error):
    with pytest.raises(error):
        Pydt(2024, 5, 7, 12).replace(**changes)


def test_replace_uses_real_fields_in_child():
    class Child(Pydt):
        year = property(lambda self: 1900)
        fold = property(lambda self: 1)

    value = Child(2024, 5, 7)
    result = value.replace(day=8)
    assert datetime.year.__get__(result) == 2024
    assert datetime.fold.__get__(result) == 0


def test_format_requires_text_and_keeps_empty_default():
    value = Pydt(2024, 5, 7)
    assert format(value, "") == str(value)
    with pytest.raises(TypeError, match="format.*str"):
        value.__format__(None)


def test_internal_queries_ignore_child_attributes():
    class Child(Pydt):
        month = property(lambda self: 1)
        microsecond = property(lambda self: 0)
        tzinfo = property(lambda self: None)

        def dst(self):
            return timedelta(hours=1)

    value = Child(2024, 5, 7, microsecond=123456, tzinfo=timezone.utc)
    assert value.is_month(5) and value.millisecond == 123
    assert value.is_utc() and not value.is_dst()


@pytest.mark.parametrize("zone, fields, earlier, later", [
    ("America/New_York", (2024, 3, 10, 2, 30), (2024, 3, 10, 1, 30), (2024, 3, 10, 3, 30)),
    ("Australia/Lord_Howe", (2024, 10, 6, 2, 15), (2024, 10, 6, 1, 45), (2024, 10, 6, 2, 45)),
    ("Pacific/Apia", (2011, 12, 30, 12, 0), (2011, 12, 29, 12, 0), (2011, 12, 31, 12, 0)),
])
@pytest.mark.parametrize("fold", [0, 1])
def test_gap_constructor_and_wall_arithmetic_agree(zone, fields, earlier, later, fold):
    import numpy as np
    from zoneinfo import ZoneInfo

    expected = datetime(*(later if fold else earlier), tzinfo=ZoneInfo(zone))
    with pytest.raises(ValueError, match='does not exist'):
        Pydt(*fields, tzinfo=zone, fold=fold)
    expected = datetime(*later, tzinfo=ZoneInfo(zone))
    raw = datetime(*fields) - timedelta(days=1)
    start = Pydt.fromdatetime(raw.replace(tzinfo=ZoneInfo(zone), fold=fold))
    for result in (start + timedelta(days=1), start.add(days=1),
                   start + np.timedelta64(1, "D")):
        assert result == expected and result.fold == 0
    if zone == "Pacific/Apia":
        # P10.4 selects a real target day; P12.1 separately preserves the
        # established Pydt arithmetic interpretation above.
        with pytest.raises(ValueError, match="calendar day"):
            start.to_day(1)
    else:
        result = start.to_day(1)
        assert result == expected and result.fold == 0


@pytest.mark.parametrize("fold", [0, 1])
def test_repeated_time_arithmetic_preserves_input_fold(fold):
    from zoneinfo import ZoneInfo
    start = Pydt(2024, 11, 2, 1, 30, tzinfo=ZoneInfo("America/New_York"), fold=fold)
    result = start + timedelta(days=1)
    assert (result.day, result.hour, result.fold) == (3, 1, 0)
    assert result.utcoffset() == timedelta(hours=-4)


def test_parser_default_fold_is_zero_and_explicit_datetime_selects_later():
    cfg = Configs()
    cfg.add_tzone("America/New_York")
    text = "2024-11-03 01:30 America/New_York"
    assert parse_str(text, ignoretz=False, cfg=cfg).fold == 0
    assert parse_str(text, default=datetime(2024, 1, 1, fold=1), ignoretz=False, cfg=cfg).fold == 1
    assert parse_str("2024-03-10 02:30 America/New_York", ignoretz=False, cfg=cfg).hour == 2


def test_timezone_protocol_uses_stored_zone_in_child():
    class Child(Pydt):
        def utcoffset(self):
            raise AssertionError("not the stored timezone protocol")

    value = Child(2024, 5, 7, tzinfo=timezone(timedelta(hours=2)))
    assert value.utcoffset_seconds() == 7200
    assert value.tomicroseconds(utc=True) == Pydt(2024, 5, 6, 22).tomicroseconds()
    assert value.tz_convert(timezone.utc).hour == 22


@pytest.mark.parametrize("zone, fields", [
    ("Europe/Berlin", (2024, 3, 31, 4, 30)),
    ("Australia/Lord_Howe", (2024, 10, 6, 13, 15)),
    ("America/New_York", (2024, 3, 9, 21, 30)),
])
def test_instant_conversions_do_not_normalize_utc_intermediate(zone, fields):
    from zoneinfo import ZoneInfo

    class Child(Pydt):
        pass

    expected = datetime(*fields, tzinfo=ZoneInfo(zone)).astimezone(timezone.utc)
    for cls in (Pydt, Child):
        value = cls(*fields, tzinfo=zone)
        for result in (value.astimezone(timezone.utc), value.tz_convert(timezone.utc),
                       value.tz_switch(timezone.utc)):
            assert result == expected and type(result) is cls


def test_custom_timezone_construction_does_not_run_callbacks():
    class Deferred(tzinfo):
        def utcoffset(self, dt):
            raise AssertionError("not needed merely to store tzinfo")

        def dst(self, dt):
            raise AssertionError("not needed merely to store tzinfo")

    zone = Deferred()
    for value in (Pydt(1, 1, 1, tzinfo=zone), Pydt.fromordinal(1, zone),
                  Pydt.fromdayofyear(1, 1, zone), Pydt.frommicroseconds(0, zone)):
        assert datetime.tzinfo.__get__(value) is zone


@pytest.mark.parametrize("year, week, weekday, expected", [
    (2024, 99, 99, datetime(2024, 12, 29)),
    (2020, 99, 7, datetime(2021, 1, 3)),
    (2024, 1, 1, datetime(2024, 1, 1)),
])
def test_iso_convenience_upper_bounds(year, week, weekday, expected):
    assert Pydt.fromisocalendar(year, week, weekday) == expected


@pytest.mark.parametrize("args", [(2024, 0, 1), (2024, 1, 0), (0, 1, 1)])
def test_iso_convenience_low_values_raise(args):
    with pytest.raises(ValueError):
        Pydt.fromisocalendar(*args)


@pytest.mark.parametrize("value", ["1", b"1", bytearray(b"1")])
def test_seconds_rejects_text(value):
    with pytest.raises(TypeError, match="fromseconds.*seconds"):
        Pydt.fromseconds(value)


def test_relativedelta_right_operand_retains_full_dateutil_fields():
    from dateutil.relativedelta import relativedelta, MO

    class Child(Pydt):
        pass

    value = Child(2024, 5, 7, 12)
    assert value + relativedelta(weekday=MO(2)) == datetime(2024, 5, 20, 12)
    assert value - relativedelta(days=2) == datetime(2024, 5, 5, 12)
    assert type(value + relativedelta(months=1)) is Child
    assert Pydt(2023, 3, 1) + relativedelta(years=1, leapdays=1) == datetime(2024, 3, 2)
    reverse = relativedelta(weekday=MO(2)) + value
    assert reverse == value + relativedelta(weekday=MO(2))
    assert type(reverse) is Child


def test_relativedelta_keeps_fold_for_local_calendar_arithmetic():
    from dateutil.relativedelta import relativedelta
    value = Pydt(2024, 3, 9, 2, 30, tzinfo="America/New_York", fold=1)
    result = value + relativedelta(days=1)
    assert (result.day, result.hour, result.fold) == (10, 3, 0)
    value = Pydt(2024, 11, 2, 1, 30, tzinfo="America/New_York", fold=1)
    assert (value + relativedelta(days=1)).fold == 0


@pytest.mark.parametrize("value", [0, -1])
def test_day_of_year_and_leap_query_reject_meaningless_low_values(value):
    with pytest.raises(ValueError):
        Pydt.fromdayofyear(2024, value)
    with pytest.raises(ValueError):
        Pydt(2024, 5, 7).leap_bt_year(value)


def test_fromdate_keeps_date_only_child_constructor_signature():
    class DateOnly(Pydt):
        def __new__(cls, year, month, day, *, tzinfo=None):
            return super().__new__(cls, year, month, day, tzinfo=tzinfo)

    value = DateOnly.fromdate(date(2024, 5, 7))
    assert type(value) is DateOnly
    assert value == datetime(2024, 5, 7)


def test_fromdatetime_converts_existing_pytz_by_its_zone_name():
    pytz = pytest.importorskip('pytz')
    zone = pytz.timezone('America/New_York')
    original = zone.localize(datetime(2024, 5, 7, 15))
    value = Pydt.fromdatetime(original)
    assert isinstance(value.tzinfo, ZoneInfo)
    assert value.tzinfo.key == 'America/New_York'
    assert (value.year, value.month, value.day, value.hour) == (2024, 5, 7, 15)
