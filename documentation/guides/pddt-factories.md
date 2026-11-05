# Build pandas date columns with factories

Named factories specify the source's role. They return Pddt, preserving order,
missing positions, the selected resolution, and an inherited or explicit name.
A scalar source requires `size`; a collection omits it. A length-one collection
remains a column and does not become a broadcast scalar.

| Factory | Source meaning |
|---|---|
| `fromseconds` | Numeric seconds on the naive 1970-01-01 clock; optional zone attaches. |
| `frommicroseconds` | Integer microseconds on that clock; optional zone attaches. |
| `fromtimestamp` | Numeric POSIX seconds; target zone converts the instant; omitted target uses naive system-local fields. |
| `utcfromtimestamp` | POSIX seconds with standard UTC output. |
| `fromdate` | Real date/datetime or matching native date column; Y/M/D at midnight, source zone discarded. |
| `fromdatetime` | Real datetime/Timestamp or matching native Datetime column; retain fields and source zone; an explicit zone replaces it without moving the clock. |
| `fromdatetime64` | Real NumPy datetime64 scalar/array; actual unit and multiplier; optional zone attaches. |
| `fromordinal` | Integer Gregorian ordinal, including zero and negative days. |
| `fromisocalendar` | Separate integer year, ISO week, and ISO weekday (Monday=1). |
| `fromdayofyear` | Separate integer year and one-based day of year. |
| `fromisoformat` | ISO text with its complete source precision and timezone. |
| `strptime` | Text plus a shared explicit format; truncate fraction at the final requested unit. |
| `combine` | Date fields from one source, clock/zone from another. |

## Scalars, columns, and numeric units

```{doctest} pddt-factory-sizes-and-numbers
>>> from datetime import date, datetime, time, timedelta, timezone
>>> import numpy as np
>>> import pandas as pd
>>> from rstimes import Pddt, Configs
>>> attached = Pddt.fromseconds(0, size=2, tz='Asia/Shanghai', name='event')
>>> converted = Pddt.fromtimestamp([0, 1], tz='Asia/Shanghai')
>>> (type(attached) is Pddt, attached.hour.tolist(), attached.name, converted.hour.tolist())
(True, [0, 0], 'event', [8, 8])
>>> (Pddt.fromseconds([1.5], unit='ms').asi8.tolist(), Pddt.frommicroseconds([1000], unit='ms').asi8.tolist())
([1500], [1])
>>> (Pddt.fromseconds([1e-9, -1e-9]).unit, Pddt.fromseconds([1e-9, -1e-9]).asi8.tolist())
('ns', [1, -1])
>>> (Pddt.utcfromtimestamp([0, None]).asi8.tolist(), str(Pddt.utcfromtimestamp([0]).tz))
([0, -9223372036854775808], 'UTC')
>>> for factory in (Pddt.fromseconds, Pddt.frommicroseconds, Pddt.fromtimestamp, Pddt.utcfromtimestamp):
...     assert type(factory(0, size=0)) is Pddt and factory(0, size=0).empty
...     assert factory([0, None]).isna().tolist() == [False, True]
...     try:
...         factory(0)
...     except ValueError:
...         pass
...     else:
...         raise AssertionError('scalar factory omitted size')
...     try:
...         factory([0], size=1)
...     except ValueError:
...         pass
...     else:
...         raise AssertionError('collection factory accepted size')
>>> for call, exception in ((lambda: Pddt.frommicroseconds([1.0]), TypeError), (lambda: Pddt.fromseconds([True]), TypeError), (lambda: Pddt.fromtimestamp(['1']), TypeError), (lambda: Pddt.fromseconds([1.5], unit='s'), ValueError), (lambda: Pddt.frommicroseconds([1500], unit='ms'), ValueError), (lambda: Pddt.fromseconds(0, size=-1), ValueError), (lambda: Pddt.fromseconds(0, size=True), TypeError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid factory role accepted')
```

## Real date sources retain their roles

Ordinary construction with a target timezone converts an aware instant.
`fromdatetime` with an explicit target instead reinterprets its clock fields.
`fromdate` takes only the calendar date, even from a precise aware Timestamp.
An empty repeated scalar keeps a determinable source timezone.

