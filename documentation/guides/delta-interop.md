# Combine Delta with other time values

Delta accepts several duration and calendar operands. The operand and
the operation determine the returned type.

## Preserve nanoseconds from a NumPy duration

(delta-numpy-duration-plus-delta)=
```python
import numpy as np
from rstimes import Delta

duration = np.timedelta64(1500, "ns")
change = duration + Delta(microseconds=1)
print(change.microseconds, change.nanoseconds)
```

**Output**

```text
2 500
```

The ordinary addition reads the NumPy scalar's ticks and keeps the
nanoseconds in a Delta value. NumPy datetime64 units for year, month,
week, and day can return a date on the left-hand side. Finer datetime64
units return a datetime with microsecond projection. NumPy year and
month durations supported on Delta's side use their fixed mean durations.
Use ordinary scalar operators for these combinations. An unsupported
unit, NaT, or explicit NumPy ufunc has its own rejection boundary.

## Keep one nanosecond in a date index

(delta-keep-index-nanosecond)=
```python
from rstimes import Delta, Pddt

events = Pddt([0], unit="ns", name="event")
shifted = events + Delta(nanoseconds=1)
print(shifted.isoformat(timespec="ns").tolist())
```

**Output**

```text
['1970-01-01T00:00:00.000000001']
```

The result keeps the index's name and unit. An existing microsecond index
cannot store this result. Select an appropriate unit before doing the
calculation. The same fixed-unit rule applies to Pldt. Use
[Polars dates](pldt-arithmetic.md) for Series or
[Polars queries](expressions-calendar.md) for Expr. One absolute
microsecond setting clears the source nanosecond tail when the Delta
leaves nanoseconds unset. An explicit nanosecond setting fills that tail.

## Import a dateutil rule

(delta-import-dateutil-hours)=
```python
from dateutil.relativedelta import relativedelta
from rstimes import Delta

rule = relativedelta(hours=1.5)
change = Delta.from_relativedelta(rule)
print(change.to_timedelta())
```

**Output**

```text
1:30:00
```

Install the [dateutil extra](../getting-started/install.md) for this
adapter. It reads the source fields and uses the resulting Delta rules.
A weekday setting or nonzero leapdays raises `ValueError`. User
operators on real external objects retain their normal result or error
when they handle an operation.

## Choose the anchor for a time span

A date anchor gives whole days. A datetime anchor applies the change to
the clock and then subtracts the original datetime. A pandas Timestamp
anchor can keep nanoseconds in that difference until the final standard
timedelta projection. See [subtract date values](pydt-interop.md) for
the scalar datetime and pandas rules.
