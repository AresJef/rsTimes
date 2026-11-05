# Timezones in native Polars date columns

Pldt encodes one timezone in its Datetime dtype. It supports named IANA regions,
UTC aliases, and standard fixed offsets with a representable whole-hour IANA
equivalent. Arbitrary custom tzinfo and fractional fixed offsets cannot be
encoded as a Polars timezone. Choose a supported target or UTC explicitly.
The native backend's supported-zone set is distinct from the system ZoneInfo
database. Original Python timezone object identity is not stored in the dtype.

**Known defect RV03:** a business ZoneInfo subclass can override an offset that
differs from its key. As a Pldt target, that object is currently interpreted by
key and can silently select the wrong instant. Use exact ordinary ZoneInfo
targets, or normalize a genuinely aware input through its actual protocol as
shown in [the executed defect and workaround](../compatibility/known-issues.md).
This defect is separate from the ordinary region cases below.

## Eager attachment and conversion

`tz_localize` attaches a zone to naive clocks, or removes it while retaining
the local clock. `tz_convert` needs an aware input and keeps its instant;
None converts to UTC then removes the zone. `tz_switch(None)` removes the zone
while keeping the clock. A nonempty target on a naive source requires base_tz;
naive=True removes the converted target zone. `astimezone(None)` targets local.

```{doctest} pldt-zone-operation-roles
>>> from datetime import timedelta, timezone
>>> import os, subprocess, sys
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt, Configs
>>> wall = Pldt([28800000000000, None], unit='ns', name='event')
>>> plain = pl.Series('event', [28800000000000, None], dtype=pl.Int64).cast(pl.Datetime('ns'))
>>> assert type(plain) is pl.Series
>>> for receiver in (wall, plain.pldt):
...     aware = receiver.tz_localize('Asia/Shanghai')
...     assert type(aware) is Pldt and aware.dtype == pl.Datetime('ns', 'Asia/Shanghai') and aware.name == 'event'
...     assert aware.to_physical().to_list() == [0, None]
...     assert aware.tz_localize(None).to_physical().to_list() == [28800000000000, None]
...     assert aware.tz_convert(None).to_physical().to_list() == [0, None]
...     assert aware.tz_switch(None).to_physical().to_list() == [28800000000000, None]
...     assert aware.astimezone('UTC').dtype == pl.Datetime('ns', 'UTC')
...     switched = receiver.tz_switch('UTC', base_tz='Asia/Shanghai', naive=True)
...     assert switched.dtype == pl.Datetime('ns') and switched.to_physical().to_list() == [0, None]
>>> known = wall.tz_localize('Asia/Shanghai')
>>> for receiver in (known, pl.Series(known).pldt):
...     converted = receiver.tz_convert('UTC')
...     alternative = receiver.astimezone('UTC')
...     assert type(converted) is Pldt and type(alternative) is Pldt
...     assert converted.dtype == alternative.dtype == pl.Datetime('ns', 'UTC')
...     assert converted.to_physical().to_list() == alternative.to_physical().to_list() == [0, None]
...     assert receiver.tz_localize(None).to_physical().to_list() == [28800000000000, None]
...     assert receiver.tz_switch(None).to_physical().to_list() == [28800000000000, None]
>>> for call, exception in ((lambda: wall.tz_convert('UTC'), TypeError), (lambda: aware.tz_localize('UTC'), TypeError), (lambda: wall.tz_switch('UTC'), ValueError), (lambda: wall.tz_switch('UTC', base_tz='Asia/Shanghai', naive=1), TypeError), (lambda: Pldt([0], tz=timezone(timedelta(minutes=30))), ValueError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid timezone role accepted')
```

## Repeated times, full-position masks, and inference

`ambiguous` accepts raise/NaT/infer, actual Python/NumPy booleans, or a boolean
mask covering every original row. The candidate selection is independent of
whether both historical candidates have the same DST status. `infer` uses the
original logical order, including across native chunks; it never sorts to make
an answer. A lone ambiguous time supplies insufficient inference information.

