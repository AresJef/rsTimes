# Inherited pandas reductions and exports

These inherited operations use pandas' scalar and container types. Reductions
return pandas Timestamp or Timedelta; export methods can return NumPy arrays,
ordinary Index, PeriodIndex, Series or DataFrame. They do not universally return
Pddt or Pydt. The [upstream DatetimeIndex reference](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DatetimeIndex.html)
provides the complete parameter reference.

## Date reductions and memory reporting

`min`, `max`, `mean`, `std`, `argmin` and `argmax` skip NaT by default. The first
three return Timestamp; `std` returns elapsed Timedelta with sample `ddof=1` by
default. Argument reductions return integer positions, not date values.
Memory reporting is in bytes and can include a populated pandas lookup engine;
it need not equal the raw date buffer's `nbytes` after other operations.

```{doctest} inherited-pddt-reductions
>>> from datetime import datetime
>>> import warnings
>>> import numpy as np
>>> import pandas as pd
>>> from rstimes import Pddt
>>> value = Pddt(['2024-01-01', '2024-01-02', '2024-01-03', None], unit='ns', tz='UTC', name='event')
>>> for method, text in [('min', '2024-01-01T00:00:00+00:00'), ('max', '2024-01-03T00:00:00+00:00'), ('mean', '2024-01-02T00:00:00+00:00')]:
...     result = getattr(value, method)()
...     assert type(result) is pd.Timestamp and result.isoformat() == text
>>> deviation = value.std()
>>> (type(deviation) is pd.Timedelta, deviation == pd.Timedelta(days=1))
(True, True)
>>> (int(value.argmin()), int(value.argmax()))
(0, 2)
>>> (value.min(skipna=False) is pd.NaT, value.max(skipna=False) is pd.NaT, value.mean(skipna=False) is pd.NaT, value.std(skipna=False) is pd.NaT)
(True, True, True, True)
>>> empty = Pddt([], unit='ns', tz='UTC')
>>> (empty.min() is pd.NaT, empty.max() is pd.NaT, empty.mean() is pd.NaT, empty.std() is pd.NaT)
(True, True, True, True)
>>> used = value.memory_usage(deep=True)
>>> (type(used) is int, used >= value.nbytes, value.nbytes)
(True, True, 32)
```

## NumPy, object and Python exits

For an aware index, `to_numpy()` defaults to an object array of aware Timestamp
objects. An explicit NumPy datetime dtype converts instants to UTC and drops
timezone metadata. `astype('int64')` exposes ticks in the receiver's unit,
including the NaT sentinel. `astype('object')` returns ordinary pandas Index.
`to_list` and `tolist` retain Timestamp nanoseconds; `to_pydatetime` returns
standard Python datetime objects limited to microseconds and discards the
submicrosecond tail. The inherited array conversion is distinct from rsTimes'
checked [unit conversions](../guides/pddt-output.md).

```{doctest} inherited-pddt-array-exports
>>> exact = Pddt(['2024-01-01 00:00:00.000000123', None], unit='ns', tz='UTC', name='event')
>>> expected = [1704067200000000123, -9223372036854775808]
>>> objects = exact.to_numpy()
>>> (type(objects) is np.ndarray, objects.dtype, type(objects[0]) is pd.Timestamp, objects[0].nanosecond, objects[1] is pd.NaT)
(True, dtype('O'), True, 123, True)
>>> dates = exact.to_numpy(dtype='datetime64[ns]', copy=True)
>>> (type(dates) is np.ndarray, str(dates.dtype), dates.view('i8').tolist())
(True, 'datetime64[ns]', [1704067200000000123, -9223372036854775808])
>>> integers = exact.astype('int64')
>>> (type(integers) is pd.Index, integers.dtype, integers.tolist(), integers.name)
(True, dtype('int64'), [1704067200000000123, -9223372036854775808], 'event')
>>> object_index = exact.astype('object')
>>> (type(object_index) is pd.Index, object_index.dtype, object_index[0].nanosecond, object_index[1] is pd.NaT)
(True, dtype('O'), 123, True)
>>> for method in ('to_list', 'tolist'):
...     result = getattr(exact, method)()
...     assert type(result) is list and type(result[0]) is pd.Timestamp
...     assert result[0].value == expected[0] and result[1] is pd.NaT
>>> python_dates = exact.to_pydatetime()
>>> (type(python_dates) is np.ndarray, python_dates.dtype, type(python_dates[0]) is datetime, python_dates[0].isoformat(), python_dates[1] is pd.NaT)
(True, dtype('O'), True, '2024-01-01T00:00:00+00:00', True)
>>> exact.asi8.tolist() == expected
True
```

## Tables, periods and Julian dates

`to_series` creates a pandas Series with the original index as labels by default.
`to_frame(index=False)` creates a DataFrame with an ordinary RangeIndex. Both
retain the date column's unit, timezone, ns and NaT. `to_period` produces a
PeriodIndex and explicitly warns that timezone information is dropped; a daily
period is a calendar label, not an instant. Julian dates are floating day
numbers, with noon as the integer boundary.

```{doctest} inherited-pddt-table-and-period-exports
>>> series = exact.to_series()
>>> (type(series) is pd.Series, series.name, str(series.dtype), series.array.asi8.tolist() == expected)
(True, 'event', 'datetime64[ns, UTC]', True)
>>> (isinstance(series.index, pd.DatetimeIndex), series.index.asi8.tolist() == expected)
(True, True)
>>> frame = exact.to_frame(index=False)
>>> (type(frame) is pd.DataFrame, type(frame.index) is pd.RangeIndex, frame.columns.tolist(), str(frame['event'].dtype))
(True, True, ['event'], 'datetime64[ns, UTC]')
>>> frame['event'].array.asi8.tolist() == expected
True
>>> with warnings.catch_warnings(record=True) as captured:
...     warnings.simplefilter('always')
...     periods = exact.to_period('D')
>>> (type(periods) is pd.PeriodIndex, str(periods.dtype), str(periods[0]), periods[1] is pd.NaT)
(True, 'period[D]', '2024-01-01', True)
>>> any(isinstance(w.message, UserWarning) and 'timezone' in str(w.message) for w in captured)
True
>>> midnight = Pddt(['2024-01-01', '2024-01-02', None], unit='us', tz='UTC')
>>> julian = midnight.to_julian_date()
>>> (type(julian) is pd.Index, julian.dtype)
(True, dtype('float64'))
>>> np.testing.assert_equal(julian.to_numpy(), np.array([2460310.5, 2460311.5, np.nan]))
```
