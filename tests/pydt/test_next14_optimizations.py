"""Protect observable behavior at the new calendar and factory fast paths."""
from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo
import copy

import numpy as np
import pytest
from rstimes import Pydt


def test_short_day_shifts_match_the_standard_calendar_at_month_and_year_edges():
    for year in (1, 1900, 2000, 2024, 9999):
        for month in range(1, 13):
            for day in (1, 28):
                source = Pydt(year, month, day, 23, 59)
                standard = datetime(year, month, day, 23, 59)
                for offset in (-28, -27, -7, -1, 0, 1, 7, 27, 28):
                    try:
                        expected = standard + timedelta(days=offset)
                    except OverflowError:
                        with pytest.raises(OverflowError):
                            source.to_day(offset)
                    else:
                        assert source.to_day(offset) == expected
                        assert source + timedelta(days=offset, minutes=2) == expected + timedelta(minutes=2)


@pytest.mark.parametrize('text,fmt', [
    ('2024-05-07', '%Y-%m-%d'), ('2024-5-7', '%Y-%m-%d'),
    ('2024-02-30', '%Y-%m-%d'), ('0000-01-01', '%Y-%m-%d'),
    ('２０２４-05-07', '%Y-%m-%d'), ('2024-05-07x', '%Y-%m-%d'),
    ('07/05/2024 12:30', '%d/%m/%Y %H:%M'),
])
def test_strptime_retains_standard_acceptance_and_error_reason(text, fmt):
    try:
        expected = datetime.strptime(text, fmt)
    except ValueError as error:
        with pytest.raises(ValueError) as actual:
            Pydt.strptime(text, fmt)
        # Calendar validation is owned by our native kernel. CPython3.14
        # changed its wording; retain the approved reason and public context.
        reason = ('day is out of range for month' if text == '2024-02-30'
                  else 'year 0 is out of range' if text == '0000-01-01'
                  else str(error))
        assert reason in str(actual.value)
    else:
        assert Pydt.strptime(text, fmt) == expected


def test_strptime_still_calls_the_child_fromdatetime_hook():
    calls = []
    class Child(Pydt):
        @classmethod
        def fromdatetime(cls, value, tz=None):
            calls.append(value)
            return super().fromdatetime(value, tz)
    assert type(Child.strptime('2024-05-07', '%Y-%m-%d')) is Child
    assert calls == [datetime(2024, 5, 7)]


def test_calendar_dictionaries_keep_standard_dst_and_utc_rules():
    for zone in (None, timezone.utc, ZoneInfo('America/New_York')):
        value = Pydt(2024, 11, 3, 1, 30, tzinfo=zone, fold=1)
        keys = ('tm_year','tm_mon','tm_mday','tm_hour','tm_min','tm_sec','tm_wday','tm_yday','tm_isdst')
        assert value.timedict() == dict(zip(keys, datetime.timetuple(value)))
        assert value.utctimedict() == dict(zip(keys, datetime.utctimetuple(value)))
        assert tuple(value.timedict()) == keys


def test_explicit_timezone_factories_keep_gap_repair_and_microsecond_flooring():
 zone=ZoneInfo('America/New_York')
 value=np.datetime64('2024-03-10T02:30:00.123456789','ns')
 with pytest.raises(ValueError,match='exist'): Pydt.fromdatetime64(value,tz=zone)
 seconds=(datetime(2024,3,10,2,30,0,123456)-datetime(1970,1,1)).total_seconds()
 with pytest.raises(ValueError,match='exist'): Pydt.fromseconds(seconds,tz=zone)
 # Precision flooring is retained on an existing wall time.
 assert Pydt.fromdatetime64(np.datetime64('2024-03-10T03:30:00.123456789','ns'),tz=zone).microsecond==123456


def test_repr_observes_a_timezone_side_effect_before_reading_the_class_name():
    original = Pydt.__name__
    class Zone(tzinfo):
        def __repr__(self):
            Pydt.__name__ = 'RenamedPydt'
            return 'Zone()'
    try:
        assert repr(Pydt(2024, 5, 7, tzinfo=Zone())) == 'RenamedPydt(2024, 5, 7, 0, 0, 0, tzinfo=Zone())'
    finally:
        Pydt.__name__ = original


def test_copy_state_remains_independent_for_slots_and_dictionary_metadata():
    class Child(Pydt):
        __slots__ = ('extra',)
    value = Child(2024, 5, 7)
    value.extra = ['slot']
    value.other = ['dict']
    for result in (copy.copy(value), copy.deepcopy(value)):
        assert result == value and result.extra == ['slot'] and result.other == ['dict']
        assert result.__dict__ is not value.__dict__


def test_repr_preserves_a_string_subclass_used_for_the_class_name():
    class Name(str):
        def __str__(self): return 'StrName'
        def __format__(self, spec): return 'FormatName'
    original = Pydt.__name__
    try:
        Pydt.__name__ = Name('RealName')
        assert repr(Pydt(2024, 5, 7)) == 'FormatName(2024, 5, 7, 0, 0, 0)'
    finally:
        Pydt.__name__ = original
