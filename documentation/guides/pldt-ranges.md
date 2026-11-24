# Generate a Polars date range

`Pldt.date_range` returns the completed column. Supply two of
`start`, `end` and `periods` when you set `freq`. Supplying all three
with no frequency divides the endpoints on the integer tick grid.
Only `start` may be positional. Bare numeric endpoints are ticks, with
ns as the default for numeric input.

## Schedule local daily events through a clock change

(pldt-local-daily-schedule)=
```python
from rstimes import Pldt

schedule = Pldt.date_range(
    "2024-03-09 12:00", periods=3, freq="D", tz="America/New_York",
)
print(schedule.isoformat().to_list())
```

**Output**

```text
['2024-03-09T12:00:00-05:00', '2024-03-10T12:00:00-04:00', '2024-03-11T12:00:00-04:00']
```

Use `24h` for elapsed days. The same start then reaches 13:00 on
March 10. Range `inclusive` accepts `both`, `left`, `right`, and `neither`.
Date `Series.pldt.diff` and `Expr.pldt.diff` use `one`, `both`, or `neither`
to count crossed date boundaries. Polars' `Series.diff` compares adjacent rows.
For generated regional clocks, ambiguous masks use the full sequence
before endpoint filtering. Every supplied endpoint must fit its unit
even if it is excluded or `periods=0`. `normalize=True` clears the
clock before the endpoint precision check.

## Subdivide native ticks

(pldt-subdivide-nanos-range)=
```python
from rstimes import Pldt

points = Pldt.date_range(0, end=5, periods=4, unit="ns", name="tick")
print(points.to_physical().to_list())
```

**Output**

```text
[0, 1, 3, 5]
```

The result carries a name and dtype. Use `pl.lit(points)` to use the
already created Series in an expression.

## Generate a custom work schedule

(pldt-custom-holiday-range)=
```python
import pandas as pd
from rstimes import Pldt

workdays = pd.offsets.CustomBusinessDay(
    weekmask="Mon Wed Fri", holidays=["2024-01-03"],
)
schedule = Pldt.date_range("2024-01-01", periods=3, freq=workdays)
print(schedule.day.to_list())
```

**Output**

```text
[1, 5, 8]
```

(pldt-choose-range-frequency)=
## Choose a frequency that fits your calendar

Ordinary ticks, calendar days, anchored dates such as `W-MON` and
`ME`, and static business rules work with just the Polars extra.
Use `SMS` for semi-month starts with an anchor from day 2 through 27,
or `SME` for semi-month ends with an anchor from day 1 through 27.
`SMS-1` raises `ValueError`, including when `periods=0`.

(pldt-semi-month-range)=
```python
from rstimes import Pldt

schedule = Pldt.date_range("2024-01-01", periods=3, freq="SME-1", unit="us")
print(schedule.isoformat().to_list())
```

**Output**

```text
['2024-01-01T00:00:00', '2024-01-31T00:00:00', '2024-02-01T00:00:00']
```

Custom business offsets, business hours, general DateOffset objects
and 52/53-week fiscal offsets use the optional pandas executor.
Install pandas for those rules. A business-hour rule raises
`ImportError` when pandas is unavailable.
