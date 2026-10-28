"""Timestamp protocols, real nanoseconds and the approved reverse-NI boundary."""
from datetime import datetime, timedelta, timezone
import operator
from zoneinfo import ZoneInfo
import pandas as pd
import pytest
from rstimes import Pydt, parse_to_epoch

OPERATIONS = {
    'eq': operator.eq, 'ne': operator.ne, 'lt': operator.lt,
    'le': operator.le, 'gt': operator.gt, 'ge': operator.ge,
}


@pytest.mark.parametrize('operation', OPERATIONS)
@pytest.mark.parametrize('timestamp_first', [False, True])
@pytest.mark.parametrize('mode', ['true', 'false', 'none', 'integer', 'object', 'error', 'decline'])
def test_timestamp_comparison_preserves_result_error_and_negotiation(operation, timestamp_first, mode):
    calls = []
    error = RuntimeError('comparison source failed')
    marker = object()
    class Result:
        def __bool__(self):
            pytest.fail('a comparison result must not be coerced to bool')
    result = {'true': True, 'false': False, 'none': None, 'integer': 17,
              'object': Result(), 'decline': NotImplemented}.get(mode)
    def callback(self, other):
        calls.append(other)
        if mode == 'error':
            error.detail = marker
            raise error
        return result
    Child = type('TimestampChild', (pd.Timestamp,),
                 {f'__{name}__': callback for name in OPERATIONS})
    # pandas factories return the base Timestamp even when invoked on a child.
    # The supported class assignment preserves a fully initialized native value.
    timestamp = pd.Timestamp('2024-01-02 12:30:01.123456789')
    timestamp.__class__ = Child
    assert type(timestamp) is Child and timestamp.nanosecond == 789
    value = Pydt(2024, 1, 2, 12, 30, 1, 123456)
    calls.clear()
    left, right = (timestamp, value) if timestamp_first else (value, timestamp)
    if mode == 'error':
        with pytest.raises(RuntimeError) as caught:
            OPERATIONS[operation](left, right)
        assert caught.value is error and error.args == ('comparison source failed',)
        assert error.detail is marker and len(calls) == 1
    else:
        actual = OPERATIONS[operation](left, right)
        if mode == 'decline':
            # The Timestamp is 789ns later. Comparing ordinary microsecond
            # datetime fields alone would incorrectly report equality.
            earlier = not timestamp_first
            expected = {'eq': False, 'ne': True, 'lt': earlier,
                        'le': earlier, 'gt': not earlier, 'ge': not earlier}[operation]
            assert actual is expected
            # Python may call a Timestamp-first child before Pydt negotiates.
            # The explicitly approved reverse boundary permits a second call.
            assert len(calls) == (2 if timestamp_first else 1)
        else:
            assert actual is result and len(calls) == 1


class PublicOffsetPydt(Pydt):
    def utcoffset(self):
        return timedelta(hours=1)


class ShadowTimezonePydt(Pydt):
    @property
    def tzinfo(self):
        return timezone(timedelta(hours=-7))


class PublicOffsetTimestamp(pd.Timestamp):
    def utcoffset(self):
        return timedelta(hours=1)


class ShadowTimezoneTimestamp(pd.Timestamp):
    @property
    def tzinfo(self):
        return timezone(timedelta(hours=-7))


def stored_wall_nanoseconds(value):
    """Use standard base descriptors as an independent stored-field oracle."""
    fields = [getattr(datetime, key).__get__(value) for key in (
        'year', 'month', 'day', 'hour', 'minute', 'second', 'microsecond',
    )]
    elapsed = datetime(*fields) - datetime(1970, 1, 1)
    nanos = ((elapsed.days * 86400 + elapsed.seconds) * 1000000 + elapsed.microseconds) * 1000
    if isinstance(value, pd.Timestamp):
        nanos += pd.Timestamp.nanosecond.__get__(value)
    return nanos


def stored_zone_nanoseconds(value):
    zone = datetime.tzinfo.__get__(value)
    if zone is None:
        return 0
    offset = zone.utcoffset(value)
    if offset is None:
        return 0
    return ((offset.days * 86400 + offset.seconds) * 1000000 + offset.microseconds) * 1000


