"""Causal coverage for removing epoch/date round trips from clock arithmetic."""
from datetime import date, datetime, time, timedelta, tzinfo, timezone
from zoneinfo import ZoneInfo
import pytest
from rstimes import Pydt

@pytest.mark.parametrize('ymd,expected',[
    ((1969,12,30),(1969,12,30)),
    ((1969,12,31),(1970,1,1)),
    ((1970,1,1),(1970,1,1)),
    ((1970,1,2),(1970,1,3)),
])
def test_day_noon_ties_keep_epoch_half_even(ymd,expected):
    assert Pydt(*ymd,12).round('D') == datetime(*expected)

@pytest.mark.parametrize('microseconds',[-1,1,-86_400_000_001,86_400_000_001])
def test_clock_duration_borrows_or_carries_real_days(microseconds):
    start = Pydt(2024,1,1)
    assert start + timedelta(microseconds=microseconds) == datetime(2024,1,1) + timedelta(microseconds=microseconds)

def test_native_combine_keeps_source_pytz_name_resolution():
    import pytz
    result = Pydt.combine(date(2024, 5, 7), time(12, 30, tzinfo=pytz.timezone('America/New_York')))
    assert type(result.tzinfo) is ZoneInfo
    assert result.tzinfo.key == 'America/New_York'
    assert result.hour == 12 and result.utcoffset() == timedelta(hours=-4)

def test_combine_child_keeps_original_constructor_arguments():
    calls = []
    class Child(Pydt):
        def __new__(cls, *args, **kwargs):
            calls.append((args, kwargs))
            return super().__new__(cls, *args, **kwargs)
    value = Child.combine(date(2024, 5, 7), time(12, 30, fold=1))
    assert type(value) is Child
    assert calls == [((2024, 5, 7, 12, 30, 0, 0, None), {'fold': 1})]

@pytest.mark.parametrize('microsecond', [0, 123456])
def test_repr_keeps_python_timezone_text_and_class_name_order(microsecond):
    class Zone(tzinfo):
        def utcoffset(self, dt): return timedelta(0)
        def dst(self, dt): return timedelta(0)
        def __repr__(self):
            Child.__name__ = 'AfterTimezone'
            return 'zone\ud800'
    class Child(Pydt):
        year = property(lambda self: 9999)
    value = Child(2024, 5, 7, 12, 30, 1, microsecond, Zone(), fold=1)
    fields = '2024, 5, 7, 12, 30, 1' + (', 123456' if microsecond else '')
    assert repr(value) == f'AfterTimezone({fields}, tzinfo=zone\ud800, fold=1)'

@pytest.mark.parametrize('fields', [
    (1, 1, 1, 0, 0, 0, 1), (9999, 12, 31, 23, 59, 59, 999999),
    (1969, 12, 31, 23, 59, 59, 999999), (1970, 1, 1, 0, 0, 0, 1),
])
@pytest.mark.parametrize('utc', [False, True])
@pytest.mark.parametrize('zone', [None, timezone(timedelta(hours=5, minutes=30))])
def test_seconds_preserve_python_float_rounding(fields, utc, zone):
    original = datetime(*fields)
    duration = original - datetime(1970, 1, 1)
    microseconds = ((duration.days * 86400 + duration.seconds) * 1000000
                    + duration.microseconds)
    if utc and zone is not None:
        offset = zone.utcoffset(None)
        microseconds -= (offset.days * 86400 + offset.seconds) * 1000000
    assert Pydt(*fields, tzinfo=zone).toseconds(utc) == microseconds * 1e-6

@pytest.mark.parametrize('fold', [0, 1])
def test_astimezone_shared_conversion_keeps_repeated_time(fold):
    source = ZoneInfo('America/New_York')
    value = Pydt(2024, 11, 3, 1, 30, tzinfo=source, fold=fold)
    expected = datetime(2024, 11, 3, 1, 30, tzinfo=source, fold=fold).astimezone(timezone.utc)
    assert value.astimezone(timezone.utc) == expected
    restored = value.astimezone(timezone.utc).astimezone(source)
    assert restored.fold == fold and restored.timestamp() == value.timestamp()

def test_astimezone_custom_source_keeps_builtin_carrier_callbacks():
    seen = []
    class Custom(tzinfo):
        def utcoffset(self, value):
            seen.append(type(value))
            return timedelta(hours=2)
        def dst(self, value): return timedelta(0)
    value = Pydt(2024, 5, 7, 12, tzinfo=Custom())
    seen.clear()
    result = value.astimezone(timezone.utc)
    assert result.hour == 10
    assert seen and all(kind is datetime for kind in seen)
