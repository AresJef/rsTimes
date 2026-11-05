# Export and format pandas dates

Choose the destination for its precision, timezone, and capacity. An explicit
output can intentionally lose precision according to its contract; ordinary
Pddt construction and fixed-unit date arithmetic remain lossless.

## Epoch numbers and local NumPy clocks

`toseconds` returns float64 seconds; `tomicroseconds` returns nullable Int64
microseconds and floors nanoseconds only at this output. Their default is a
local wall-clock coordinate. `utc=True` uses aware instants instead. `timestamp`
always requests a Unix instant, interpreting naive dates in the process-local
zone. `values_naive` removes a zone while keeping the local clock, whereas
inherited `values` exposes UTC coordinates for aware dates.

```{doctest} pddt-numeric-and-numpy-output
>>> from datetime import date, datetime, time, timedelta, timezone
>>> import numpy as np
>>> import pandas as pd
>>> from rstimes import Pddt, Pydt
>>> wall = Pddt(['1970-01-01T08:00:00.000000123', None], tz='Asia/Shanghai', name='event')
>>> (wall.toseconds().tolist(), wall.toseconds(utc=True).tolist(), wall.timestamp().tolist())
([28800.000000123, nan], [1.23e-07, nan], [1.23e-07, nan])
>>> (wall.tomicroseconds().tolist(), wall.tomicroseconds(utc=True).tolist())
([28800000000, <NA>], [0, <NA>])
>>> (str(wall.toseconds().dtype), str(wall.tomicroseconds().dtype), wall.toordinal().tolist())
('float64', 'Int64', [719163, <NA>])
>>> (wall.values_naive.dtype, wall.values_naive.view('int64').tolist(), wall.values.view('int64').tolist())
(dtype('<M8[ns]'), [28800000000123, -9223372036854775808], [123, -9223372036854775808])
>>> Pddt([-1, None], unit='ns').tomicroseconds().tolist()
[-1, <NA>]
>>> for unit, scale in (('s', 1), ('ms', 1000), ('us', 1000000), ('ns', 1000000000)):
...     result = Pddt([1, -1], unit=unit).toseconds()
...     assert result.tolist() == [1 / scale, -1 / scale]
>>> fractional_offset = Pddt([0], unit='ms', tz=timezone(timedelta(microseconds=500)))
>>> try:
...     fractional_offset.values_naive
... except ValueError as error:
...     print(type(error).__name__)
ValueError
>>> fractional_offset.as_unit('us').values_naive.view('int64').tolist()
[500]
>>> for call, exception in ((lambda: wall.toseconds(utc=1), TypeError), (lambda: wall.tomicroseconds(utc=None), TypeError), (lambda: Pddt([2**63-1], unit='s').tomicroseconds(), OverflowError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid numeric export accepted')
```

Floats cannot distinguish every nanosecond far from the epoch. `asi8` keeps the
exact stored ticks at `unit`, but uses the reserved NaT sentinel at missing
rows. Always carry the unit and timezone when exchanging those integers.

## Nullable calendar tables

`timedf` and `utctimedf` return DataFrames with a positional RangeIndex, not a
date index. Their nine columns have fixed nullable integer dtypes. All fields
are missing for NaT. The local DST marker is −1 for an unspecified adjustment,
0 for zero, and 1 for a legal nonzero adjustment; UTC uses 0.