```{doctest} pddt-date-source-factories
>>> source = pd.Timestamp('1970-01-01 08:00:00.000000123', tz='Asia/Shanghai')
>>> ordinary = Pddt([source], tz='UTC')
>>> fields = Pddt.fromdatetime(source, size=1, tz='UTC')
>>> (ordinary.unit, ordinary.asi8.tolist(), fields.unit, fields.asi8.tolist())
('ns', [123], 'ns', [28800000000123])
>>> (Pddt.fromdate(source, size=1).isoformat().tolist(), Pddt.fromdate(source, size=1, tz='UTC').isoformat().tolist())
(['1970-01-01T00:00:00'], ['1970-01-01T00:00:00+00:00'])
>>> kept = Pddt.fromdatetime(source, size=0)
>>> (len(kept), str(kept.tz), kept.unit)
(0, 'Asia/Shanghai', 'ns')
>>> native = np.array([1, -1, 'NaT'], dtype='datetime64[10D]')
>>> decoded = Pddt.fromdatetime64(native)
>>> (decoded.unit, decoded.asi8.tolist(), decoded.isna().tolist())
('s', [864000, -864000, -9223372036854775808], [False, False, True])
>>> for factory, scalar in ((Pddt.fromdate, date(2024, 2, 29)), (Pddt.fromdatetime, datetime(2024, 2, 29)), (Pddt.fromdatetime64, np.datetime64('2024-02-29'))):
...     result = factory(scalar, size=2, tz='UTC')
...     assert type(result) is Pddt and result.day.tolist() == [29, 29] and str(result.tz) == 'UTC'
...     assert factory([scalar, None]).isna().tolist() == [False, True]
>>> for call in (lambda: Pddt.fromdate(['2024-01-01']), lambda: Pddt.fromdatetime([date(2024, 1, 1)]), lambda: Pddt.fromdatetime64([0]), lambda: Pddt.fromdatetime(np.array([0], dtype='datetime64[s]'))):
...     try:
...         call()
...     except TypeError:
...         continue
...     raise AssertionError('wrong source factory accepted')
```

## Calendar coordinates and positional broadcasting

Calendar factories allow zero, negative, and wide years within the selected
unit's capacity. High ISO week/day and day-of-year values select the year's
real last week/Sunday or last day; values below one are errors. All integer
components reject floats and booleans. Missing component values propagate NaT.

```{doctest} pddt-calendar-coordinate-factories
>>> (Pddt.fromordinal([1, 0, -1], unit='us').isoformat().tolist())
['0001-01-01T00:00:00', '0000-12-31T00:00:00', '0000-12-30T00:00:00']
>>> iso = Pddt.fromisocalendar([2024, 2015, None], [9, 53, 1], 4)
>>> (iso.isoformat().dropna().tolist(), iso.isna().tolist())
(['2024-02-29T00:00:00', '2015-12-31T00:00:00'], [False, False, True])
>>> Pddt.fromisocalendar(2024, 99, 99, size=1).isoformat().tolist()
['2024-12-29T00:00:00']
>>> Pddt.fromdayofyear([2024, 2023, 0], [60, 999, 60], unit='us').isoformat().tolist()
['2024-02-29T00:00:00', '2023-12-31T00:00:00', '0000-02-29T00:00:00']
>>> named = Pddt.fromdayofyear(pd.Series([2024, 2023], index=['b', 'a'], name='year'), pd.Series([60, 60], index=['a', 'b']))
>>> (named.name, named.day.tolist(), named.month.tolist())
('year', [29, 1], [2, 3])
>>> for call, exception in ((lambda: Pddt.fromisocalendar([2024, 2023], [1], 1), ValueError), (lambda: Pddt.fromdayofyear(2024, 0, size=1), ValueError), (lambda: Pddt.fromisocalendar(2024, 0, 1, size=1), ValueError), (lambda: Pddt.fromordinal([1.0]), TypeError), (lambda: Pddt.fromdayofyear([True], 1), TypeError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid calendar component accepted')
```

## ISO text, explicit formats, and combined clocks

`fromisoformat` and ordinary construction require a lossless explicit unit.
`strptime` has a different contract: it reads the complete fractional input,
then truncates it once to its final requested resolution. A format without
year uses 1900. Configs supplies month/weekday/AMPM vocabulary and explicitly
registered zone names.

