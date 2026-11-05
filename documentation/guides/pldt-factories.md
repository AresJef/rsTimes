# Build native Polars dates with factories

Factories return Pldt with one native Datetime unit, one timezone, a string
name, and independent null validity. A scalar source requires `size`; a
collection omits it. Scalar components broadcast to a common column length;
all columns must match. A length-one column is still a column.

Native Series `.pldt` factories use the receiver as their source column. They
return Pldt eagerly. Class factories also support scalar repetition. Expr
factories retain Polars' separate planning and execution boundaries.

## Numeric seconds, integer microseconds, and instants

`fromseconds` interprets epoch clock seconds, then attaches an optional zone.
`frommicroseconds` uses integer clock microseconds. `fromtimestamp` converts
POSIX seconds to a target zone, or to naive system-local clock fields if no
target is provided. `utcfromtimestamp` fixes the target at UTC.

Output `unit` never changes those input units. The numeric factories default
to us, or ns when a real finer tail is present. Explicit output must be lossless.

```{doctest} pldt-numeric-factories
>>> from datetime import date, datetime, time, timedelta, timezone
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt, Configs
>>> attached = Pldt.fromseconds(0, size=2, tz='Asia/Shanghai', name='event')
>>> converted = Pldt.fromtimestamp([0, 1], tz='Asia/Shanghai')
>>> (type(attached) is Pldt, attached.dtype, attached.hour.to_list(), converted.hour.to_list())
(True, Datetime(time_unit='us', time_zone='Asia/Shanghai'), [0, 0], [8, 8])
>>> (Pldt.fromseconds([1.5], unit='ms').to_physical().to_list(), Pldt.frommicroseconds([1000], unit='ms').to_physical().to_list())
([1500], [1])
>>> tail = Pldt.fromseconds([1e-9, -1e-9, None])
>>> (tail.dtype, tail.to_physical().to_list())
(Datetime(time_unit='ns', time_zone=None), [1, -1, None])
>>> for name in ('fromseconds', 'frommicroseconds', 'fromtimestamp', 'utcfromtimestamp'):
...     factory = getattr(Pldt, name)
...     assert type(factory(0, size=0)) is Pldt and len(factory(0, size=0)) == 0
...     assert factory([0, None]).is_null().to_list() == [False, True]
...     for call in (lambda: factory(0), lambda: factory([0], size=1)):
...         try:
...             call()
...         except ValueError:
...             continue
...         raise AssertionError('size role was bypassed')
>>> seconds = pl.Series('input', [0, 1, None])
>>> for name in ('fromseconds', 'frommicroseconds', 'fromtimestamp', 'utcfromtimestamp'):
...     kwargs = {} if name == 'utcfromtimestamp' else {'tz': 'UTC'}
...     result = getattr(seconds.pldt, name)(**kwargs)
...     expected = [0, 1, None] if name == 'frommicroseconds' else [0, 1000000, None]
...     assert type(result) is Pldt and result.dtype == pl.Datetime('us', 'UTC')
...     assert result.name == 'input' and result.to_physical().to_list() == expected
>>> for call, exception in ((lambda: Pldt.frommicroseconds([1.0]), TypeError), (lambda: Pldt.fromseconds([True]), TypeError), (lambda: Pldt.fromtimestamp(['1']), TypeError), (lambda: Pldt.fromseconds([1.5], unit='ms', size=1), ValueError), (lambda: Pldt.frommicroseconds([1500], unit='ms'), ValueError), (lambda: Pldt.fromseconds(0, size=-1), ValueError), (lambda: Pldt.fromseconds(0, size=True), TypeError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid numeric factory argument accepted')
```

## Date, datetime, and NumPy sources

`fromdate` takes Y/M/D at midnight, discarding the source clock and zone.
`fromdatetime` keeps complete source fields and known instants without a target;
an explicit target replaces the zone while keeping clock fields. NumPy dates
use `fromdatetime64`, which reads the real unit and multiplier and attaches
an optional target without moving the decoded clock.

