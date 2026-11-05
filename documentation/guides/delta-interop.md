# Delta interoperability and precision

Calendar rules are shared; destination containers retain their own resolution,
capacity, timezone rules, and protocols. A standard datetime or Pydt has
microsecond resolution. A Timestamp, Pddt, or Pldt can retain nanoseconds.

## Preserve or replace a nanosecond tail

The following timestamp is one microsecond plus 789 nanoseconds after the Unix
epoch. An absolute nanosecond setting replaces the tail. An absolute
microsecond setting alone clears that tail. Merging the settings is a different
operation from applying the changes successively.

```{doctest} delta-timestamp-fields
>>> import pandas as pd
>>> from rstimes import Delta
>>> source = pd.Timestamp(1789, unit='ns')
>>> a, b = Delta(nanosecond=2), Delta(microsecond=1)
>>> together, successive = source + (a + b), (source + a) + b
>>> (type(together) is pd.Timestamp, together.value, successive.value)
(True, 1002, 1000)
>>> (source + Delta(microseconds=1)).value
2789
>>> (source + Delta(microsecond=0)).value
0
```

## Keep vector units fixed

Pddt uses a NaT sentinel; Polars uses an independent validity bitmap. Both keep
source missing positions during a date transformation. The returned date
container preserves the source unit and name.

```{doctest} delta-vector-nanoseconds
>>> import polars as pl
>>> from rstimes import Pydt, Pddt, Pldt
>>> index = Pddt([1, None], unit='ns', name='event')
>>> shifted_index = index + Delta(nanoseconds=1)
>>> (type(shifted_index) is Pddt, shifted_index.unit, shifted_index.name, shifted_index.asi8.tolist())
(True, 'ns', 'event', [2, -9223372036854775808])
>>> column = Pldt([1, None], unit='ns', name='event')
>>> shifted_column = column + Delta(nanoseconds=1)
>>> (type(shifted_column) is Pldt, shifted_column.dtype == pl.Datetime('ns'), shifted_column.name, shifted_column.to_physical().to_list())
(True, True, 'event', [2, None])
>>> scalar = Pydt(1970, 1, 1) + Delta(nanoseconds=1)
>>> (type(scalar) is Pydt, scalar.microsecond)
(True, 0)
```

One nanosecond cannot be represented by an existing microsecond column. A
normal date operation raises `ValueError` for precision loss and `OverflowError`
for capacity loss. Use `as_unit` explicitly before the operation. Exactly
cancelling fixed contributions are valid: the final change determines precision.

```{doctest} delta-fixed-unit-and-pairing
>>> for dates in (Pddt([0], unit='us'), Pldt([0], unit='us')):
...     try:
...         dates + Delta(nanoseconds=1)
...     except ValueError:
...         continue
...     raise AssertionError('precision loss was accepted')
>>> cancelled = Delta(microseconds=1, nanoseconds=-1000)
>>> (bool(cancelled), (Pddt([0], unit='us') + cancelled).asi8.tolist(), (Pldt([0], unit='us') + cancelled).to_physical().to_list())
(False, [0], [0])
>>> row_changes = [Delta(nanoseconds=1), Delta(nanoseconds=2)]
>>> (Pldt([0, 0], unit='ns') + row_changes).to_physical().to_list()
[1, 2]
>>> try:
...     Pldt([0, 0], unit='ns') + [Delta()]
... except ValueError as error:
...     print(type(error).__name__)
ValueError
>>> try:
...     Pldt([None], unit='ns') + [None]
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```

A scalar Delta broadcasts. A collection of Deltas must match the date column
length exactly; a one-element collection is not a scalar. Missing source dates
do not make a missing Delta operand valid.

## NumPy scalar directions

Ordinary scalar operators preserve the documented source roles. This table
describes the library's normal path; actual custom arithmetic methods retain
their own negotiation and exceptions.

| NumPy scalar | `delta + value` | `value + delta` / `value - delta` |
|---|---|---|
| datetime64 in Y/M/W/D | datetime | date |
| datetime64 in h/m/s/ms/us/ns | datetime | datetime |
| timedelta64 in W/D/h/m/s/ms/us/ns | Delta | Delta |
| timedelta64 in Y/M | Delta | Unsupported |

Datetime outputs round only at the final microsecond destination. NumPy
timedelta years and months, when read by Delta, are average fixed durations
(31,556,952 and 2,629,746 seconds); they do not become relative calendar fields.
Subnanosecond and generic units are unsupported input types (`TypeError`). NaT
has no scalar date or duration value and is also rejected by this adapter.