```{doctest} pddt-calendar-table-output
>>> local, utc = wall.timedf(), wall.utctimedf()
>>> keys = ['tm_year', 'tm_mon', 'tm_mday', 'tm_hour', 'tm_min', 'tm_sec', 'tm_wday', 'tm_yday', 'tm_isdst']
>>> (type(local) is pd.DataFrame, local.columns.tolist(), [str(d) for d in local.dtypes], local.index.equals(pd.RangeIndex(2)))
(True, ['tm_year', 'tm_mon', 'tm_mday', 'tm_hour', 'tm_min', 'tm_sec', 'tm_wday', 'tm_yday', 'tm_isdst'], ['Int64', 'Int8', 'Int8', 'Int8', 'Int8', 'Int8', 'Int8', 'Int16', 'Int8'], True)
>>> (local.iloc[0].tolist(), utc.iloc[0].tolist(), local.iloc[1].isna().all(), utc.iloc[1].isna().all())
([1970, 1, 1, 8, 0, 0, 3, 1, 0], [1970, 1, 1, 0, 0, 0, 3, 1, 0], np.True_, np.True_)
>>> Pddt(['1970-01-01']).timedf()['tm_isdst'].tolist()
[-1]
>>> Pddt(['1970-01-01'], tz=timezone.utc).timedf()['tm_isdst'].tolist()
[-1]
>>> for method in ('timedf', 'utctimedf'):
...     empty = getattr(Pddt([]), method)()
...     assert empty.shape == (0, 9) and empty.columns.tolist() == keys
...     assert [str(d) for d in empty.dtypes] == ['Int64', 'Int8', 'Int8', 'Int8', 'Int8', 'Int8', 'Int8', 'Int16', 'Int8']
```

## Python date/time objects and fold

`datetime()` returns an object ndarray of Pydt, with pd.NaT at missing rows.
`date`, `time`, and `timetz` are properties returning object ndarrays of the
corresponding standard-library type. Clock output floors to microseconds;
time drops the zone, while timetz retains it. Regional folds survive.
Date/datetime objects must fit years 1–9999 even when the Pddt can store more.

```{doctest} pddt-object-output
>>> repeated = Pddt(np.array(['2024-11-03T05:30:00.123456789', '2024-11-03T06:30:00.123456789', 'NaT'], dtype='datetime64[ns]'), tz='UTC').tz_convert('America/New_York')
>>> objects = repeated.datetime()
>>> (type(objects) is np.ndarray, objects.dtype == object, [type(v) is Pydt for v in objects[:2]], [v.fold for v in objects[:2]], [v.microsecond for v in objects[:2]], objects[2] is pd.NaT)
(True, True, [True, True], [0, 1], [123456, 123456], True)
>>> for name, expected_type in (('date', date), ('time', time), ('timetz', time)):
...     result = getattr(repeated, name)
...     assert type(result) is np.ndarray and result.dtype == object
...     assert all(type(item) is expected_type for item in result[:2]) and result[2] is pd.NaT
>>> ([v.fold for v in repeated.time[:2]], [v.tzinfo is None for v in repeated.time[:2]], [v.tzinfo is repeated.tz for v in repeated.timetz[:2]])
([0, 1], [True, True], [True, True])
>>> repeated.date.tolist()
[datetime.date(2024, 11, 3), datetime.date(2024, 11, 3), NaT]
>>> wide = Pddt(['0000-01-01'], unit='us')
>>> (wide.toordinal().tolist(), wide.time[0].isoformat(), wide.ctime().tolist())
([-365], '00:00:00', ['Sat Jan  1 00:00:00 0000'])
>>> for operation in (lambda: wide.datetime(), lambda: wide.date):
...     try:
...         operation()
...     except ValueError:
...         continue
...     raise AssertionError('Python object exceeded year capacity')
```

## ISO display and exact fractional formatting

ISO auto display uses nine fraction digits for a nonzero nanosecond tail,
six for a nonzero microsecond fraction without that tail, and none for a whole
second. An explicit timespec fixes the display precision and truncates text
without changing dates. Separator is exactly one Unicode character.

`strftime('%f')` has a separate rule: nine digits for ns storage, six for
s/ms/us. Explicit `%.1f`–`%.9f` includes a dot and truncates or pads;
`%.0f` emits nothing. Other directives keep the platform/pandas system rules.

