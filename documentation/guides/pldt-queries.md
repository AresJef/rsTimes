# Query calendar fields and match dates

## Select rows by month

(pldt-match-calendar-month)=
```python
import polars as pl
from rstimes import Pldt

events = Pldt(["2024-02-29", "2024-03-01", None], name="event")
matches = pl.Series(events).pldt.is_month("February")
print(matches.to_list())
```

**Output**

```text
[True, False, False]
```

Boolean date queries use False at source nulls. Supply a valid target
even at a null row. Calendar integer queries return nullable Int64
Series. `weekday` numbers Monday=0, while `isoweekday()` starts
at 1. `nanosecond` returns the 0–999 tail within the microsecond.

## Read ISO week fields

(pldt-extract-iso-week-struct)=
```python
from rstimes import Pldt

dates = Pldt(["0000-01-01", None], unit="us", name="event")
weeks = dates.isocalendar()
print(weeks.to_list())
```

**Output**

```text
[{'year': -1, 'week': 52, 'day': 6}, None]
```

January 1 of year 0 belongs to ISO year −1. The `year` field uses `Int64`.
The `week` and `day` fields use `UInt32`. Saturday is day 6.
A missing date gives a null Struct.

A date can fit in the column and still fall outside the supported range
of its named time zone. Pldt and Series.pldt raise `OverflowError` in
that case. `isoyear()` reads just the ISO year and uses the same local date.

(pldt-query-now-and-zone)=
## Inspect a timezone and compare with now

`is_utc()` and `is_local()` return whole-column booleans.
`is_dst()` returns a Boolean Series, and `utcoffset_seconds()`
returns an Int64 Series with null for missing or naive dates.
`is_past()` and `is_future()` compare strictly to the current
instant or clock; equality matches neither. See the
[expression guide](expressions-queries.md) for query-time behavior.
