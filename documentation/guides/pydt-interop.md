# Use Pydt with NumPy, pandas, and dateutil

## Convert a NumPy datetime before the epoch

(pydt-read-negative-numpy-tick)=
```python
import numpy as np
from rstimes import Pydt

tick = np.datetime64(-1, "ns")
value = Pydt.fromdatetime64(tick)
print(value.isoformat())
```

**Output**

```text
1969-12-31T23:59:59.999999
```

The original value is one nanosecond before the epoch. The destination
uses the earlier whole microsecond. The conversion reads the declared
NumPy unit, including a supported unit multiplier. A missing NaT
cannot become a scalar Pydt.

## Subtract a pandas Timestamp with a nanosecond tail

(pydt-subtract-nanosecond-timestamp)=
```python
import pandas as pd
from rstimes import Pydt

start = Pydt(1970, 1, 1)
stamp = pd.Timestamp(1500, unit="ns")
difference = start - stamp
print(difference)
```

**Output**

```text
-1 day, 23:59:59.999998
```

The exact difference is −1.5 microseconds. Here the standard timedelta
holds the even −2 microseconds. Pydt comparisons with a Timestamp check
its original nanoseconds. `Pydt.fromdatetime(stamp)` uses the original
clock fields at Pydt's available microsecond precision. With a Timestamp
on the left, pandas can return a nanosecond Timedelta under its own
operator rules.

## Apply a dateutil calendar rule

(pydt-add-dateutil-month)=
```python
from dateutil.relativedelta import relativedelta
from rstimes import Pydt

start = Pydt(2024, 1, 31, 9)
shifted = start + relativedelta(months=1)
print(shifted.isoformat())
```

**Output**

```text
2024-02-29T09:00:00
```

Install the dateutil extra for this input. The supported rule fields
come from the original object. See [Delta and dateutil](delta-interop.md)
for the accepted conversion roles and rejected weekday and leapdays
settings. Standard datetime subtraction keeps Python's same-zone
clock behavior. Use [timezone conversion](pydt-timezones.md) first to
compute elapsed time in UTC across a transition.
