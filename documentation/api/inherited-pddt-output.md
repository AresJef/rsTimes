# Inherited pandas reductions and exports

## Build a labeled pandas Series

(ref-pddt-export-index-series)=
```python
from rstimes import Pddt

events = Pddt([5, None], unit="ns", tz="UTC", name="event")
series = events.to_series(index=["first", "second"])
print(series.index.tolist())
print(series.isna().tolist())
```

**Output**

```text
['first', 'second']
[False, True]
```

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

## NumPy, object and Python exits

For an aware index, `to_numpy()` defaults to an object array of aware Timestamp
objects. An explicit NumPy datetime dtype converts instants to UTC and drops
timezone metadata. `astype('int64')` exposes ticks in the receiver's unit,
including the NaT sentinel. `astype('object')` returns ordinary pandas Index.
`to_list` and `tolist` retain Timestamp nanoseconds; `to_pydatetime` returns
standard Python datetime objects limited to microseconds and discards the
submicrosecond tail. The inherited array conversion is distinct from rsTimes'
checked [unit conversions](../guides/pddt-output.md).

## Tables, periods and Julian dates

`to_series` creates a pandas Series with the original index as labels by default.
`to_frame(index=False)` creates a DataFrame with an ordinary RangeIndex. Both
retain the date column's unit, timezone, ns and NaT. `to_period` produces a
PeriodIndex and explicitly warns that timezone information is dropped; a daily
period is a calendar label, not an instant. Julian dates are floating day
numbers, with noon as the integer boundary.
