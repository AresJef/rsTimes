# Timezones and DST policies for pandas columns

A Pddt has one timezone for the column. Without a target, naive and aware
values cannot mix, and different source regions or fixed offsets cannot be
guessed into one zone. Supplying a target interprets naive date fields there
and converts aware instants to it. Missing rows do not create zone conflicts.

## Attach, convert, remove, or switch

```{doctest} pddt-zone-operation-roles
>>> from datetime import datetime, timedelta, timezone
>>> from zoneinfo import ZoneInfo
>>> import numpy as np
>>> import pandas as pd
>>> from rstimes import Pddt, Configs
>>> wall = Pddt(['1970-01-01T08:00:00', None], unit='ns', name='event')
>>> aware = wall.tz_localize('Asia/Shanghai')
>>> converted = aware.tz_convert('UTC')
>>> (type(aware) is Pddt, aware.unit, aware.name, aware.hour.tolist(), converted.asi8.tolist())
(True, 'ns', 'event', [8.0, nan], [0, -9223372036854775808])
>>> (aware.tz_localize(None).asi8.tolist(), aware.tz_convert(None).asi8.tolist())
([28800000000000, -9223372036854775808], [0, -9223372036854775808])
>>> (aware.tz_switch(None).asi8.tolist(), aware.astimezone('UTC').asi8.tolist())
([28800000000000, -9223372036854775808], [0, -9223372036854775808])
>>> switched = wall.tz_switch('UTC', base_tz='Asia/Shanghai', naive=True)
>>> (switched.tz is None, switched.asi8.tolist(), switched.unit, switched.name)
(True, [0, -9223372036854775808], 'ns', 'event')
>>> for call, exception in ((lambda: wall.tz_convert('UTC'), TypeError), (lambda: aware.tz_localize('UTC'), TypeError), (lambda: wall.tz_switch('UTC'), ValueError), (lambda: wall.tz_switch('UTC', base_tz='Asia/Shanghai', naive=1), TypeError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid zone operation accepted')
>>> for values in ([datetime(2024, 1, 1), datetime(2024, 1, 1, tzinfo=timezone.utc)], ['2024-01-01T00:00+08:00', '2024-01-01T00:00+09:00']):
...     try:
...         Pddt(values)
...     except ValueError:
...         pass
...     else:
...         raise AssertionError('mixed zones were guessed')
...     assert str(Pddt(values, tz='UTC').tz) == 'UTC'
```

## Select actual repeated-time candidates

`ambiguous` accepts `'raise'`, `'NaT'`, `'infer'`, true Python/NumPy booleans,
or a one-dimensional true boolean mask. A mask covers every original position,
including ordinary and missing rows, and uses position rather than labels.
Numeric 0/1 are not boolean policies.

True and False select the candidates defined by the library's pandas-compatible
policy. They are not a universal test of `dst() != 0`, nor a new fold parameter.
The historical cases below have two candidates with the same DST status.

```{doctest} pddt-ambiguous-candidates
>>> text = '2024-11-03T01:30:00.000000123'
>>> first = Pddt([text], tz='America/New_York', ambiguous=np.bool_(True))
>>> second = Pddt([text], tz='America/New_York', ambiguous=False)
>>> (first.tz_convert('UTC').isoformat().tolist(), second.tz_convert('UTC').isoformat().tolist())
(['2024-11-03T05:30:00.000000123+00:00'], ['2024-11-03T06:30:00.000000123+00:00'])
>>> (first.is_dst().tolist(), second.is_dst().tolist(), int(second.asi8[0] - first.asi8[0]))
([True], [False], 3600000000000)
>>> historical = [('Europe/Warsaw', '1915-08-04 23:50', (5040, 3600), False), ('Europe/Kyiv', '1990-07-01 01:30', (14400, 10800), True)]
>>> for region, text, offsets, daylight in historical:
...     a, b = Pddt([text], tz=region, ambiguous=True), Pddt([text], tz=region, ambiguous=False)
...     assert (a.utcoffset_seconds()[0], b.utcoffset_seconds()[0]) == offsets
...     assert a.is_dst().tolist() == b.is_dst().tolist() == [daylight]
>>> values = [None, '2024-11-03 01:30', '2024-11-03 02:30', '2024-11-03 01:30']
>>> mask = pd.Series([True, False, True, True], index=[9, 7, 3, 1], dtype='boolean')
>>> selected = Pddt(values, tz='America/New_York', ambiguous=mask)
>>> (selected.isna().tolist(), selected[1].fold, selected[3].fold)
([True, False, False, False], 1, 0)
>>> Pddt(['2024-11-03 01:30', None], tz='America/New_York', ambiguous='NaT').isna().tolist()
[True, True]
>>> for strict in (False, True):
...     try:
...         Pddt(['2024-11-03 01:30'], tz='America/New_York', strict=strict)
...     except ValueError:
...         continue
...     raise AssertionError('strict changed the DST policy')
```

