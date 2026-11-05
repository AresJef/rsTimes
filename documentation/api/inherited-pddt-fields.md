# Inherited pandas date fields and metadata

Pddt is a real `pandas.DatetimeIndex` subclass. The entries on this page use
pandas' container rules. Numeric calendar fields return ordinary pandas Index
objects; Boolean date predicates return NumPy arrays. They do not become Pddt.
Missing numeric fields are floating NaN, and date predicates are False at NaT.
`nanosecond` is the remainder after microseconds, from 0 through 999.

The table is executable: every named property is read from an actual Pddt,
including its missing row. These aliases are all exercised rather than inferred
from spelling. See the [pandas DatetimeIndex reference](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DatetimeIndex.html)
for the provider's complete reference.

## Calendar fields and aliases

```{doctest} inherited-pddt-calendar-fields
>>> import numpy as np
>>> import pandas as pd
>>> from rstimes import Pddt
>>> value = Pddt(['2024-02-29 12:34:56.123456789', None, '2025-01-01'], unit='ns', tz='UTC', name='event')
>>> expected_fields = {
...     'day': [29.0, np.nan, 1.0], 'month': [2.0, np.nan, 1.0],
...     'quarter': [1.0, np.nan, 1.0], 'hour': [12.0, np.nan, 0.0],
...     'minute': [34.0, np.nan, 0.0], 'second': [56.0, np.nan, 0.0],
...     'microsecond': [123456.0, np.nan, 0.0], 'nanosecond': [789.0, np.nan, 0.0],
...     'weekday': [3.0, np.nan, 2.0], 'dayofweek': [3.0, np.nan, 2.0],
...     'day_of_week': [3.0, np.nan, 2.0], 'dayofyear': [60.0, np.nan, 1.0],
...     'day_of_year': [60.0, np.nan, 1.0], 'days_in_month': [29.0, np.nan, 31.0],
...     'daysinmonth': [29.0, np.nan, 31.0],
... }
>>> for name, expected in expected_fields.items():
...     actual = getattr(value, name)
...     assert type(actual) is pd.Index and actual.dtype == np.dtype('float64')
...     np.testing.assert_equal(actual.to_numpy(), np.array(expected))
>>> expected_flags = {
...     'is_leap_year': [True, False, False],
...     'is_month_start': [False, False, True], 'is_month_end': [True, False, False],
...     'is_quarter_start': [False, False, True], 'is_quarter_end': [False, False, False],
...     'is_year_start': [False, False, True], 'is_year_end': [False, False, False],
... }
>>> for name, expected in expected_flags.items():
...     actual = getattr(value, name)
...     assert type(actual) is np.ndarray and actual.dtype == np.dtype('bool')
...     assert actual.tolist() == expected
>>> names = value.day_name()
>>> (type(names) is pd.Index, [None if pd.isna(x) else x for x in names])
(True, ['Thursday', None, 'Wednesday'])
```

`day_name(locale=None)` uses the provider's default English day names in these
profiles. A nondefault locale depends on installed operating-system locales;
this page makes no promise that arbitrary locale identifiers are available.
For the rsTimes component conversion methods with explicit output choices, see
[the Pddt calendar guide](../guides/pddt-calendar.md).

## Storage, shape and identity metadata

The UTC integer ticks below are exact nanoseconds. `asi8` and `array.asi8` use
the index's actual `unit`, rather than always meaning nanoseconds. NaT is the
pandas int64 minimum sentinel. `values` is a NumPy datetime array in UTC without
timezone metadata; `array` retains the timezone. Use documented export methods
when a copy or an explicit output unit is required.

```{doctest} inherited-pddt-storage-metadata
>>> expected_ticks = [1709210096123456789, -9223372036854775808, 1735689600000000000]
>>> (type(value.array) is pd.arrays.DatetimeArray, value.array.unit, str(value.array.tz))
(True, 'ns', 'UTC')
>>> value.array.asi8.tolist() == value.asi8.tolist() == expected_ticks
True
>>> (type(value.asi8) is np.ndarray, value.asi8.dtype, str(value.dtype), value.unit, str(value.tz))
(True, dtype('int64'), 'datetime64[ns, UTC]', 'ns', 'UTC')
>>> (type(value.values) is np.ndarray, str(value.values.dtype), value.values.view('i8').tolist() == expected_ticks)
(True, 'datetime64[ns]', True)
>>> (value.name, list(value.names), value.shape, value.size, value.ndim, value.nlevels, value.empty)
('event', ['event'], (3,), 3, 1, 1, False)
>>> (value.nbytes, value.resolution, value.inferred_type, value.hasnans, value.has_duplicates, value.is_unique)
(24, 'nanosecond', 'datetime64', True, False, True)
>>> (value.is_monotonic_increasing, value.is_monotonic_decreasing, value.is_normalized)
(False, False, False)
>>> (value.freq, value.freqstr, value.inferred_freq)
(None, None, None)
>>> regular = Pddt.date_range('2024-01-01', periods=3, freq='D', unit='us', tz='UTC')
>>> (regular.freq == pd.offsets.Day(), regular.freqstr, regular.inferred_freq, regular.unit)
(True, 'D', 'D', 'us')
>>> (regular.is_monotonic_increasing, regular.is_monotonic_decreasing, regular.is_normalized)
(True, False, True)
>>> repeated = Pddt(['2024-01-01', '2024-01-01', None])
>>> (repeated.has_duplicates, repeated.is_unique, Pddt([]).empty)
(True, False, True)
```

Metadata such as `freq` describes an actual validated regular grid; construction
without an explicit frequency does not guarantee it is populated. Missing rows
prevent the sample from being monotonic and normalized under pandas' rules.

## One-dimensional views and initialization

`T`, `transpose` and `to_flat_index` preserve the index because it is already
one-dimensional and flat. `ravel`, `infer_objects` and `view` return Pddt in the
verified no-argument calls. These operations are container operations, not the
rsTimes copy protocol: this page does not promise deep ownership isolation.
Pddt construction occurs in `__new__`; the inherited object `__init__` does not
replace data when it is called on an existing object.

```{doctest} inherited-pddt-views
>>> value.T is value
True
>>> value.transpose() is value
True
>>> value.to_flat_index() is value
True
>>> for name in ('ravel', 'infer_objects', 'view'):
...     result = getattr(value, name)()
...     assert type(result) is Pddt and result.unit == 'ns' and str(result.tz) == 'UTC'
...     assert result.asi8.tolist() == expected_ticks and result.name == 'event'
>>> value.__init__() is None
True
>>> value.asi8.tolist() == expected_ticks
True
```
