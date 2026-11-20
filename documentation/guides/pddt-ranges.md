# Generate dates on a pandas calendar

`Pddt.date_range` builds a date index from endpoints, a number of periods,
and a frequency. Text endpoints use rsTimes date parsing. Numeric endpoints
are ticks of the selected unit.

## Schedule the next three working days

(pddt-schedule-three-working-days)=
```python
from rstimes import Pddt

days = Pddt.date_range(
    "2024-01-05", periods=3, freq="B",
    unit="us", name="work",
)
for text in days.strftime("%Y-%m-%d"):
    print(text)
```

**Output**

```text
2024-01-05
2024-01-08
2024-01-09
```

January 5 was a Friday. The workday frequency skips Saturday and Sunday.
Use a `CustomBusinessDay` rule for an explicit weekmask or holiday list.

## Preserve a workday's subsecond offset

(pddt-keep-workday-submicro-offset)=
```python
from datetime import date, timedelta

from pandas.tseries.offsets import BusinessDay
from rstimes import Pddt

rule = BusinessDay(offset=timedelta(microseconds=1))
days = Pddt.date_range(date(2024, 1, 1), periods=2, freq=rule)
for text in days.isoformat(timespec="us"):
    print(text)
```

**Output**

```text
2024-01-01T00:00:00.000000
2024-01-02T00:00:00.000001
```

The offset requires microseconds, even though the start is a date.
An explicit `unit="s"` raises `ValueError` for this range. Keep the
inferred unit or choose one fine enough for every result. With a
normalized workday offset, the calendar step and offset determine the
date before the clock is set to midnight. See the
[weekend-to-workday example](../compatibility/migration.md#check-workday-ranges-with-offsets).

## Check a rolled endpoint when periods is zero

(pddt-zero-custom-month-ends)=
```python
from datetime import timedelta

from pandas.tseries.offsets import CustomBusinessMonthEnd
from rstimes import Pddt

rule = CustomBusinessMonthEnd(offset=-timedelta(days=1))
days = Pddt.date_range(
    end="2024-01-31", periods=0,
    freq=rule, unit="us"
)
print(days.strftime("%Y-%m-%d").tolist())
```

**Output**

```text
['2023-12-28']
```

A custom work calendar can roll and infer the same endpoint and return
one date. Check the frequency, endpoint, and `inclusive` behavior when
using zero periods. A zero-period daily range is empty.

## Place four points between exact endpoints

(pddt-even-interval-grid)=
```python
from rstimes import Pddt

grid = Pddt.date_range(
    0, end=5, periods=4, freq=None, unit="ns"
)
print(grid.asi8.tolist())
```

**Output**

```text
[0, 1, 3, 5]
```

The evenly spaced intermediate coordinates are selected at the earlier
whole tick. `inclusive` controls whether specified endpoints are kept.
Choose a frequency with the same direction as the range when generating
a regularly stepped grid.

Use `D` for a calendar day and `24h` for an elapsed 24 hours.
Weeks, month ends and beginnings, and business month boundaries have
their own frequencies. Use `min` for minutes and `ME` for month ends.
Custom pandas offsets with dynamic calendar behavior use pandas's full
delegated rule. See [the date range reference](../api/reference/rstimes/pddt/index.rst)
for accepted frequency and timezone options.
