# Calendar changes, elapsed time, and real protocols

A Delta carries calendar and exact nanosecond changes. A timedelta carries
elapsed time. Pldt preserves the current date unit and rejects a result that
would lose precision or exceed capacity. Actual Python protocol overrides keep
their normal responsibilities; native expressions accept concrete date rules
without running arbitrary Python row callbacks.

## Delta fields and arithmetic directions

Relative months fit once to the final month. Absolute fields retain their
meaning during subtraction: subtracting `Delta(day=1)` selects day 1 instead of
negating the absolute field. A nanosecond tail is separate from the complete
fractional microsecond part.

```{doctest} pldt-delta-field-arithmetic
>>> from datetime import date, datetime, timedelta
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt, Delta
>>> source = Pldt(['2024-01-31T12:34:56.123456789', None], name='event')
>>> changes = [
...     (Delta(months=1), '2024-02-29T12:34:56.123456789'),
...     (Delta(days=1), '2024-02-01T12:34:56.123456789'),
...     (Delta(day=1), '2024-01-01T12:34:56.123456789'),
...     (Delta(hour=0), '2024-01-31T00:34:56.123456789'),
...     (Delta(microseconds=1), '2024-01-31T12:34:56.123457789'),
...     (Delta(microseconds=.001), '2024-01-31T12:34:56.123456790'),
...     (Delta(nanoseconds=1), '2024-01-31T12:34:56.123456790'),
...     (Delta(millisecond=1), '2024-01-31T12:34:56.001000000'),
...     (Delta(microsecond=1), '2024-01-31T12:34:56.000001000'),
...     (Delta(microsecond=0), '2024-01-31T12:34:56.000000000'),
...     (Delta(nanosecond=2), '2024-01-31T12:34:56.123456002'),
...     (Delta(month=2, months=1, day=31), '2024-03-31T12:34:56.123456789'),
...     (Delta(weekday=0), '2024-01-29T12:34:56.123456789'),
... ]
>>> for delta, answer in changes:
...     for result in (source + delta, delta + source, source.pldt.add_delta(delta), pl.Series(source).pldt.add_delta(delta)):
...         assert type(result) is Pldt and result.dtype == source.dtype and result.name == 'event'
...         assert result.isoformat(timespec='ns').to_list() == [answer, None]
>>> (source - Delta(day=1)).day.to_list()
[1, None]
>>> (source - Delta(nanoseconds=1)).nanosecond.to_list()
[788, None]
>>> source.pldt.sub_delta(Delta(nanoseconds=1)).to_physical().to_list() == (source - Delta(nanoseconds=1)).to_physical().to_list()
True
>>> pl.Series(source).pldt.sub_delta(Delta(day=1)).day.to_list()
[1, None]
>>> dates = Pldt(['2024-01-31', '2024-02-29'], unit='ns')
>>> for deltas in ([Delta(months=1), Delta(months=2)], (Delta(months=1), Delta(months=2)), np.array([Delta(months=1), Delta(months=2)], dtype=object), pl.Series('change', [Delta(months=1), Delta(months=2)], dtype=pl.Object), iter([Delta(months=1), Delta(months=2)])):
...     assert (dates + deltas).isoformat().to_list() == ['2024-02-29T00:00:00', '2024-04-29T00:00:00']
>>> minimum = Pldt([-2**63, None], unit='ns')
>>> (minimum + Delta(nanoseconds=1)).to_physical().to_list()
[-9223372036854775807, None]
>>> for action, error in [(lambda: minimum - Delta(nanoseconds=1), OverflowError), (lambda: Pldt([0], unit='us') + Delta(nanoseconds=1), ValueError), (lambda: dates + [Delta()], ValueError), (lambda: dates + [Delta(), None], TypeError), (lambda: source + True, TypeError), (lambda: source + 1, TypeError), (lambda: Delta(months=1) - source, TypeError)]:
...     try:
...         action()
...     except error:
...         continue
...     raise AssertionError('unsupported or lossy date arithmetic was accepted')
```

## Actual duration units and independent nulls

Python timedelta, real NumPy timedelta64 scalars/arrays, and native Duration
columns have elapsed-time roles. NumPy NaT and native nulls stay missing. A
valid minimum native Duration tick is an actual duration, not a missing marker.
Calendar days and elapsed 24-hour durations differ across DST.