```{doctest} delta-numpy-scalars
>>> from datetime import date, datetime, timedelta
>>> import numpy as np
>>> duration = np.timedelta64(1500, 'ns') + Delta(microseconds=1)
>>> (type(duration) is Delta, duration.microseconds, duration.nanoseconds)
(True, 2, 500)
>>> coarse = np.datetime64('2024-01-01', 'D')
>>> (type(coarse + Delta(days=1)) is date, type(Delta(days=1) + coarse) is datetime)
(True, True)
>>> (coarse + Delta(days=1)).isoformat()
'2024-01-02'
>>> fine = np.datetime64(1500, 'ns') + Delta()
>>> (type(fine) is datetime, fine.isoformat())
(True, '1970-01-01T00:00:00.000002')
>>> (np.datetime64(1, 'ns') - Delta(nanoseconds=1)).isoformat()
'1970-01-01T00:00:00'
>>> for unit in ('ps', 'fs', 'as'):
...     try:
...         Delta() + np.timedelta64(1, unit)
...     except TypeError as error:
...         assert 'unsupported NumPy timedelta64 unit' in str(error)
...         continue
...     raise AssertionError(unit)
>>> for unit in ('Y', 'M', 'W', 'D', 'h', 'm', 's', 'ms', 'us', 'ns'):
...     zero = np.datetime64(0, unit)
...     forward, backward = zero + Delta(days=1), zero - Delta(days=1)
...     expected_type = date if unit in ('Y', 'M', 'W', 'D') else datetime
...     assert type(forward) is expected_type and type(backward) is expected_type
...     assert (forward.year, forward.month, forward.day) == (1970, 1, 2)
...     assert (backward.year, backward.month, backward.day) == (1969, 12, 31)
...     assert type(Delta(days=1) + zero) is datetime
>>> for unit, seconds in (('Y', 31556952), ('M', 2629746)):
...     assert (Delta() + np.timedelta64(1, unit)).to_timedelta() == timedelta(seconds=seconds)
>>> for missing in (np.datetime64('NaT', 'ns'), np.timedelta64('NaT', 'ns')):
...     try:
...         Delta() + missing
...     except ValueError as error:
...         assert 'NaT' in str(error)
...         continue
...     raise AssertionError('NaT accepted')
```

These are scalar operators, not a promise of arbitrary ndarray arithmetic or
NumPy ufunc broadcasting.

`apply_many` preserves the same NumPy scalar roles, including their final
destination rounding.

```{doctest} delta-numpy-batch
>>> from datetime import timedelta
>>> batch = Delta(nanoseconds=500).apply_many([np.timedelta64(1000, 'ns'), np.datetime64(1000, 'ns')])
>>> (type(batch[0]) is Delta, batch[0].microseconds, batch[0].nanoseconds, type(batch[1]) is datetime, batch[1].microsecond)
(True, 1, 500, True, 2)
```

## Import supported dateutil fields

`from_relativedelta()` requires the optional `python-dateutil` dependency. It
reads supported original fields, including fractional fixed amounts, without
calling `normalized()`. The result is a base Delta. Nonempty dateutil weekday
rules and nonzero `leapdays` cannot be represented by this adapter.

```{doctest} delta-dateutil-adapter
>>> from dateutil.relativedelta import relativedelta, MO
>>> converted = Delta.from_relativedelta(relativedelta(months=1, hours=1.5, microseconds=0.001))
>>> (type(converted) is Delta, converted.months, converted.hours, converted.minutes, converted.nanoseconds)
(True, 1, 1, 30, 1)
>>> for unsupported in (relativedelta(weekday=MO(1)), relativedelta(leapdays=1)):
...     try:
...         Delta.from_relativedelta(unsupported)
...     except ValueError:
...         continue
...     raise AssertionError('unrepresentable dateutil rule')
```

The adapter does not promise that every dateutil operation has the same result
after conversion. Use the [dateutil relativedelta reference](https://dateutil.readthedocs.io/en/stable/relativedelta.html)
for its original rules and the [Delta guide](delta.md) for the resulting value.

## Anchors can change the final span

A standard datetime anchor first produces a microsecond datetime. A Timestamp
anchor can represent the exact 500-nanosecond difference and rounds that span
only when converting to standard timedelta. Both results below follow their
destination rules.

```{doctest} delta-anchor-resolution
>>> from datetime import timedelta
>>> tiny = Delta(nanoseconds=500)
>>> plain_start = datetime(1970, 1, 1, microsecond=1)
>>> precise_start = pd.Timestamp(1000, unit='ns')
>>> (tiny.to_timedelta(plain_start), tiny.to_timedelta(precise_start))
(datetime.timedelta(microseconds=1), datetime.timedelta(0))
```
