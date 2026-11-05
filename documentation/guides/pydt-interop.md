# Scalar interoperability

Pydt's final representation is always a Python datetime with microsecond
precision. Input adapters have distinct jobs: copying a date into Pydt,
comparing a Timestamp, subtracting a Timestamp, and adding a NumPy duration
do not share one blanket rounding rule.

## NumPy dates and durations

`fromdatetime64` floors a date to microseconds, including negative values.
Y and M datetime units select the first day of the corresponding calendar
year/month. Dtype multipliers apply before the precision conversion.

```{doctest} pydt-numpy-date-units
>>> from datetime import datetime, timedelta
>>> import numpy as np
>>> from rstimes import Pydt
>>> date_units = [('Y', '1971-01-01T00:00:00'), ('M', '1970-02-01T00:00:00'), ('W', '1970-01-08T00:00:00'), ('D', '1970-01-02T00:00:00'), ('h', '1970-01-01T01:00:00'), ('m', '1970-01-01T00:01:00'), ('s', '1970-01-01T00:00:01'), ('ms', '1970-01-01T00:00:00.001000'), ('us', '1970-01-01T00:00:00.000001'), ('ns', '1970-01-01T00:00:00')]
>>> for unit, expected in date_units:
...     result = Pydt.fromdatetime64(np.datetime64(1, unit))
...     assert type(result) is Pydt and result.isoformat() == expected
>>> Pydt.fromdatetime64(np.datetime64(-1, 'ns')).tomicroseconds()
-1
>>> Pydt.fromdatetime64(np.datetime64(2, '10D')).isoformat()
'1970-01-21T00:00:00'
>>> Pydt(1970, 1, 2) - np.datetime64(0, 'D')
datetime.timedelta(days=1)
```

A NumPy Y duration is 365.2425 days and M is one twelfth of that duration;
they are elapsed amounts, unlike `Delta(years=1)` or `Delta(months=1)`.
NumPy durations floor to microseconds before being added or subtracted.
Consequently, −1 ns becomes −1 μs, while +1 ns becomes zero. Subtraction
negates that already converted duration. Use Delta to keep exact nanoseconds
until its final destination conversion.

```{doctest} pydt-numpy-duration-units
>>> epoch = Pydt(1970, 1, 1)
>>> units = {'Y': 31556952000000, 'M': 2629746000000, 'W': 604800000000, 'D': 86400000000, 'h': 3600000000, 'm': 60000000, 's': 1000000, 'ms': 1000, 'us': 1, 'ns': 0}
>>> for unit, microseconds in units.items():
...     forward, backward = epoch + np.timedelta64(1, unit), epoch - np.timedelta64(1, unit)
...     assert type(forward) is Pydt and type(backward) is Pydt
...     assert forward.tomicroseconds() == microseconds and backward.tomicroseconds() == -microseconds
>>> for nanoseconds, microseconds in ((1, 0), (999, 0), (1500, 1), (-1, -1), (-999, -1), (-1500, -2)):
...     assert (epoch + np.timedelta64(nanoseconds, 'ns')).tomicroseconds() == microseconds
...     assert (epoch - np.timedelta64(nanoseconds, 'ns')).tomicroseconds() == -microseconds
>>> (epoch + np.timedelta64(2, '10ms')).tomicroseconds()
20000
>>> for call, exception in ((lambda: Pydt.fromdatetime64(np.datetime64('NaT')), ValueError), (lambda: epoch - np.datetime64('NaT'), ValueError), (lambda: epoch + np.timedelta64('NaT'), ValueError), (lambda: Pydt.fromdatetime64(np.datetime64(1, 'ps')), TypeError), (lambda: epoch + np.timedelta64(1, 'ps'), TypeError), (lambda: Pydt.fromdatetime64(np.datetime64('10000-01-01', 'D')), ValueError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid NumPy source accepted')
```

## pandas Timestamp precision

Copying with `fromdatetime` reads a Timestamp's real calendar fields and
truncates its fractional nanosecond tail at the Pydt destination. Comparisons
instead retain that tail. Pydt minus Timestamp returns a standard timedelta
and rounds the complete difference once to the nearest microsecond, with
ties to even. The reflected expression owned by pandas can return its own
nanosecond Timedelta.

```{doctest} pydt-pandas-precision
>>> import pandas as pd
>>> stamp = pd.Timestamp(123, unit='ns')
>>> copied = Pydt.fromdatetime(stamp)
>>> (type(copied) is Pydt, copied.isoformat(), epoch == stamp, epoch < stamp, epoch != stamp)
(True, '1970-01-01T00:00:00', False, True, True)
>>> for name, expected in (('__eq__', False), ('__ne__', True), ('__lt__', True), ('__le__', True), ('__gt__', False), ('__ge__', False)):
...     assert getattr(epoch, name)(stamp) is expected
>>> rounding = [(499, 0), (500, 0), (501, -1), (1499, -1), (1500, -2), (1501, -2), (-499, 0), (-500, 0), (-501, 1), (-1499, 1), (-1500, 2), (-1501, 2)]
>>> for nanoseconds, microseconds in rounding:
...     difference = epoch - pd.Timestamp(nanoseconds, unit='ns')
...     assert type(difference) is timedelta and difference == timedelta(microseconds=microseconds)
>>> reflected = stamp - epoch
>>> (type(reflected) is pd.Timedelta, reflected.value)
(True, 123)
>>> wide = pd.Timestamp('3000-02-03 04:05:06').as_unit('us')
>>> (Pydt.fromdate(wide).isoformat(), Pydt.fromdatetime(wide).isoformat())
('3000-02-03T00:00:00', '3000-02-03T04:05:06')
>>> zoned = pd.Timestamp('1970-01-01 08:00:00.000000123', tz='Asia/Shanghai')
>>> copied_zoned = Pydt.fromdatetime(zoned)
>>> (copied_zoned.isoformat(), copied_zoned.timestamp(), Pydt(1970, 1, 1, tzinfo='UTC') < zoned)
('1970-01-01T08:00:00+08:00', 0.0, True)
>>> for factory in (Pydt.fromdate, Pydt.fromdatetime, Pydt.parse):
...     try:
...         factory(pd.NaT)
...     except ValueError:
...         continue
...     raise AssertionError('NaT became a scalar date')
```

## dateutil calendar operands

A real `relativedelta` keeps its dateutil behavior, including weekday selection
and actual external overrides. A returned datetime is adapted to the Pydt
subtype. This optional integration requires python-dateutil.

```{doctest} pydt-dateutil-operands
>>> from dateutil.relativedelta import relativedelta, MO
>>> source = Pydt(2024, 5, 7, 12)
>>> result = source + relativedelta(weekday=MO(2))
>>> (type(result) is Pydt, result.isoformat())
(True, '2024-05-20T12:00:00')
>>> (relativedelta(months=1) + source).isoformat()
'2024-06-07T12:00:00'
>>> (source - relativedelta(months=1)).isoformat()
'2024-04-07T12:00:00'
>>> calls = []
>>> class BusinessAdjustment(relativedelta):
...     def __radd__(self, other):
...         calls.append(type(other))
...         return 'application result'
>>> source + BusinessAdjustment()
'application result'
>>> calls == [datetime]
True
>>> marker = RuntimeError('application calendar failed')
>>> class FailingAdjustment(relativedelta):
...     def __rsub__(self, other):
...         raise marker
>>> try:
...     source - FailingAdjustment()
... except RuntimeError as caught:
...     print(caught is marker)
True
```
