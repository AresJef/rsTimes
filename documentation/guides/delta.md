# Move a date with Delta

Use a relative amount such as `months=1` to move a date. Use an absolute
setting such as `day=15` to choose a field in the result.

## Set the day of a recurring date

(delta-set-day-next-month)=
```python
from datetime import date

from rstimes import Delta

start = date(2024, 1, 31)
result = start + Delta(months=1, day=15)
print(result)
```

**Output**

```text
2024-02-15
```

With no explicit day, a move into a shorter month uses that month's last
day. See [the month-end example](../getting-started/index.md#add-one-month-to-a-billing-date).
Multiples of whole months can be combined with `years` or `quarters`.

## Keep a submicrosecond change until the result

(delta-round-at-datetime-result)=
```python
from datetime import datetime

from rstimes import Delta

start = datetime(2024, 1, 1, microsecond=1)
result = start + Delta(nanoseconds=500)
print(result.isoformat())
```

**Output**

```text
2024-01-01T00:00:00.000002
```

The complete result lies halfway between two microseconds. A datetime
result uses the even microsecond. A Python date selects the day of the
exact result calculated from midnight. Fixed-unit date columns keep
their unit and require an exactly representable result.

Integer contributions stay exact. Fractional weeks through nanoseconds
use the values of the supplied binary floats. Delta rounds their combined
total to the nearest nanosecond, with ties to even. Projection to a
microsecond datetime or timedelta happens at that result.

## Combine two months in one change

(delta-combined-months-versus-two-moves)=
```python
from datetime import date

from rstimes import Delta

start = date(2024, 1, 31)
month = Delta(months=1)
print(start + (month + month))
print((start + month) + month)
```

**Output**

```text
2024-03-31
2024-03-29
```

The combined move reaches March directly. Two moves pass through
February 29 and carry that day into March. Combining Delta values adds
the relative amounts. When two absolute settings address the same field,
addition takes the right setting and subtraction keeps the left setting
if it is present. Each absolute field is independent.

## Measure a calendar month from a specific date

(delta-span-from-month-start)=
```python
from datetime import date

from rstimes import Delta

span = Delta(months=1).to_timedelta(
    date(2024, 1, 31)
)
print(span)
```

**Output**

```text
29 days, 0:00:00
```

`to_timedelta(start)` measures the difference between the adjusted
date and its start. With no start, the Delta must contain only fixed
relative units and have no absolute settings.

Relative years, quarters, and months use integers. Fixed relative units
can use supported Python and NumPy floats as well. Use `None` to leave an
absolute field unset. Zero is a real clock setting, such as `hour=0`.
Use the [Delta signature and parameter reference](../api/reference/rstimes/delta/index.rst)
for the ranges. See [combine Delta with other time values](delta-interop.md)
for NumPy, datetime columns, and dateutil.
