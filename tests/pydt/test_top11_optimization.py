"""Preserve observable hooks when moving Pydt field handling into Rust."""
from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

import pytest

from rstimes import Pydt


@pytest.mark.parametrize("target", [timezone.utc, ZoneInfo("America/New_York")])
@pytest.mark.parametrize("fields", [
    (2024, 3, 10, 7, 30),
    (2024, 11, 3, 5, 30),
    (2024, 11, 3, 6, 30),
])
def test_child_conversion_calls_only_the_final_constructor(target, fields):
    calls = []

    class Child(Pydt):
        def __new__(cls, *args, **kwargs):
            calls.append((args, kwargs))
            return super().__new__(cls, *args, **kwargs)

    source = timezone(timedelta(hours=1))
    value = Child(*fields, tzinfo=source)
    calls.clear()
    expected = datetime(*fields, tzinfo=source).astimezone(target)
    result = value.astimezone(target)
    assert type(result) is Child and result == expected
    assert calls == [(
        (expected.year, expected.month, expected.day, expected.hour,
         expected.minute, expected.second, expected.microsecond),
        {"tzinfo": target, "fold": expected.fold},
    )]


def test_replacement_indexes_each_supplied_value_once_in_field_order():
    calls = []

    class Index:
        def __init__(self, label, value):
            self.label, self.value = label, value

        def __index__(self):
            calls.append(self.label)
            return self.value

    value = Pydt(2024, 5, 7)
    result = value.replace(year=Index("year", 2024), day=Index("day", 7),
                           fold=Index("fold", 0))
    assert result is value and calls == ["year", "day", "fold"]


def test_tz_switch_validates_dynamic_boolean_before_no_target_return():
    calls = []

    class Boolean:
        def __bool__(self):
            calls.append(True)
            return False

    value = Pydt(2024, 5, 7)
    with pytest.raises(TypeError):
        value.tz_switch(None, naive=Boolean())
    assert calls == []
    with pytest.raises(TypeError):
        value.tz_switch(None, naive="False")


def test_child_conversion_keeps_type_dependent_timezone_carrier():
    class Custom(tzinfo):
        def utcoffset(self, value):
            return timedelta(hours=1 if type(value) is datetime else 2)

        def dst(self, value):
            return timedelta(0)

    class Child(Pydt):
        pass

    value = Child(2024, 5, 7, 12, tzinfo=Custom())
    assert value.tz_convert(timezone.utc) == value.astimezone(timezone.utc)
    assert value.tz_convert(timezone.utc).hour == 11
