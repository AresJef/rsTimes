"""Independent calendar values and actual carrier lifetime before field reuse."""
from datetime import datetime, timedelta, tzinfo

import numpy as np
import pytest

from rstimes import Pddt


@pytest.mark.parametrize('unit', ['s', 'ms', 'us', 'ns'])
@pytest.mark.parametrize('zone', ['Europe/Berlin', 'America/New_York'])
def test_regional_month_end_keeps_full_ticks_missingness_and_source(unit, zone):
    before = np.array(['2024-01-31T11:00:00.123456789', 'NaT',
                       '2024-03-31T11:00:00.987654321'], dtype=f'datetime64[{unit}]')
    expected = np.array(['2024-02-29T11:00:00.123456789', 'NaT',
                         '2024-04-30T11:00:00.987654321'], dtype=before.dtype)
    source = Pddt(before.view('i8'), unit=unit, tz=zone, name='events')
    saved = source.asi8.copy()
    result = source.add(months=1)
    assert result.asi8.tolist() == expected.view('i8').tolist()
    assert result.unit == unit and result.name == 'events' and result.tz is source.tz
    assert np.array_equal(source.asi8, saved)


@pytest.mark.parametrize('unit', ['us', 'ns'])
@pytest.mark.parametrize('utc,days,target', [
    ('2024-03-30T11:00:00.123456789', 1, '2024-03-31T10:00:00.123456789'),
    ('2024-04-01T10:00:00.123456789', -1, '2024-03-31T10:00:00.123456789'),
    ('2024-10-26T00:30:00.123456789', 1, '2024-10-27T00:30:00.123456789'),
    ('2024-10-28T01:30:00.123456789', -1, '2024-10-27T01:30:00.123456789'),
])
def test_regional_day_move_keeps_actual_occurrence_and_fraction(unit, utc, days, target):
    values = np.array([utc, 'NaT'], dtype=f'datetime64[{unit}]')
    expected = np.array([target, 'NaT'], dtype=values.dtype).view('i8')
    source = Pddt(values.view('i8'), unit=unit, tz='Europe/Berlin', name='events')
    result = source.add(days=days)
    assert result.asi8.tolist() == expected.tolist()
    assert source.asi8.tolist() == values.view('i8').tolist()


def test_source_fromutc_carrier_is_dropped_before_subsequent_zone_callbacks():
    events = []
    state = {'started': False, 'dropped': False, 'calls': 0}

    class Carrier(datetime):
        def __del__(self):
            if self.source_marker:
                state['dropped'] = True
                events.append('source_drop')

    class Zone(tzinfo):
        def utcoffset(self, value):
            if type(value) is Carrier and value.source_marker:
                events.append('source_offset')
            elif state['started']:
                assert state['dropped'], 'source carrier retained into later callbacks'
            return timedelta(0)

        def dst(self, value):
            return timedelta(0)

        def tzname(self, value):
            return 'zero'

        def fromutc(self, value):
            state['calls'] += 1
            first = state['calls'] == 1
            if first:
                state['started'] = True
                events.append('source_fromutc')
            result = datetime.__new__(Carrier, value.year, value.month, value.day,
                                      value.hour, value.minute, value.second,
                                      value.microsecond, tzinfo=self, fold=value.fold)
            result.source_marker = first
            return result

    zone = Zone()
    source = Pddt([1706698800123456789], unit='ns', tz='UTC').tz_convert(zone)
    state.update(started=False, dropped=False, calls=0)
    events.clear()
    result = source.add(months=1)
    assert events[:3] == ['source_fromutc', 'source_offset', 'source_drop']
    expected = np.datetime64('2024-02-29T11:00:00.123456789', 'ns').view('i8').item()
    assert result.asi8.tolist() == [expected]


@pytest.mark.parametrize('invalid', [False, True])
def test_source_fromutc_real_exception_or_instant_error_keeps_its_role(invalid):
    error = RuntimeError('actual source fromutc error')

    class Zone(tzinfo):
        enabled = False

        def utcoffset(self, value):
            return timedelta(0)

        def dst(self, value):
            return timedelta(0)

        def tzname(self, value):
            return 'zero'

        def fromutc(self, value):
            if self.enabled:
                if invalid:
                    return value + timedelta(seconds=1)
                raise error
            return value

    zone = Zone()
    source = Pddt([1706698800123456789], unit='ns', tz='UTC').tz_convert(zone)
    zone.enabled = True
    if invalid:
        with pytest.raises(ValueError, match='preserve the actual instant'):
            source.add(months=1)
    else:
        with pytest.raises(RuntimeError) as caught:
            source.add(months=1)
        assert caught.value is error
