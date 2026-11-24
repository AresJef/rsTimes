# Apply a calendar change or an elapsed duration

## Add a day through daylight saving time

(pldt-calendar-day-versus-duration)=
```python
from datetime import timedelta

from rstimes import Delta, Pldt

events = Pldt(["2024-03-09 12:00", None], tz="America/New_York", name="event")
calendar = events + Delta(days=1)
elapsed = events + timedelta(days=1)
print(calendar.isoformat().to_list())
print(elapsed.isoformat().to_list())
```

**Output**

```text
['2024-03-10T12:00:00-04:00', None]
['2024-03-10T13:00:00-04:00', None]
```

Delta day changes use the local calendar. Python timedelta, NumPy
timedelta64 and native Polars Duration advance by elapsed time. A
timedelta64 NaT or native Duration null gives a null date. A native
minimum duration tick can be valid. Timezone, name and date precision
are carried by the result.

## Apply an exact nanosecond adjustment to a native Series

(pldt-series-delta-precision)=
```python
import polars as pl
from rstimes import Delta
import rstimes.pldt

events = pl.Series("event", [123456789, None], dtype=pl.Datetime("ns"))
adjusted = events.pldt.add_delta(Delta(nanoseconds=1))
print(adjusted.to_physical().to_list())
```

**Output**

```text
[123456790, None]
```

An adjustment must fit in the existing unit and int64 range. An
inexact result raises `ValueError`, and overflow raises
`OverflowError`. To increase precision for a change, convert first
with `as_unit`.

(pldt-arithmetic-dispatch)=
## Select an arithmetic entry point

On Pldt, the operators follow Python's normal method dispatch.
`.pldt.add_delta` and `.pldt.sub_delta` give the native Series
explicit Delta entry points. A supported row-wise operand must align
by position. Absolute Delta fields keep their purpose during
subtraction. For example, subtracting `Delta(day=1)` selects day 1.
NumPy temporal operands also support the approved `np.add` and
`np.subtract` directions. Use a supported date or duration dtype
so its unit and missing representation are carried through.
For a date-to-date duration, see [subtract dates](pldt-differences.md).

## Subtract a calendar month through Delta

(reader-series-subtract-delta)=
```python
import polars as pl
import rstimes.pldt
from rstimes import Delta

source = pl.Series('event', ['2024-01-31 14:30']).str.to_datetime(time_unit='us')
delta = Delta(months=1)
moved = source.pldt.sub_delta(delta)
print(moved.strftime('%Y-%m-%d %H:%M').to_list()[0])
```

**Output**

```text
2023-12-31 14:30
```