```{doctest} pldt-duration-and-date-operands
>>> before = Pldt(['2024-03-09 12:00'], tz='America/New_York')
>>> ((before + Delta(days=1)).hour.to_list(), (before + timedelta(days=1)).hour.to_list(), (timedelta(days=1) + before).hour.to_list())
([12], [13], [13])
>>> zero = Pldt([0, None], unit='ns')
>>> for unit, scale in [('W', 604800000000000), ('D', 86400000000000), ('h', 3600000000000), ('m', 60000000000), ('s', 1000000000), ('ms', 1000000), ('us', 1000), ('ns', 1)]:
...     duration = np.timedelta64(1, unit)
...     for result in (zero + duration, duration + zero, zero + np.array([1, 2], dtype=f'timedelta64[{unit}]')):
...         assert type(result) is Pldt and result.dtype == zero.dtype
...         assert result.to_physical().to_list() == [scale, None]
...     assert (zero - duration).to_physical().to_list() == [-scale, None]
>>> durations = pl.Series('duration', [-2**63, None, 1], dtype=pl.Duration('ns'))
>>> (Pldt([0, 0, None], unit='ns') + durations).to_physical().to_list()
[-9223372036854775808, None, None]
>>> (zero + np.timedelta64('NaT', 'ns')).to_physical().to_list()
[None, None]
>>> dates = Pldt(['2024-01-02', None], unit='ns')
>>> for target in (datetime(2024, 1, 1), date(2024, 1, 1), np.datetime64('2024-01-01', 'D'), pl.Series('day', [date(2024, 1, 1), None], dtype=pl.Date)):
...     elapsed = dates - target
...     assert type(elapsed) is pl.Series and elapsed.dtype == pl.Duration('ns')
...     assert elapsed.to_physical().to_list() == [86400000000000, None]
>>> try:
...     dates - ['2024-01-01', None]
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```

## NumPy temporal ufuncs

Approved `np.add` and `np.subtract` directions preserve real NumPy temporal
operands, including their units. Reflected date subtraction has no additional
support promise; a rejected direction remains an error. Other ufunc behavior
belongs to the underlying Series protocol.

```{doctest} pldt-numpy-temporal-ufuncs
>>> zero = Pldt([0, None], unit='ns')
>>> np.add(zero, np.timedelta64(1, 'ns')).to_physical().to_list()
[1, None]
>>> np.add(np.array([1, 2], dtype='timedelta64[ns]'), zero).to_physical().to_list()
[1, None]
>>> np.subtract(zero, np.timedelta64(1, 'ns')).to_physical().to_list()
[-1, None]
>>> np.subtract(zero, np.datetime64(1, 'ns')).to_physical().to_list()
[-1, None]
>>> try:
...     np.subtract(np.datetime64(1, 'ns'), zero)
... except TypeError as error:
...     print(type(error).__name__)
TypeError
>>> np.negative(zero).equals(np.negative(pl.Series(zero)))
True
```

## Real application overrides

A genuine scalar Delta override participates in Python's actual arithmetic
negotiation and may own a foreign result. A named `add_delta`/`sub_delta`
operation requires date results with the proper length. A row callback receives
an actual one-row native Series with its full precision, rather than a Python
datetime. Null source rows do not run their row callback. The first genuine
callback failure keeps its exception object.

```{doctest} pldt-application-arithmetic-protocols
>>> calls = []
>>> class ForeignResult(Delta):
...     def __radd__(self, other):
...         calls.append(type(other))
...         return 'application result'
>>> delta = ForeignResult(days=1)
>>> zero.__add__(delta) is NotImplemented
True
>>> calls
[]
>>> zero + delta
'application result'
>>> calls == [Pldt]
True
>>> try:
...     zero.pldt.add_delta(delta)
... except TypeError as error:
...     print(type(error).__name__)
TypeError
>>> calls = []
>>> class RowChange(Delta):
...     def __radd__(self, other):
...         calls.append((type(other) is pl.Series, len(other), other.dtype == pl.Datetime('ns')))
...         return other.pldt.add(nanoseconds=2)
>>> (Pldt([0, None], unit='ns') + [RowChange(), RowChange()]).to_physical().to_list()
[2, None]
>>> calls
[(True, 1, True)]
>>> marker = RuntimeError('application date adjustment failed')
>>> class FailedChange(Delta):
...     def __radd__(self, other):
...         raise marker
>>> try:
...     zero + [FailedChange(), Delta()]
... except RuntimeError as caught:
...     print(caught is marker)
True
>>> class ReverseChange(Delta):
...     def __rsub__(self, other):
...         return 'application subtraction'
>>> zero - ReverseChange()
'application subtraction'
```