Inference uses the original order. It needs enough repeated-time information
to select a consistent progression, and does not sort or guess a lone repeated
clock. Existing aware datetimes already identify instants and retain their fold
without another ambiguity choice.

```{doctest} pddt-ambiguous-infer-and-known-instants
>>> clocks = ['2024-11-03 00:30', '2024-11-03 01:30', '2024-11-03 01:30', '2024-11-03 02:30']
>>> inferred = Pddt(clocks, tz='America/New_York', ambiguous='infer')
>>> inferred.tz_convert('UTC').isoformat().tolist()
['2024-11-03T04:30:00+00:00', '2024-11-03T05:30:00+00:00', '2024-11-03T06:30:00+00:00', '2024-11-03T07:30:00+00:00']
>>> try:
...     Pddt(['2024-11-03 01:30'], tz='America/New_York', ambiguous='infer')
... except ValueError as error:
...     print(type(error).__name__)
ValueError
>>> region = ZoneInfo('America/New_York')
>>> known = [datetime(2024, 11, 3, 1, 30, tzinfo=region, fold=0), datetime(2024, 11, 3, 1, 30, tzinfo=region, fold=1)]
>>> existing = Pddt(known)
>>> (existing[0].fold, existing[1].fold, existing.tz_convert('UTC').hour.tolist())
(0, 1, [5, 6])
```

## Resolve a missing local clock

`nonexistent` accepts `'raise'`, `'NaT'`, `'shift_forward'`, `'shift_backward'`,
or one legal timedelta. Forward/backward choose the nearest existing boundary,
rather than adding the gap length to every clock. A timedelta explicitly shifts
the clock and must land outside the gap. The last earlier tick depends on the
column's unit. A half-hour or whole-day gap uses its actual boundary.

```{doctest} pddt-missing-local-times
>>> gap = '2024-03-10 02:30'
>>> for unit, scale in (('s', 1), ('ms', 1000), ('us', 1000000), ('ns', 1000000000)):
...     forward = Pddt([gap], unit=unit, tz='America/New_York', nonexistent='shift_forward')
...     backward = Pddt([gap], unit=unit, tz='America/New_York', nonexistent='shift_backward')
...     assert forward.asi8.tolist() == [1710054000 * scale]
...     assert backward.asi8.tolist() == [1710054000 * scale - 1]
...     assert Pddt([gap], unit=unit, tz='America/New_York', nonexistent='NaT').isna().tolist() == [True]
>>> Pddt([gap], tz='America/New_York', nonexistent=timedelta(hours=1)).isoformat().tolist()
['2024-03-10T03:30:00-04:00']
>>> cases = [('Australia/Lord_Howe', '2024-10-06 02:15', '2024-10-06T02:30:00+11:00', '2024-10-06T01:59:59.999999+10:30'), ('Pacific/Apia', '2011-12-30 12:30', '2011-12-31T00:00:00+14:00', '2011-12-29T23:59:59.999999-10:00')]
>>> for region, clock, forward, backward in cases:
...     assert Pddt([clock], unit='us', tz=region, nonexistent='shift_forward').isoformat().tolist() == [forward]
...     assert Pddt([clock], unit='us', tz=region, nonexistent='shift_backward').isoformat().tolist() == [backward]
>>> for policy in ('raise', timedelta(minutes=1)):
...     try:
...         Pddt([gap], tz='America/New_York', nonexistent=policy)
...     except ValueError:
...         continue
...     raise AssertionError('unresolved gap was accepted')
```