@pytest.mark.parametrize('left_class', [Pydt, PublicOffsetPydt, ShadowTimezonePydt])
@pytest.mark.parametrize('right_class', [pd.Timestamp, PublicOffsetTimestamp, ShadowTimezoneTimestamp])
@pytest.mark.parametrize('year', [1970, 1972, 2024])
@pytest.mark.parametrize('tail', [0, 789])
@pytest.mark.parametrize('left_zone,right_zone', [
    (None, None),
    (timezone.utc, timezone.utc),
    (timezone.utc, timezone(timedelta(hours=2))),
    (timezone(timedelta(hours=-3, minutes=-30)), timezone.utc),
    (None, timezone.utc),
    (timezone.utc, None),
])
def test_standard_timestamp_operations_use_stored_timezone(
    left_class, right_class, year, tail, left_zone, right_zone,
):
    left = left_class(year, 5, 7, 12, 34, 56, 123456, tzinfo=left_zone)
    right = pd.Timestamp(datetime(year, 5, 7, 12, 34, 56, 123456, tzinfo=right_zone)).as_unit('ns')
    right += pd.Timedelta(tail, 'ns')
    if right_class is not pd.Timestamp:
        right.__class__ = right_class
    same_zone = left_zone is right_zone
    left_ns = stored_wall_nanoseconds(left) - (0 if same_zone else stored_zone_nanoseconds(left))
    right_ns = stored_wall_nanoseconds(right) - (0 if same_zone else stored_zone_nanoseconds(right))
    mixed = (left_zone is None) != (right_zone is None)
    plain_left = datetime(year, 5, 7, 12, 34, 56, 123456, tzinfo=left_zone)
    for operation in OPERATIONS.values():
        for a, b, na, nb in ((left, right, left_ns, right_ns), (right, left, right_ns, left_ns)):
            if a is right and right_class is ShadowTimezoneTimestamp:
                # pandas may finish its own comparison using its overridden
                # public property. Pydt cannot replace a result returned before
                # its slot is called; retain the independent datetime behavior.
                try:
                    external = getattr(pd.Timestamp, '__' + operation.__name__ + '__')(right, plain_left)
                except TypeError:
                    with pytest.raises(TypeError):
                        operation(a, b)
                    continue
                else:
                    if external is not NotImplemented:
                        assert operation(a, b) is external
                        continue
                # A declined pandas hook reaches Pydt's nanosecond-aware slot;
                # plain datetime's fallback would lose that tail.
            if mixed and operation not in (operator.eq, operator.ne):
                with pytest.raises(TypeError):
                    operation(a, b)
            else:
                wanted = operation(na, nb) if not mixed else operation is operator.ne
                assert operation(a, b) is wanted
    if mixed:
        with pytest.raises(TypeError):
            left - right
    else:
        micros, remainder = divmod(left_ns - right_ns, 1000)
        expected = timedelta(microseconds=micros + int(remainder > 500 or remainder == 500 and micros % 2))
        assert left - right == expected
        if left_ns == right_ns:
            assert hash(left) == hash(right)


@pytest.mark.parametrize('fold', [0, 1])
def test_public_offset_override_keeps_the_stored_regional_fold(fold):
    zone = ZoneInfo('America/New_York')
    left = PublicOffsetPydt(2024, 11, 3, 1, 30, tzinfo=zone, fold=fold)
    right = pd.Timestamp(datetime(2024, 11, 3, 1, 30, tzinfo=zone, fold=fold).astimezone(timezone.utc))
    assert not (left == right) and left != right
    assert not (right == left) and right != left
    assert left <= right and left >= right
    assert left - right == timedelta(0)


def test_public_epoch_conversion_keeps_its_separate_offset_protocol():
    value = PublicOffsetPydt(2024, 1, 1, tzinfo=timezone.utc)
    expected = datetime(2024, 1, 1) - datetime(1970, 1, 1) - timedelta(hours=1)
    assert parse_to_epoch(value) == (expected.days * 86400 + expected.seconds) * 1000000