```{doctest} pldt-date-source-factories
>>> source = datetime(1970, 1, 1, 8, tzinfo=timezone(timedelta(hours=8)))
>>> (Pldt.fromdate(source, size=1).isoformat().to_list(), Pldt.fromdatetime(source, size=1, tz='UTC').isoformat().to_list())
(['1970-01-01T00:00:00'], ['1970-01-01T08:00:00+00:00'])
>>> kept = Pldt.fromdatetime(source, size=0)
>>> (len(kept), kept.dtype == pl.Datetime('us', 'Etc/GMT-8'))
(0, True)
>>> native = pl.Series('event', [123, None], dtype=pl.Int64).cast(pl.Datetime('ns', 'UTC'))
>>> for factory in (Pldt.fromdatetime, lambda values: values.pldt.fromdatetime()):
...     result = factory(native)
...     assert type(result) is Pldt and result.dtype == pl.Datetime('ns', 'UTC')
...     assert result.to_physical().to_list() == [123, None] and result.name == 'event'
>>> for result in (Pldt.fromdate(native), native.pldt.fromdate()):
...     assert type(result) is Pldt and result.dtype == pl.Datetime('ns')
...     assert result.to_physical().to_list() == [0, None]
>>> numpy_dates = np.array([1, -1, 'NaT'], dtype='datetime64[10D]')
>>> decoded = Pldt.fromdatetime64(numpy_dates)
>>> (decoded.dtype, decoded.to_physical().to_list())
(Datetime(time_unit='ms', time_zone=None), [864000000, -864000000, None])
>>> for factory, scalar in ((Pldt.fromdate, date(2024, 2, 29)), (Pldt.fromdatetime, datetime(2024, 2, 29)), (Pldt.fromdatetime64, np.datetime64('2024-02-29'))):
...     result = factory(scalar, size=2, tz='UTC')
...     assert type(result) is Pldt and result.day.to_list() == [29, 29] and result.dtype.time_zone == 'UTC'
...     assert factory([scalar, None]).is_null().to_list() == [False, True]
>>> for call in (lambda: Pldt.fromdate(['2024-01-01']), lambda: Pldt.fromdatetime([date(2024, 1, 1)]), lambda: Pldt.fromdatetime64([0]), lambda: Pldt.fromdatetime(np.array([0], dtype='datetime64[s]'))):
...     try:
...         call()
...     except TypeError:
...         continue
...     raise AssertionError('wrong source factory accepted')
```

## Calendar coordinates and row components

Gregorian ordinal 1 is 0001-01-01; zero and negative ordinals are valid.
ISO weekday uses Monday=1 through Sunday=7. High ISO week/day and day-of-year
values select the real last week/Sunday or year end; values below one fail.
Calendar-coordinate factories default explicitly to us; their `unit` parameter
is a required unit value when supplied and does not accept None as inference.

```{doctest} pldt-calendar-factories
>>> Pldt.fromordinal([1, 0, -1]).isoformat().to_list()
['0001-01-01T00:00:00', '0000-12-31T00:00:00', '0000-12-30T00:00:00']
>>> iso = Pldt.fromisocalendar([2024, 2015, None], [9, 53, 1], 4)
>>> (iso.dtype, iso.isoformat().to_list())
(Datetime(time_unit='us', time_zone=None), ['2024-02-29T00:00:00', '2015-12-31T00:00:00', None])
>>> Pldt.fromisocalendar(2024, 99, 99, size=1).isoformat().to_list()
['2024-12-29T00:00:00']
>>> Pldt.fromdayofyear([2024, 2023, 0], [60, 999, 60]).isoformat().to_list()
['2024-02-29T00:00:00', '2023-12-31T00:00:00', '0000-02-29T00:00:00']
>>> years = pl.Series('year', [2024, 2023, None])
>>> (years.pldt.fromdayofyear(60).isoformat().to_list(), years.pldt.fromisocalendar(1, 1).year.to_list())
(['2024-02-29T00:00:00', '2023-03-01T00:00:00', None], [2024, 2023, None])
>>> pl.Series('ordinal', [738945, None]).pldt.fromordinal().day.to_list()
[29, None]
>>> for call, exception in ((lambda: Pldt.fromisocalendar([2024, 2023], [1], 1), ValueError), (lambda: Pldt.fromdayofyear(2024, 0, size=1), ValueError), (lambda: Pldt.fromordinal([1.0]), TypeError), (lambda: Pldt.fromdayofyear([True], 1), TypeError), (lambda: Pldt.fromordinal([1], unit=None), TypeError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid calendar component accepted')
```

