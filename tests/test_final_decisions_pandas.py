"""F13/F14: actual pandas values, local fields and final span rounding."""

import operator
from datetime import date, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from rstimes import Delta, Pydt, parse, parse_str, parse_to_epoch


class HiddenTimestamp(pd.Timestamp):
    @property
    def asm8(self):
        return np.datetime64("1999-01-01", "us")

    @property
    def nanosecond(self):
        return 0


class HiddenDuration(pd.Timedelta):
    @property
    def asm8(self):
        return np.timedelta64(1, "D")


@pytest.mark.parametrize("year", [1970, 1972, 2024, 12024])
def test_timestamp_base_descriptors_keep_true_ticks_and_tail(year):
    stamp = pd.Timestamp(np.datetime64(f"{year}-01-02T03:04:05.000001", "us"))
    if year < 9999:
        stamp += pd.Timedelta(123, "ns")
    expected = int(pd.Timestamp.asm8.__get__(stamp).astype("int64"))
    input_unit = str(pd.Timestamp.asm8.__get__(stamp).dtype).split("[")[1][:-1]
    stamp.__class__ = HiddenTimestamp
    assert parse_to_epoch(stamp, unit=input_unit) == expected
    if year < 9999:
        assert parse(stamp) == datetime(year, 1, 2, 3, 4, 5, 1)
        assert Pydt.fromdatetime(stamp) == datetime(year, 1, 2, 3, 4, 5, 1)
        assert pd.Timestamp.nanosecond.__get__((Delta(microseconds=1) + stamp)) == 123
        for delta in [Delta(microsecond=1), Delta(microsecond=2), Delta(millisecond=0)]:
            assert pd.Timestamp.nanosecond.__get__(delta + stamp) == 0
            assert pd.Timestamp.nanosecond.__get__(delta.apply_many([stamp])[0]) == 0
    else:
        with pytest.raises(OverflowError):
            Pydt.fromdatetime(stamp)
        assert pd.Timestamp.year.__get__(stamp + Delta(days=1)) == year


@pytest.mark.parametrize("seconds", [2, 2**63 - 1])
def test_duration_base_descriptor_keeps_true_value(seconds):
    # The public numpy-scalar constructor retains the source unit on pandas2
    # too; its numeric constructor prematurely forces large seconds into ns.
    duration = pd.Timedelta(np.timedelta64(seconds, "s"))
    duration.__class__ = HiddenDuration
    normalized = Delta() + duration
    assert normalized.days == seconds // 86400
    assert normalized.seconds == seconds % 60
    if seconds == 2:
        assert Pydt(2024, 1, 1) + duration == datetime(2024, 1, 1, 0, 0, 2)
    else:
        with pytest.raises(OverflowError):
            Pydt(2024, 1, 1) + duration


@pytest.mark.parametrize("year", [1970, 1972, 2024])
def test_local_timestamp_operations_do_not_consume_offset(year):
    class Zone(tzinfo):
        armed = False

        def utcoffset(self, value):
            if self.armed:
                raise RuntimeError("unused offset")
            return timedelta(hours=2)

        def dst(self, value):
            return timedelta(0)

    zone = Zone()
    stamp = pd.Timestamp(datetime(year, 1, 2, 23, 30, 0, 1, tzinfo=zone))
    stamp += pd.Timedelta(500, "ns")
    stamp.__class__ = HiddenTimestamp
    value = Pydt(year, 1, 2, 23, 30, tzinfo=zone)
    zone.armed = True
    expected = (date(year, 1, 2).toordinal() - date(1970, 1, 1).toordinal()) * 86400000000000
    expected += (23 * 3600 + 30 * 60) * 1000000000 + 1500
    assert parse_to_epoch(stamp, unit="ns", ignoretz=True) == expected
    assert value - stamp == timedelta(microseconds=-2)
    for copied in [parse(stamp), Pydt.fromdatetime(stamp)]:
        assert (copied.year, copied.month, copied.day, copied.hour) == (year, 1, 2, 23)
    assert parse_str("12:30", default=stamp) == datetime(year, 1, 2, 12, 30)
    with pytest.raises(RuntimeError, match="unused offset"):
        parse_to_epoch(stamp, ignoretz=False)


@pytest.mark.parametrize("year", [1970, 1972, 2024])
def test_cross_zone_equality_obeys_fold_exception_for_all_years(year):
    zone = ZoneInfo("America/New_York")
    # Select the fall transition independently from each year's standard rules.
    overlap = next(datetime(year, 10, 1) + timedelta(days=n) for n in range(62)
                   if (lambda d: d.replace(tzinfo=zone, fold=0).utcoffset()
                        != d.replace(tzinfo=zone, fold=1).utcoffset())(
                            datetime(year, 10, 1) + timedelta(days=n, hours=1)))
    value = Pydt(year, overlap.month, overlap.day, 1, 30, tzinfo=zone, fold=1)
    stamp = pd.Timestamp(value.astimezone(timezone.utc))
    assert not (value == stamp) and value != stamp
    assert not (stamp == value) and stamp != value
    assert value <= stamp and value >= stamp


@pytest.mark.parametrize("operation", [operator.eq, operator.ne, operator.lt, operator.le,
                                        operator.gt, operator.ge])