```{doctest} pldt-repeated-time-policies
>>> first = Pldt(['2024-11-03 01:30:00.000000123'], tz='America/New_York', ambiguous=True)
>>> second = Pldt(['2024-11-03 01:30:00.000000123'], tz='America/New_York', ambiguous=np.bool_(False))
>>> (first.tz_convert('UTC').isoformat().to_list(), second.tz_convert('UTC').isoformat().to_list())
(['2024-11-03T05:30:00.000000123+00:00'], ['2024-11-03T06:30:00.000000123+00:00'])
>>> for zone, text, offsets, dst in (('Europe/Warsaw', '1915-08-04 23:50', (5040, 3600), False), ('Europe/Kyiv', '1990-07-01 01:30', (14400, 10800), True)):
...     a, b = Pldt([text], tz=zone, ambiguous=True), Pldt([text], tz=zone, ambiguous=False)
...     assert (a.utcoffset_seconds()[0], b.utcoffset_seconds()[0]) == offsets
...     assert a.is_dst().to_list() == b.is_dst().to_list() == [dst]
>>> values = [None, '2024-11-03 01:30', '2024-11-03 02:30', '2024-11-03 01:30']
>>> selected = Pldt(values, tz='America/New_York', ambiguous=pl.Series([True, False, True, True]))
>>> (selected.is_null().to_list(), selected.tz_convert('UTC').hour.to_list())
([True, False, False, False], [None, 6, 7, 5])
>>> chunks = pl.concat([pl.Series(['2024-11-03 00:30', '2024-11-03 01:30']), pl.Series(['2024-11-03 01:30', '2024-11-03 02:30'])], rechunk=False)
>>> assert chunks.n_chunks() == 2
>>> Pldt(chunks, tz='America/New_York', ambiguous='infer').tz_convert('UTC').hour.to_list()
[4, 5, 6, 7]
>>> Pldt(['2024-11-03 01:30', None], tz='America/New_York', ambiguous='NaT').is_null().to_list()
[True, True]
>>> try:
...     Pldt(['2024-11-03 01:30'], tz='America/New_York', ambiguous='infer')
... except ValueError as error:
...     print(type(error).__name__)
ValueError
```

## Missing clocks use actual boundaries

`nonexistent` accepts raise/NaT/shift_forward/shift_backward or one timedelta.
Boundary shifts find the nearest existing boundary at the current unit.
A timedelta shifts the input clock and must land outside the gap. These are
not interchangeable rules. Explicit policies do not coerce unrelated bad text.

```{doctest} pldt-gap-policies
>>> gap = '2024-03-10 02:30'
>>> for unit, scale in (('ms', 1000), ('us', 1000000), ('ns', 1000000000)):
...     a = Pldt([gap], unit=unit, tz='America/New_York', nonexistent='shift_forward')
...     b = Pldt([gap], unit=unit, tz='America/New_York', nonexistent='shift_backward')
...     assert a.to_physical().to_list() == [1710054000 * scale]
...     assert b.to_physical().to_list() == [1710054000 * scale - 1]
...     assert Pldt([gap], unit=unit, tz='America/New_York', nonexistent='NaT').is_null().to_list() == [True]
>>> Pldt([gap], tz='America/New_York', nonexistent=timedelta(hours=1)).isoformat().to_list()
['2024-03-10T03:30:00-04:00']
>>> for zone, clock, expected in (('Australia/Lord_Howe', '2024-10-06 02:15', '2024-10-06T02:30:00+11:00'), ('Pacific/Apia', '2011-12-30 12:30', '2011-12-31T00:00:00+14:00')):
...     assert Pldt([clock], tz=zone, nonexistent='shift_forward').isoformat().to_list() == [expected]
>>> for call, exception in ((lambda: Pldt([gap], tz='America/New_York'), ValueError), (lambda: Pldt([gap], tz='America/New_York', nonexistent=timedelta(minutes=1)), ValueError), (lambda: Pldt([], ambiguous=[True]), ValueError), (lambda: Pldt([], ambiguous=[1]), TypeError), (lambda: Pldt([], ambiguous=None), TypeError), (lambda: Pldt([], nonexistent=['NaT']), TypeError), (lambda: Pldt(['bad'], nonexistent='NaT'), ValueError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid policy or date accepted')
```

## Registered source regions and metadata

Region text requires Configs registration and is interpreted in its source
region before target conversion. An explicit target argument needs no parser
vocabulary registration. Whole-column metadata uses `tzinfo` and
`dtype.time_zone`; Pldt does not add Pddt's `tz` attribute.

```{doctest} pldt-source-zone-and-metadata
>>> config = Configs()
>>> config.add_tzone('America/New_York')
True
>>> regional = Pldt(['2024-11-03 01:30:00.123456789 America/New_York'], cfg=config, tz='UTC', ambiguous=False)
>>> (regional.dtype, regional.isoformat().to_list())
(Datetime(time_unit='ns', time_zone='UTC'), ['2024-11-03T06:30:00.123456789+00:00'])
>>> utc = Pldt([0, None], unit='ns', tz='UTC')
>>> (utc.tzinfo is timezone.utc, utc.dtype.time_zone, utc.is_utc(), type(utc.tz_available) is set, 'America/New_York' in utc.tz_available)
(True, 'UTC', True, True, True)
>>> (utc.is_dst().to_list(), utc.utcoffset_seconds().to_list(), wall.tzinfo)
([False, False], [0, None], None)
>>> program = '\n'.join([
...     'from rstimes import Pldt',
...     "x = Pldt(['1970-01-01 08:00']).astimezone()",
...     "assert x.dtype.time_zone == 'Asia/Shanghai' and x.is_local() is True",
...     "assert x.tz_convert('UTC').to_physical().to_list() == [0]",
...     "assert Pldt.fromtimestamp(0, size=1).hour.to_list() == [8]",
... ])
>>> result = subprocess.run([sys.executable, '-I', '-c', program], env=dict(os.environ, TZ='Asia/Shanghai'), check=True, capture_output=True, text=True, timeout=20)
>>> (result.returncode, result.stdout, result.stderr)
(0, '', '')
```