## ISO text, explicit formats, and combined clocks

ISO construction is lossless at an explicit unit. `strptime` instead reads the
complete fractional input, then truncates at its chosen output unit. Configs
controls its month/weekday/AMPM and registered-zone names. Omitted format year
uses 1900. `combine` takes Y/M/D from the date component and clock/zone from
the time component; an explicit target replaces that clock's zone.

```{doctest} pldt-text-and-combine-factories
>>> text = '1970-01-01T00:00:00.123456789+00:00'
>>> iso = Pldt.fromisoformat([text, None])
>>> (iso.dtype, iso.to_physical().to_list(), pl.Series('text', [text, None]).pldt.fromisoformat().to_physical().to_list())
(Datetime(time_unit='ns', time_zone='UTC'), [123456789, None], [123456789, None])
>>> config = Configs()
>>> config.add_month('harvest', 10)
True
>>> Pldt.strptime(['7 harvest 2024'], '%d %b %Y', cfg=config).month.to_list()
[10]
>>> fraction = '1970-01-01 00:00:00.123456789'
>>> (Pldt.strptime(fraction, '%Y-%m-%d %H:%M:%S.%f', size=1).dtype, pl.Series('text', [fraction, None]).pldt.strptime('%Y-%m-%d %H:%M:%S.%f', unit='us').to_physical().to_list())
(Datetime(time_unit='ns', time_zone=None), [123456, None])
>>> Pldt.strptime(['12:30.5'], '%H:%M.%f').isoformat().to_list()
['1900-01-01T12:30:00.500000']
>>> clocks = pl.Series('clock', [34200000000123, None], dtype=pl.Int64).cast(pl.Time)
>>> combined = Pldt.combine(date(2024, 1, 2), clocks)
>>> (combined.dtype, combined.isoformat().to_list())
(Datetime(time_unit='ns', time_zone=None), ['2024-01-02T09:30:00.000000123', None])
>>> pl.Series('date', [date(2024, 1, 2), None]).pldt.combine('09:30').hour.to_list()
[9, None]
>>> for call, exception in ((lambda: Pldt.fromisoformat(['not ISO']), ValueError), (lambda: Pldt.strptime(['2024-01-02extra'], '%Y-%m-%d'), ValueError), (lambda: Pldt.combine([date(2024, 1, 2)], ['09:30', '10:30']), ValueError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid formatted or combined source accepted')
```

## Current time is read once per nonempty call

`now(size)` and `today(size)` repeat a complete naive local clock;
`utcnow(size)` is aware UTC. An explicit zone in now converts the current
instant. Empty results retain selected metadata without reading the clock.
Requested ns storage retains available system precision and does not promise
one-nanosecond clock accuracy.

```{doctest} pldt-current-time-factories
>>> import time as time_module
>>> before = time_module.time_ns()
>>> current = Pldt.utcnow(3, unit='ns', name='sample')
>>> after = time_module.time_ns()
>>> ticks = current.to_physical().to_list()
>>> (type(current) is Pldt, current.dtype, current.name, len(set(ticks)), before <= ticks[0] <= after)
(True, Datetime(time_unit='ns', time_zone='UTC'), 'sample', 1, True)
>>> for factory in (Pldt.now, Pldt.today):
...     before = datetime.now()
...     result = factory(3)
...     after = datetime.now()
...     assert type(result) is Pldt and result.dtype == pl.Datetime('us')
...     assert len(set(result.to_physical().to_list())) == 1 and before <= result[0] <= after
>>> for unit in ('ms', 'us', 'ns'):
...     result = Pldt.now(0, tz='UTC', unit=unit)
...     assert len(result) == 0 and result.dtype == pl.Datetime(unit, 'UTC')
>>> for invalid, exception in ((-1, ValueError), (True, TypeError), (1.0, TypeError)):
...     try:
...         Pldt.utcnow(invalid)
...     except exception:
...         continue
...     raise AssertionError('invalid clock size accepted')
```