```{doctest} pddt-text-output
>>> fraction = Pddt(['2024-02-29T12:34:56.123456789', None], name='event')
>>> specs = {'auto': '12:34:56.123456789', 'hours': '12', 'h': '12', 'minutes': '12:34', 'm': '12:34', 'min': '12:34', 'seconds': '12:34:56', 's': '12:34:56', 'milliseconds': '12:34:56.123', 'ms': '12:34:56.123', 'microseconds': '12:34:56.123456', 'us': '12:34:56.123456', 'nanoseconds': '12:34:56.123456789', 'ns': '12:34:56.123456789'}
>>> for spec, clock in specs.items():
...     rendered = fraction.isoformat(sep='日', timespec=spec)
...     assert type(rendered) is pd.Index and rendered.name == 'event'
...     assert rendered.dropna().tolist() == ['2024-02-29日' + clock] and rendered.isna().tolist() == [False, True]
>>> [Pddt([123456789], unit='ns').strftime('%.' + str(p) + 'f')[0] for p in range(10)]
['', '.1', '.12', '.123', '.1234', '.12345', '.123456', '.1234567', '.12345678', '.123456789']
>>> for unit, tick, expected in (('s', 0, '000000'), ('ms', 123, '123000'), ('us', 123456, '123456'), ('ns', 123456789, '123456789')):
...     assert Pddt([tick], unit=unit).strftime('%f').tolist() == [expected]
>>> (fraction.strftime('%%f|%.3f|%.9f|%.0f').dropna().tolist(), fraction.strftime('').dropna().tolist())
(['%f|.123|.123456789|'], [''])
>>> Pddt(['2024-02-29 12:34:56']).ctime().tolist()
['Thu Feb 29 12:34:56 2024']
>>> for call, exception in ((lambda: fraction.isoformat(sep=''), ValueError), (lambda: fraction.isoformat(sep='XX'), ValueError), (lambda: fraction.isoformat(timespec='unknown'), ValueError), (lambda: fraction.strftime(None), TypeError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid display option accepted')
```

Month/weekday names use bundled CLDR data, independent of Configs parser
vocabulary. `tzname()` returns object Index with actual names or None.
Other text outputs use the installed pandas version's string missing form,
as shown in [factory outputs](pddt-factories.md).

```{doctest} pddt-localized-and-zone-text
>>> (fraction.month_name().dropna().tolist(), fraction.weekday_name('fr_FR').dropna().tolist())
(['February'], ['jeudi'])
>>> for method in ('month_name', 'weekday_name'):
...     for locale, exception in (('no_such_locale', ValueError), (1, TypeError)):
...         try:
...             getattr(fraction, method)(locale)
...         except exception:
...             continue
...         raise AssertionError((method, locale))
>>> seasonal = Pddt(['2024-01-01', '2024-07-01', None], tz='America/New_York')
>>> (seasonal.tzname().tolist(), seasonal.tzname().dtype == object, Pddt(['2024-01-01', None]).tzname().tolist())
(['EST', 'EDT', None], True, [None, None])
```

## A naive timestamp needs a local interpretation

Use `tz_localize` with explicit policies before converting a repeated or missing
local clock to timestamp. This isolated example verifies that failure without
changing an existing process's local-zone cache.

```{doctest} pddt-naive-timestamp-local
>>> import os, subprocess, sys
>>> program = '\n'.join([
...     'from rstimes import Pddt',
...     "for text in ('2024-03-10 02:30', '2024-11-03 01:30'):",
...     '    try: Pddt([text]).timestamp()',
...     "    except ValueError as error: assert 'tz_localize' in str(error)",
...     "    else: raise AssertionError('ambiguous local timestamp was guessed')",
... ])
>>> result = subprocess.run([sys.executable, '-I', '-c', program], env=dict(os.environ, TZ='America/New_York'), capture_output=True, text=True, check=True, timeout=20)
>>> (result.returncode, result.stdout, result.stderr)
(0, '', '')
```
