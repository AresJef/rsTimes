# Move or edit a Pydt calendar date

Use a calendar selector to move to another period. Use `replace` when
your new fields must form an exact valid date.

## Move January 31 into February

(pydt-select-day-in-short-month)=
```python
from rstimes import Pydt

start = Pydt(2024, 1, 31, 16, 30)
result = start.to_datetime(month=2, day=31)
print(result.isoformat())
```

**Output**

```text
2024-02-29T16:30:00
```

A day such as 31 is valid as a selection. `to_datetime` fits it to the
last day of the target month and keeps unmodified fields. `to_date`
selects date fields, and `to_time` selects clock fields. Pass `None`
to keep a field. Zero sets a clock field to zero.

`replace(month=2)` on this January 31 would raise `ValueError`. For
strict replacement, supply a valid day such as `replace(month=2, day=29)`.

## Select a date in a nearby period

| Method family | How to use it |
| --- | --- |
| `to_year`, `to_quarter`, `to_month` | Pass a signed offset. Use the allowed month and day selectors to choose a position within the target. |
| `to_weekday`, `to_day` | Move by calendar weeks or days. Weekday numbers start at Monday as 0. |
| `to_curr_*`, `to_prev_*`, `to_next_*` | Choose the current, previous, or next period. |
| `to_monday` through `to_sunday` | Select a weekday in the current week. |
| `to_yesterday`, `to_tomorrow` | Move one calendar day. |

Use an integer month with `to_date` and `to_datetime`. Date selectors
that accept month names list that support in the
[Pydt reference](../api/reference/rstimes/pydt/index.rst).
A quarter's month selector is a position from 1 to 3.
The weekday name and month name selectors use the library's saved names.

## Add whole calendar days

(pydt-add-two-calendar-days)=
```python
from rstimes import Pydt

due = Pydt(2024, 2, 28, 9)
moved = due.add(days=2)
print(moved.isoformat())
```

**Output**

```text
2024-03-01T09:00:00
```

Named `add` and `sub` use integer amounts. They combine the relative
months before selecting one target month, then apply the day and clock
amounts. Zero leaves the relative amount unchanged. Negative amounts
move in the reverse direction. Use [Delta](delta.md) for supported
fractional changes.

## Read the position of a date in its year

(pydt-read-day-of-year)=
```python
from rstimes import Pydt

value = Pydt(2024, 2, 29)
print(value.day_of_year)
```

**Output**

```text
60
```

`day_of_year`, `days_in_month`, and `is_leap_year` are properties.
Use `weekday()` for the standard datetime method. Calendar queries
such as `is_month` return a bool for a valid target. An unknown name
raises `ValueError`. See [calendar boundaries](pydt-boundaries.md)
for rounding or comparing dates.

## Move to the next month or set calendar fields

(reader-pydt-month-and-fields)=
```python
from rstimes import Pydt

source = Pydt.parse('2024-01-31 14:30')
moved = source.to_next_month()
edited = source.to_datetime(month=2, day=31, hour=9)
print(moved.strftime('%Y-%m-%d %H:%M'))
print(edited.strftime('%Y-%m-%d %H:%M'))
```

**Output**

```text
2024-02-29 14:30
2024-02-29 09:30
```
