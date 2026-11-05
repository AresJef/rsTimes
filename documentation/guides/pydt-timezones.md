# Scalar timezones, fold, and DST

Attach a zone when your input represents local clock fields. Convert zones
when your input already represents an instant. Each method gives `None` its
own meaning.

| Operation | Meaning |
|---|---|
| `tz_localize(zone)` | Attach a zone to naive fields; an already aware value is an error. |
| `tz_localize(None)` / `replace(tzinfo=None)` | Remove the zone while keeping the clock. |
| `tz_convert(zone)` | Convert an aware instant; naive input is an error. |
| `tz_convert(None)` | Convert to UTC and then remove the zone. |
| `astimezone(None)` | Express the instant in the process-local region. |
| `tz_switch(zone, base_tz=..., naive=...)` | Interpret a naive source in base_tz, then convert; optionally remove the result zone. |
| `tz_switch(None)` | Remove the zone while keeping the current clock. |

```{doctest} pydt-zone-operations
>>> from datetime import datetime, timedelta, timezone, tzinfo
>>> from zoneinfo import ZoneInfo
>>> from rstimes import Pydt
>>> wall = Pydt(1970, 1, 1, 8)
>>> attached = wall.tz_localize('Asia/Shanghai')
>>> (type(attached) is Pydt, attached.isoformat(), attached.tz is attached.tzinfo)
(True, '1970-01-01T08:00:00+08:00', True)
>>> attached.tz_convert('UTC').isoformat()
'1970-01-01T00:00:00+00:00'
>>> (attached.tz_localize(None).isoformat(), attached.tz_convert(None).isoformat())
('1970-01-01T08:00:00', '1970-01-01T00:00:00')
>>> (attached.tz_switch(None).isoformat(), attached.replace(tzinfo=None).isoformat())
('1970-01-01T08:00:00', '1970-01-01T08:00:00')
>>> attached.astimezone('UTC').isoformat()
'1970-01-01T00:00:00+00:00'
>>> wall.tz_switch('UTC', base_tz='Asia/Shanghai', naive=True).isoformat()
'1970-01-01T00:00:00'
>>> for call in (lambda: wall.tz_convert('UTC'), lambda: attached.tz_localize('UTC'), lambda: wall.tz_switch('UTC')):
...     try:
...         call()
...     except ValueError:
...         continue
...     raise AssertionError('missing or conflicting source zone accepted')
>>> try:
...     wall.tz_switch('UTC', base_tz='Asia/Shanghai', naive=1)
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```

## Select a repeated time; reject a missing time

In New York, 2024-11-03 01:30 occurs twice. `fold=0` selects the earlier
occurrence and `fold=1` the later. The two instants are an hour apart. On
2024-03-10, 02:30 does not exist; either fold is rejected by strict construction
and replacement. Fold does not repair a gap.

```{doctest} pydt-fold-and-gap
>>> region = ZoneInfo('America/New_York')
>>> first = Pydt(2024, 11, 3, 1, 30, tzinfo=region, fold=0)
>>> second = Pydt(2024, 11, 3, 1, 30, tzinfo=region, fold=1)
>>> (first.tz is region, second.tz is region, first.utcoffset_seconds(), second.utcoffset_seconds())
(True, True, -14400, -18000)
>>> (first.tz_convert('UTC').isoformat(), second.tz_convert('UTC').isoformat())
('2024-11-03T05:30:00+00:00', '2024-11-03T06:30:00+00:00')
>>> (first.is_dst(), second.is_dst(), second.timestamp() - first.timestamp())
(True, False, 3600.0)
>>> second - first
datetime.timedelta(0)
>>> second.tz_convert('UTC') - first.tz_convert('UTC')
datetime.timedelta(seconds=3600)
>>> for fold in (0, 1):
...     try:
...         Pydt(2024, 3, 10, 2, 30, tzinfo=region, fold=fold)
...     except ValueError:
...         continue
...     raise AssertionError('nonexistent time accepted')
>>> try:
...     first.replace(month=3, day=10, hour=2)
... except ValueError as error:
...     print(type(error).__name__)
ValueError
```

The direct subtraction between values sharing the same tzinfo object follows
Python's wall-clock rule and ignores fold. Convert both to UTC for an elapsed
instant difference. Calendar day arithmetic likewise retains the local clock
across a DST transition; its elapsed duration can differ from 24 hours.

```{doctest} pydt-calendar-dst
>>> before = Pydt(2024, 3, 9, 12, tzinfo=region)
>>> after = before.add(days=1)
>>> (after.isoformat(), after - before, after.tz_convert('UTC') - before.tz_convert('UTC'))
('2024-03-10T12:00:00-04:00', datetime.timedelta(days=1), datetime.timedelta(seconds=82800))
```

## Query zone metadata and offsets

`tz` aliases the actual tzinfo. `tz_available` is a set property of installed
ZoneInfo keys. `is_utc()` tests the standard `timezone.utc` object; an explicitly
supplied ZoneInfo('UTC') is still its own region object. `is_dst()` tests for
any nonzero daylight adjustment, including a negative adjustment.

