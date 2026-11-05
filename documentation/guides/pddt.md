# Dates in a pandas index

Pddt is a real pandas DatetimeIndex subclass. It holds an ordered, one-dimensional
date column, its unit and timezone, its name, and missing positions. Install the
pandas extra to use it. Scalar datetimes belong in Pydt; a one-row Pddt still
uses a collection such as `[value]`.

## Numeric construction uses ticks

Numeric construction treats values as ticks in the selected unit. Supported
units are `s`, `ms`, `us`, and `ns`; numbers without an explicit unit mean ns.
This differs from `Pddt.fromseconds`, which always reads seconds.

```{doctest} pddt-construction-unit
>>> from datetime import date, datetime, timedelta, timezone
>>> import numpy as np
>>> import pandas as pd
>>> from rstimes import Pddt, Configs
>>> value = Pddt([1], unit='ms', name='event')
>>> (type(value) is Pddt, value.unit, value.name, value.asi8.tolist())
(True, 'ms', 'event', [1])
>>> for unit in ('s', 'ms', 'us', 'ns'):
...     result = Pddt([1, -1, None], unit=unit, name='event')
...     assert type(result) is Pddt and result.unit == unit and result.name == 'event'
...     assert result.asi8.tolist() == [1, -1, -9223372036854775808]
...     assert result.isna().tolist() == [False, False, True]
>>> (Pddt([1]).unit, Pddt([1.0]).asi8.tolist(), Pddt([-2**63], unit='us').isna().tolist())
('ns', [1], [True])
>>> (Pddt([0], tz='Asia/Shanghai').hour.tolist(), Pddt(['1970-01-01'], tz='Asia/Shanghai').hour.tolist())
([8], [0])
```

Numbers with a target timezone represent UTC instants converted to that zone.
Naive date text instead supplies local clock fields to attach to that zone.
An explicit unit must retain every nonmissing source instant exactly.

## Input containers and source resolution

Lists, tuples, single-use iterators, one-dimensional NumPy arrays, pandas
Series/Index and supported extension arrays are accepted by their actual
element roles. A source Series/Index name is retained unless overridden.
Rows are read by position, without label alignment. Native temporal sources
retain their resolution; mixed inputs select the finer required resolution.

```{doctest} pddt-input-containers
>>> containers = [[0, 1, None], (0, 1, None), iter([0, 1, None]), pd.Series([0, 1, pd.NA], dtype='Int64', name='event'), pd.Index([0, 1, None]), pd.array([0, 1, None], dtype='Int64')]
>>> for data in containers:
...     result = Pddt(data, unit='s')
...     assert type(result) is Pddt and result.asi8.tolist() == [0, 1, -9223372036854775808]
>>> inherited_name = Pddt(pd.Series([0, 1], index=['second', 'first'], name='event'), unit='ms')
>>> (inherited_name.name, inherited_name.asi8.tolist())
('event', [0, 1])
>>> (Pddt(inherited_name, name=('renamed', 1)).name, Pddt([0], name=True).name)
(('renamed', 1), True)
>>> source = np.arange(6, dtype='int64').view('datetime64[s]')[::2]
>>> result = Pddt(source)
>>> (result.unit, result.asi8.tolist())
('s', [0, 2, 4])
>>> for unit in ('s', 'ms', 'us', 'ns'):
...     source = pd.DatetimeIndex(np.array([1, 2], dtype='datetime64[' + unit + ']'), name='source')
...     result = Pddt(source)
...     assert result.unit == unit and result.name == 'source' and result.asi8.tolist() == [1, 2]
>>> inferred = [(Pddt(['1970-01-01']), 'us'), (Pddt(['1970-01-01T00:00:00.000000000']), 'ns'), (Pddt([date(1970, 1, 1)]), 's'), (Pddt([datetime(1970, 1, 1)]), 'us'), (Pddt([np.datetime64(0, 'D')]), 's')]
>>> assert all(result.unit == expected for result, expected in inferred)
>>> mixed = Pddt([date(1970, 1, 1), datetime(1970, 1, 1, 0, 0, 1), np.datetime64(123, 'ns'), None])
>>> (mixed.unit, mixed.asi8.tolist())
('ns', [0, 1000000000, 123, -9223372036854775808])
>>> for invalid, exception in ((None, TypeError), (0, TypeError), ('2024-01-01', TypeError), (np.array(0), ValueError), (np.array([[0]]), ValueError), (pd.DataFrame({'date': [0]}), TypeError)):
...     try:
...         Pddt(invalid)
...     except exception:
...         continue
...     raise AssertionError('invalid outer shape accepted')
```

## Missing values and empty columns

Date missing values are retained rather than deleted or replaced by `default`.
Supported whole-text missing markers are exact, including the empty string.
Whitespace is not automatically stripped to create a missing marker.
The int64 minimum tick is pandas' reserved NaT value in a date buffer.