@pytest.mark.parametrize("year", [1970, 1972, 2024, 12024])
def test_timestamp_custom_comparison_keeps_dispatch_for_wide_carrier(operation, year):
    calls = []
    class Child(pd.Timestamp):
        def __eq__(self, other): calls.append("eq"); return "custom"
        def __ne__(self, other): calls.append("ne"); return "custom"
        def __lt__(self, other): calls.append("lt"); return "custom"
        def __le__(self, other): calls.append("le"); return "custom"
        def __gt__(self, other): calls.append("gt"); return "custom"
        def __ge__(self, other): calls.append("ge"); return "custom"
    stamp = pd.Timestamp(np.datetime64(f"{year}-01-01", "us"))
    stamp.__class__ = Child
    assert operation(Pydt(2024, 1, 1), stamp) == "custom"
    assert len(calls) == 1


@pytest.mark.parametrize("start, target, days", [(1700, 2024, 118338), (2024, 1700, -118338)])
def test_timestamp_span_exceeds_pandas_intermediate_duration(start, target, days):
    stamp = pd.Timestamp(np.datetime64(f"{start}-01-01", "us"))
    assert Delta(year=target).to_timedelta(stamp) == timedelta(days=days)


class InheritedSpanDelta(Delta):
    pass


class InheritedSpanTimestamp(pd.Timestamp):
    pass


@pytest.mark.parametrize('delta_class', [Delta, InheritedSpanDelta])
@pytest.mark.parametrize('stamp_class', [pd.Timestamp, InheritedSpanTimestamp])
@pytest.mark.parametrize('first,last', [(1700, 2024), (2024, 1700)])
@pytest.mark.parametrize('nanos', [0, 123, 500, 700, 1500])
@pytest.mark.parametrize('reset', [None, 'microsecond', 'millisecond'])
@pytest.mark.parametrize('unit', ['ns', 'us'])
def test_wide_timestamp_span_preserves_precision_and_subclasses(
    delta_class, stamp_class, first, last, nanos, reset, unit,
):
    start = (pd.Timestamp(f'{first}-01-01').as_unit('ns') + pd.Timedelta(nanos, 'ns')).as_unit(unit)
    original_fraction = datetime.microsecond.__get__(start) * 1000 + pd.Timestamp.nanosecond.__get__(start)
    if stamp_class is not pd.Timestamp:
        start.__class__ = stamp_class
    value = delta_class(year=last, **({reset: 0} if reset else {}))
    raw = (datetime(last, 1, 1) - datetime(first, 1, 1)).days * 86400000000000
    if reset:
        raw -= original_fraction
    micros, rest = divmod(raw, 1000)
    expected = timedelta(microseconds=micros + int(rest > 500 or rest == 500 and micros % 2))
    result = value.to_timedelta(start)
    assert type(result) is timedelta and result == expected


@pytest.mark.parametrize('regional', [False, True])
def test_timestamp_elapsed_span_does_not_use_a_public_offset_override(regional):
    calls = []
    class PublicOffset(pd.Timestamp):
        def utcoffset(self):
            calls.append('public offset')
            return timedelta(hours=1)
    start = pd.Timestamp('2024-03-09T12:00:00', tz='America/New_York') if regional else pd.Timestamp('2024-01-01T00:00:00Z')
    start.__class__ = PublicOffset
    expected = timedelta(hours=23 if regional else 24)
    calls.clear()
    assert Delta(days=1).to_timedelta(start) == expected
    assert calls == []


@pytest.mark.parametrize('mode', ['add_sub', 'add_rsub', 'delta_radd', 'standard_add_rsub'])
def test_timestamp_span_keeps_real_arithmetic_dispatch_once(mode):
    calls = []
    class Duration(timedelta):
        pass
    class AddSubtract(pd.Timestamp):
        def __add__(self, other):
            calls.append('add')
            target = pd.Timestamp('2024-01-02')
            target.__class__ = AddSubtract
            return target
        def __sub__(self, other):
            calls.append('sub')
            return Duration(microseconds=7)
    class AddReflected(pd.Timestamp):
        def __add__(self, other):
            calls.append('add')
            return pd.Timestamp('2024-01-02')
        def __rsub__(self, other):
            calls.append('rsub')
            return Duration(microseconds=11)
    class ReflectedOnly(pd.Timestamp):
        def __rsub__(self, other):
            calls.append('rsub')
            return Duration(microseconds=13)
    class CustomDelta(Delta):
        def __radd__(self, other):
            calls.append('delta_radd')
            return pd.Timestamp('2024-01-03')
    start = pd.Timestamp('2024-01-01')
    value = Delta(days=1)
    if mode == 'add_sub':
        start.__class__ = AddSubtract
        expected, expected_calls = timedelta(microseconds=7), ['add', 'sub']
    elif mode == 'add_rsub':
        start.__class__ = AddReflected
        expected, expected_calls = timedelta(microseconds=11), ['add', 'rsub']
    elif mode == 'delta_radd':
        value = CustomDelta(days=1)
        expected, expected_calls = timedelta(days=2), ['delta_radd']
    else:
        start.__class__ = ReflectedOnly
        value = CustomDelta(days=1)
        expected, expected_calls = timedelta(microseconds=13), ['delta_radd', 'rsub']
    actual = value.to_timedelta(start)
    assert type(actual) is timedelta and actual == expected
    assert calls == expected_calls

