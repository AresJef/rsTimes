"""Independent values and observable protocols for the bounded diff fast path."""
from datetime import datetime, timedelta, timezone, tzinfo

import pytest

from rstimes import Pydt


@pytest.mark.parametrize('zone', [None, timezone.utc, timezone(timedelta(hours=5, minutes=30))])
@pytest.mark.parametrize('unit,expected', [('D', 6), ('M', 0), ('us', 522000000001)])
def test_exact_pydt_boundary_counts_keep_signed_inclusive_and_absolute(zone, unit, expected):
    left = Pydt(2024, 5, 7, 12, 30, 45, 123456, tzinfo=zone)
    right = Pydt(2024, 5, 1, 11, 30, 45, 123455, tzinfo=zone)
    assert left.diff(right, unit) == expected
    assert right.diff(left, unit) == -expected
    assert left.diff(right, unit, absolute=True, inclusive='both') == expected + 1
    assert right.diff(left, unit, absolute=True, inclusive='neither') == expected - 1


@pytest.mark.parametrize('fields,offset,expected', [
    ((1, 1, 1, 0), 2, -1),
    ((9999, 12, 31, 23), -2, 1),
])
def test_fixed_offset_utc_calendar_bucket_can_cross_datetime_year_limits(fields, offset, expected):
    left = Pydt(*fields, tzinfo=timezone(timedelta(hours=offset)))
    right = Pydt(*fields, tzinfo=timezone.utc)
    assert left.diff(right, 'Y') == expected


def test_custom_zone_receives_original_self_and_copied_builtin_other():
    calls = []

    class Zone(tzinfo):
        def utcoffset(self, value):
            calls.append(value)
            return timedelta(hours=1 if type(value) is datetime else 2)

        def dst(self, value):
            return timedelta(0)

    zone = Zone()
    left = Pydt(2024, 5, 7, 12, tzinfo=zone)
    right = Pydt(2024, 5, 7, 12, tzinfo=zone)
    calls.clear()
    assert left.diff(right, 'h') == -1
    assert len(calls) == 2
    assert calls[0] is left
    assert type(calls[1]) is datetime and calls[1] is not right
    assert datetime.year.__get__(calls[1]) == 2024


def test_datetime_child_keeps_stored_fields_and_has_no_extra_constructor_call():
    constructed = []

    class Child(Pydt):
        year = property(lambda self: 9999)
        tzinfo = property(lambda self: timezone(timedelta(hours=12)))

        def __new__(cls, *args, **kwargs):
            constructed.append(True)
            return super().__new__(cls, *args, **kwargs)

    right = Child(2024, 5, 1)
    left = Pydt(2024, 5, 7)
    constructed.clear()
    assert left.diff(right, 'D') == 6
    assert constructed == []


def test_exact_pydt_uses_stored_timezone_despite_visible_class_property(monkeypatch):
    left = Pydt(2024, 5, 7)
    right = Pydt(2024, 5, 1)

    def unexpected(self):
        raise AssertionError('visible timezone property must not be read')

    monkeypatch.setattr(Pydt, 'tzinfo', property(unexpected))
    assert left.diff(right, 'D') == 6


def test_custom_offset_exception_identity_and_source_order_are_preserved():
    error = RuntimeError('actual offset failure')
    calls = []

    class Zone(tzinfo):
        def utcoffset(self, value):
            calls.append(value)
            raise error

        def dst(self, value):
            return timedelta(0)

    left = Pydt(2024, 5, 7, tzinfo=Zone())
    right = Pydt(2024, 5, 1, tzinfo=timezone.utc)
    calls.clear()
    with pytest.raises(RuntimeError) as caught:
        left.diff(right, 'D')
    assert caught.value is error
    assert len(calls) == 1 and calls[0] is left


def test_invalid_absolute_is_rejected_before_actual_timezone_offset_callback():
    calls = []

    class Zone(tzinfo):
        def utcoffset(self, value):
            calls.append(value)
            return timedelta(0)

        def dst(self, value):
            return timedelta(0)

    left = Pydt(2024, 5, 7, tzinfo=Zone())
    right = Pydt(2024, 5, 1, tzinfo=Zone())
    calls.clear()
    with pytest.raises(TypeError):
        left.diff(right, 'D', absolute=object())
    assert calls == []


def test_bad_other_is_reported_before_invalid_unit_or_absolute():
    with pytest.raises(TypeError) as caught:
        Pydt(2024, 5, 7).diff(object(), object(), absolute=object())
    assert 'dtobj' in str(caught.value)


def test_exact_pydt_naive_aware_mix_remains_an_error():
    with pytest.raises(TypeError, match='naive and aware'):
        Pydt(2024, 5, 7).diff(Pydt(2024, 5, 1, tzinfo=timezone.utc), 'D')


@pytest.mark.parametrize('subclass', [False, True])
def test_aware_text_keeps_offset_and_stored_string_semantics(subclass):
    class Stored(str):
        def __str__(self):
            raise AssertionError('date input must use the stored text')

    text = '2024-05-07T12:00:00+02:00'
    if subclass:
        text = Stored(text)
    assert Pydt(2024, 5, 7, 12, tzinfo=timezone.utc).diff(text, 'h') == 2