```{doctest} pddt-text-and-combine-factories
>>> iso = Pddt.fromisoformat(['1970-01-01T00:00:00.123456789+00:00', None])
>>> (iso.unit, str(iso.tz), iso.asi8.tolist())
('ns', 'UTC', [123456789, -9223372036854775808])
>>> iso_empty = Pddt.fromisoformat('1970-01-01T08:00:00+08:00', size=0)
>>> (len(iso_empty), iso_empty.tz.utcoffset(None))
(0, datetime.timedelta(seconds=28800))
>>> config = Configs()
>>> config.add_month('harvest', 10)
True
>>> Pddt.strptime(['7 harvest 2024'], '%d %b %Y', cfg=config).month.tolist()
[10]
>>> format_text = '1970-01-01 00:00:00.123456789'
>>> (Pddt.strptime(format_text, '%Y-%m-%d %H:%M:%S.%f', size=1).unit, Pddt.strptime(format_text, '%Y-%m-%d %H:%M:%S.%f', size=1, unit='us').asi8.tolist())
('ns', [123456])
>>> Pddt.strptime(['12:30.5'], '%H:%M.%f').isoformat().tolist()
['1900-01-01T12:30:00.500000']
>>> Pddt.strptime(['2024-01-02 12:00+0800', '2024-01-02 12:00+0900'], '%Y-%m-%d %H:%M%z', tz='UTC').hour.tolist()
[4, 3]
>>> clock = pd.Timestamp('1970-01-01 09:30:00.000000123', tz='Asia/Shanghai')
>>> combined = Pddt.combine([date(2024, 1, 2), None], clock)
>>> (combined.unit, combined.isoformat().dropna().tolist(), combined.isna().tolist())
('ns', ['2024-01-02T09:30:00.000000123+08:00'], [False, True])
>>> Pddt.combine(date(2024, 1, 2), clock, size=1, tz='UTC').isoformat().tolist()
['2024-01-02T09:30:00.000000123+00:00']
>>> for call, exception in ((lambda: Pddt.fromisoformat(['not ISO']), ValueError), (lambda: Pddt.strptime(['2024-01-02extra'], '%Y-%m-%d'), ValueError), (lambda: Pddt.combine([date(2024, 1, 2)], [time(), time()]), ValueError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid formatted/combined input accepted')
```

The text output is a pandas Index and uses that installed pandas version's
string missing representation: NaN with the tested pandas 3, and None with
pandas 2. The date column retains the same NaT positions in both profiles.

```{doctest} pddt-string-missing-representation
>>> rendered = combined.isoformat()
>>> assert type(rendered) is pd.Index and rendered.isna().tolist() == [False, True]
>>> if pd.__version__.split('.')[0] == '3':
...     assert type(rendered[1]) is float and np.isnan(rendered[1])
... else:
...     assert pd.__version__.split('.')[0] == '2' and rendered[1] is None
```

## Read the clock once per nonempty call

`now(size)` and `today(size)` return complete naive local clock values;
`utcnow(size)` is aware UTC. A nonempty call reads the clock once and repeats
that value. Unit `ns` retains the precision available from the system; it is
not a claim of one-nanosecond clock accuracy. An empty result keeps the selected
metadata without reading the current time.

```{doctest} pddt-current-time-factories
>>> before = __import__('time').time_ns()
>>> current = Pddt.utcnow(3, unit='ns', name='sample')
>>> after = __import__('time').time_ns()
>>> (type(current) is Pddt, str(current.tz), current.unit, current.name, len(set(current.asi8.tolist())), before <= int(current.asi8[0]) <= after)
(True, 'UTC', 'ns', 'sample', 1, True)
>>> for factory in (Pddt.now, Pddt.today):
...     before = datetime.now()
...     result = factory(3)
...     after = datetime.now()
...     assert type(result) is Pddt and result.tz is None and result.unit == 'us'
...     assert len(set(result.asi8.tolist())) == 1 and before <= result[0] <= after
>>> for unit in ('s', 'ms', 'us', 'ns'):
...     result = Pddt.now(0, tz='UTC', unit=unit)
...     assert result.empty and result.unit == unit and str(result.tz) == 'UTC'
>>> for invalid, exception in ((-1, ValueError), (True, TypeError), (1.0, TypeError)):
...     try:
...         Pddt.utcnow(invalid)
...     except exception:
...         continue
...     raise AssertionError('invalid size accepted')
```