Policies are validated on empty/native inputs too. `'NaT'` only resolves the
stated DST condition; it does not coerce unrelated bad text.

```{doctest} pddt-invalid-zone-policies
>>> for policy, exception in ((1, TypeError), (0, TypeError), (None, TypeError), ('unknown', ValueError), ([1], TypeError), (np.array([[True]]), ValueError), ([True], ValueError)):
...     try:
...         Pddt([], ambiguous=policy)
...     except exception:
...         continue
...     raise AssertionError('invalid ambiguity policy accepted')
>>> for policy, exception in ((True, TypeError), (None, TypeError), (0, TypeError), (['NaT'], TypeError), (np.timedelta64(1, 'h'), TypeError), ('unknown', ValueError)):
...     try:
...         Pddt([], nonexistent=policy)
...     except exception:
...         continue
...     raise AssertionError('invalid gap policy accepted')
>>> try:
...     Pddt(['not a date'], tz='America/New_York', ambiguous='NaT', nonexistent='NaT')
... except ValueError as error:
...     print(type(error).__name__)
ParseError
```

## Register source regions in text

Region names inside text require exact Configs registration. The source clock
is interpreted in that region before any target-zone conversion, so a UTC
target cannot remove the need to resolve a source repeated time. Explicit `tz`
arguments and existing timezone objects need no vocabulary registration.

```{doctest} pddt-registered-source-region
>>> config = Configs()
>>> config.add_tzone('America/New_York')
True
>>> text = '2024-11-03 01:30:00.123456789 America/New_York'
>>> regional = Pddt([text], cfg=config, tz='UTC', ambiguous=False)
>>> (regional.unit, regional.isoformat().tolist())
('ns', ['2024-11-03T06:30:00.123456789+00:00'])
>>> try:
...     Pddt([text], tz='UTC', ambiguous=False)
... except ValueError as error:
...     print(type(error).__name__, 'register' in str(error))
ParseError True
```

## Metadata and a process-local timezone

`tzinfo` aliases the stored zone, `tz_available` is a set of available region
names, and `is_utc` tests the standard UTC singleton. `is_local` compares with
the successfully cached process-local ZoneInfo. Set `TZ` before the first local
request, or use an explicit target to avoid depending on the host.

```{doctest} pddt-zone-metadata
>>> utc = Pddt([0, None], unit='s', tz='UTC')
>>> (utc.tzinfo is utc.tz, utc.is_utc(), type(utc.tz_available) is set, 'America/New_York' in utc.tz_available)
(True, True, True, True)
>>> (utc.is_dst().tolist(), utc.utcoffset_seconds().tolist())
([False, False], [0, <NA>])
>>> import os, subprocess, sys
>>> program = '\n'.join([
...     'from rstimes import Pddt',
...     "x = Pddt(['1970-01-01 08:00']).astimezone()",
...     "assert x.tz.key == 'Asia/Shanghai' and x.is_local() is True",
...     "assert x.tz_convert('UTC').asi8.tolist() == [0]",
...     "assert Pddt.fromtimestamp(0, size=1).hour.tolist() == [8]",
... ])
>>> result = subprocess.run([sys.executable, '-I', '-c', program], env=dict(os.environ, TZ='Asia/Shanghai'), check=True, capture_output=True, text=True, timeout=20)
>>> (result.returncode, result.stdout, result.stderr)
(0, '', '')
```
