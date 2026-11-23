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

events = Pldt(["2024-02-29", None], name="event")
weeks = events.isocalendar()
print(weeks.to_list())
```

**Output**

```text
[{'year': 2024, 'week': 9, 'day': 4}, None]
```

The Struct has UInt32 `year`, `week` and `day` fields. Pldt and
Series.pldt raise `OverflowError` when the ISO year falls outside
the unsigned range. Use `isoyear()` to read a signed ISO year.
Calendar queries that use named timezone rules also check the year range
of those rules. A date outside that range raises `OverflowError` in eager
calls even if it fits in the Datetime column.

(pldt-query-now-and-zone)=
## Inspect a timezone and compare with now

`is_utc()` and `is_local()` return whole-column booleans.
`is_dst()` returns a Boolean Series, and `utcoffset_seconds()`
returns an Int64 Series with null for missing or naive dates.
`is_past()` and `is_future()` compare strictly to the current
instant or clock; equality matches neither. See the
[expression guide](expressions-queries.md) for query-time behavior.