```{doctest} pddt-missing-and-empty
>>> markers = [None, pd.NaT, pd.NA, np.nan, np.datetime64('NaT'), '', 'NaT', 'NAT', 'nat', 'NaN', 'NAN', 'nan']
>>> missing = Pddt(markers, unit='ns', name='missing')
>>> (missing.isna().tolist(), len(missing), missing.name, missing.unit)
([True, True, True, True, True, True, True, True, True, True, True, True], 12, 'missing', 'ns')
>>> for strict in (False, True):
...     assert Pddt(markers, strict=strict).isna().all()
>>> (Pddt([]).unit, Pddt([None, pd.NA, np.nan]).unit, Pddt(np.array([], dtype='float64')).unit, Pddt(np.array([np.nan])).unit)
('s', 's', 'ns', 'ns')
>>> empty = Pddt(np.array([], dtype='datetime64[ms]'), tz='UTC', name='empty')
>>> (type(empty) is Pddt, len(empty), empty.unit, str(empty.tz), empty.name)
(True, 0, 'ms', 'UTC', 'empty')
>>> for text in (' ', 'None', 'null', 'nAt', ' NaT '):
...     try:
...         Pddt([text])
...     except ValueError:
...         continue
...     raise AssertionError(text)
>>> for invalid in (True, np.bool_(False), b'2024-01-01', np.timedelta64('NaT')):
...     try:
...         Pddt([invalid])
...     except TypeError:
...         continue
...     raise AssertionError('unsupported element became NaT')
```

## Explicitly reduce precision

`as_unit` defaults to `round_ok=True`. It rounds toward the earlier tick, so
minus one nanosecond becomes minus one microsecond rather than zero. Set
`round_ok=False` when the conversion must preserve the exact instant.

```{doctest} pddt-negative-unit
>>> source = Pddt([-1], unit='ns', name='event')
>>> coarse = source.as_unit('us')
>>> (type(coarse) is Pddt, coarse.unit, coarse.name, coarse.asi8.tolist())
(True, 'us', 'event', [-1])
>>> try:
...     source.as_unit('us', round_ok=False)
... except ValueError as error:
...     print(type(error).__name__, 'cannot preserve' in str(error))
ValueError True
>>> source.asi8.tolist()
[-1]
```

An existing Pddt keeps its unit during date operations. A nonzero result too
fine for that unit raises ValueError, and an out-of-capacity result raises
OverflowError. First convert explicitly when finer storage is your intention.
`as_unit` changes resolution, preserving timezone, name, and missing positions;
it does not relocalize the dates.

```{doctest} pddt-lossless-construction
>>> fine = np.array([123, -1500], dtype='datetime64[ns]')
>>> for data in (fine, ['1970-01-01T00:00:00.000000123']):
...     try:
...         Pddt(data, unit='us')
...     except ValueError:
...         continue
...     raise AssertionError('construction lost nanoseconds')
>>> Pddt(fine).as_unit('us').asi8.tolist()
[0, -2]
>>> ordinary = Pddt([0, None], unit='s', tz='UTC', name='event')
>>> precise = ordinary.as_unit('ns')
>>> (type(precise) is Pddt, precise.unit, precise.name, str(precise.tz), precise.asi8.tolist())
(True, 'ns', 'event', 'UTC', [0, -9223372036854775808])
>>> for unit in ('s', 'ms', 'us', 'ns'):
...     assert ordinary.as_unit(unit, round_ok=False).asi8.tolist() == [0, -9223372036854775808]
>>> try:
...     ordinary.add(nanoseconds=1)
... except ValueError as error:
...     print(type(error).__name__)
ValueError
>>> ordinary.as_unit('ns').add(nanoseconds=1).asi8.tolist()
[1, -9223372036854775808]
>>> wide = Pddt(['0000-02-29', '9999-01-01'], unit='us')
>>> (wide.year.tolist(), wide.add(years=1).year.tolist())
([0, 9999], [1, 10000])
>>> try:
...     wide.as_unit('ns')
... except OverflowError as error:
...     print(type(error).__name__)
OverflowError
```

## Parser options, defaults, and errors

`Pddt.parse` uses the same constructor contract. Ordering preferences override
Configs when explicit. A complete default only supplies missing date fields;
it is prepared only if text actually needs it. `strict` rejects invalid explicit
fields and is independent of regional DST strategies.

```{doctest} pddt-parse-options
>>> config = Configs(dayfirst=True)
>>> config.add_month('harvest', 10)
True
>>> parsed = Pddt.parse(['01/02/2024', '7 harvest 2024', None], cfg=config)
>>> (type(parsed) is Pddt, parsed.month.tolist(), parsed.isna().tolist())
(True, [2.0, 10.0, nan], [False, False, True])
>>> Pddt.parse(['01/02/2024'], cfg=config, dayfirst=False).month.tolist()
[1]
>>> Pddt(['February 29'], default=datetime(2024, 1, 1, 12, tzinfo=timezone.utc)).isoformat().tolist()
['2024-02-29T00:00:00']
>>> (Pddt([], default=object()).empty, Pddt([0], default=object()).asi8.tolist())
(True, [0])
>>> Pddt(['2024-02-31']).isoformat().tolist()
['2024-02-29T00:00:00']
>>> try:
...     Pddt(['2024-02-31'], strict=True)
... except ValueError as error:
...     print(type(error).__name__)
ParseError
>>> Pddt(['2024-02-29'], isoformat=False).day.tolist()
[29]
>>> for option in ('copy', 'strict', 'isoformat', 'yearfirst', 'dayfirst'):
...     try:
...         Pddt([], **{option: 1})
...     except TypeError:
...         continue
...     raise AssertionError(option)
>>> for call, exception in ((lambda: Pddt([0], unit='D'), ValueError), (lambda: Pddt([0], unit=1), TypeError), (lambda: ordinary.as_unit('ms', round_ok=1), TypeError), (lambda: Pddt([0], cfg={}), TypeError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid constructor option accepted')
```

Inherited pandas attributes keep pandas return types and missing-value forms.
For example, `month` above uses a floating Index when NaT is present; the
library's own nullable integer queries are described in the query guide.
