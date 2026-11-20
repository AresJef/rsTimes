# Add a calendar month across date containers

## Change a scalar date

(calendar-recipe-month-to-leap-day)=
```python
from rstimes import Delta, Pydt

start = Pydt(2024, 1, 31, 12)
renewal = start + Delta(months=1)
print(renewal.isoformat())
```

**Output**

```text
2024-02-29T12:00:00
```

A calendar month uses the destination month's valid final day.
The reverse change begins from February 29, so subtracting a month
from the result reaches January 29.

## Apply the same change to two native date collections

(calendar-recipe-match-column-results)=
```python
from rstimes import Delta, Pddt, Pldt

month = Delta(months=1)
values = ["2024-01-31T12:00:00.000000123", None]
index = Pddt(values, unit="ns", name="event") + month
column = Pldt(values, unit="ns", name="event") + month
print(index.isoformat().dropna().tolist())
print(column.isoformat().to_list())
```

**Output**

```text
['2024-02-29T12:00:00.000000123']
['2024-02-29T12:00:00.000000123', None]
```

Pddt retains its NaT and Pldt retains its native null. The print
for Pddt drops the missing value from display. Both date results
preserve their nanosecond storage and name. Pydt stores
microseconds and applies its own final rounding for finer changes.

See [date arithmetic](../guides/delta-interop.md) for elapsed
duration and [timezone rules](../concepts/time-and-calendars.md)
for aware clocks.