`utcoffset_seconds()` returns an integer using the earlier whole-second
boundary. A fractional negative offset therefore floors to the next smaller
integer. `utcoffset()` and `dst()` retain their timedelta precision.

```{doctest} pydt-zone-queries
>>> utc = Pydt(2024, 1, 1, tzinfo='UTC')
>>> named_utc = Pydt(2024, 1, 1, tzinfo=ZoneInfo('UTC'))
>>> (utc.is_utc(), named_utc.is_utc(), named_utc.tzinfo.key)
(True, False, 'UTC')
>>> (type(utc.tz_available) is set, {'UTC', 'Asia/Shanghai', 'America/New_York'} <= utc.tz_available)
(True, True)
>>> (wall.tz, wall.utcoffset_seconds(), wall.utcoffset(), wall.dst(), wall.tzname(), wall.is_dst())
(None, None, None, None, None, False)
>>> class NegativeDaylight(tzinfo):
...     def utcoffset(self, value):
...         return timedelta(0)
...     def dst(self, value):
...         return timedelta(hours=-1)
>>> negative_daylight = Pydt(2024, 1, 1, tzinfo=NegativeDaylight())
>>> (negative_daylight.dst(), negative_daylight.is_dst())
(datetime.timedelta(days=-1, seconds=82800), True)
>>> fractional = Pydt(1970, 1, 1, tzinfo=timezone(timedelta(microseconds=-500000)))
>>> (fractional.utcoffset(), fractional.utcoffset_seconds())
(datetime.timedelta(days=-1, seconds=86399, microseconds=500000), -1)
```

## Use an explicit process-local region

The first local-zone request reads `TZ` when set, otherwise it asks the system
for its region. A successful ZoneInfo is cached; failure does not silently
become UTC. Set the region before that first request. This example uses a fresh
process to keep the reader's existing process cache unchanged.

```{doctest} pydt-process-local-zone
>>> import os, subprocess, sys
>>> program = '\n'.join([
...     'from rstimes import Pydt',
...     "local = Pydt(1970, 1, 1, 8).astimezone()",
...     "assert local.tzinfo.key == 'Asia/Shanghai' and local.is_local() is True",
...     "assert local.tz_convert('UTC').isoformat() == '1970-01-01T00:00:00+00:00'",
...     "assert Pydt(1970, 1, 1, tzinfo='America/New_York').is_local() is False",
... ])
>>> result = subprocess.run([sys.executable, '-I', '-c', program], env=dict(os.environ, TZ='Asia/Shanghai'), check=True, capture_output=True, text=True, timeout=20)
>>> (result.returncode, result.stdout, result.stderr)
(0, '', '')
```

Real timezone callbacks retain their own errors. A supported duration returned
by `dst` is checked as a duration, rather than converted by arbitrary truthiness.

```{doctest} pydt-timezone-callback-error
>>> failure = RuntimeError('application daylight rule failed')
>>> class BusinessZone(tzinfo):
...     def utcoffset(self, value):
...         return timedelta(0)
...     def dst(self, value):
...         raise failure
>>> custom = Pydt(2024, 1, 1, tzinfo=BusinessZone())
>>> try:
...     custom.is_dst()
... except RuntimeError as error:
...     print(error is failure)
True
```

## Interoperate with an explicit builtin carrier

Pydt's timedelta addition follows its calendar adjustment rules. An external
timezone implementation that performs arithmetic directly on a Pydt can
therefore differ from Pydt's own conversion. This applies to directly calling
`ZoneInfo.fromutc(Pydt)` and explicitly invoking the base
`datetime.astimezone` descriptor. They are not transparent substitutes for
`value.astimezone()` or `value.tz_convert()` around every transition.

The repeated New York hour below demonstrates the actual boundary: the external
protocol selects fold 1 and represents an instant one hour later. Use the
library conversion, or give external timezone code an explicit builtin
datetime carrier with the same instant.

```{doctest} pydt-external-timezone-boundary
>>> region = ZoneInfo('America/New_York')
>>> instant = Pydt(2024, 11, 3, 5, 30, tzinfo='UTC')
>>> own = instant.tz_convert(region)
>>> (own.isoformat(), own.fold)
('2024-11-03T01:30:00-04:00', 0)
>>> external = region.fromutc(Pydt(2024, 11, 3, 5, 30, tzinfo=region))
>>> (external.isoformat(), external.fold, external.timestamp() - instant.timestamp())
('2024-11-03T01:30:00-05:00', 1, 3600.0)
>>> base_conversion = datetime.astimezone(instant, region)
>>> (base_conversion.isoformat(), base_conversion.fold)
('2024-11-03T01:30:00-05:00', 1)
>>> builtin = datetime.fromtimestamp(instant.timestamp(), timezone.utc)
>>> safe = builtin.astimezone(region)
>>> (type(safe) is datetime, safe.isoformat(), safe.fold, safe.timestamp() == instant.timestamp())
(True, '2024-11-03T01:30:00-04:00', 0, True)
```
