# Create a single date and time with Pydt

A `Pydt` is a Python datetime subclass. It stores microseconds and uses
years 1 through 9999.

## Create a datetime from its fields

(pydt-build-a-wall-clock)=
```python
from rstimes import Pydt

opening = Pydt(2024, 2, 29, 9, 30)
print(opening.isoformat())
```

**Output**

```text
2024-02-29T09:30:00
```

The value has no timezone. Pass `tzinfo` when the fields describe a
particular local time. See [attach or convert a timezone](pydt-timezones.md).

## Choose wall-clock seconds or a Unix instant

(pydt-clock-seconds-versus-unix-seconds)=
```python
from rstimes import Pydt

zone = "Asia/Shanghai"
wall = Pydt.fromseconds(0, zone)
instant = Pydt.fromtimestamp(0, zone)
print(wall.isoformat())
print(instant.isoformat())
```

**Output**

```text
1970-01-01T00:00:00+08:00
1970-01-01T08:00:00+08:00
```

`fromseconds` sets the clock relative to a naive 1970 epoch and attaches
the selected zone. `frommicroseconds` uses that same coordinate and takes
an integer count. `fromtimestamp` takes Unix epoch seconds and expresses
the instant in the selected zone. Without a zone it returns the local
clock without timezone metadata. Use `utcfromtimestamp` for UTC output.

## Combine a date with a clock

(pydt-combine-calendar-and-clock)=
```python
from datetime import date, time

from rstimes import Pydt

meeting = Pydt.combine(
    date(2024, 5, 7), time(9, 30)
)
print(meeting.isoformat())
```

**Output**

```text
2024-05-07T09:30:00
```

The first argument supplies the calendar date. The second supplies the
clock, including its timezone and fold when present. A missing date
uses today. A missing clock uses midnight. An explicit timezone gives
the result that timezone's interpretation of the clock fields.

## Choose a factory for the source value

| Source | Factory |
| --- | --- |
| Python date | `fromdate` reads year, month, and day and starts at midnight. |
| Python datetime | `fromdatetime` retains its clock. An explicit zone reinterprets the clock fields in that zone. |
| NumPy datetime64 | `fromdatetime64` reads its declared unit and takes the earlier microsecond tick. |
| Ordinal day | `fromordinal` uses 1 for 0001-01-01. |
| ISO week date | `fromisocalendar` uses weekday 1 through 7. A week or weekday above the supported range fits the final valid one. |
| Day of year | `fromdayofyear` starts at 1. A value above the year's last day selects the last day. |
| Ordinary date text, ISO text, or a known format | `parse`, `fromisoformat`, or `strptime`. See [parse dates](parsing.md). |

Use `now(tz)` to read the current clock in a chosen zone. With no zone,
`now()` and `today()` return the complete local date and time, with no
timezone attached. `utcnow()` returns an aware UTC value.

Date fields and integer factories accept integers and the integer-index
protocol. Booleans and floats are rejected for those roles. The seconds
factories have their own numeric input rules. The [scalar factory reference](../api/reference/rstimes/pydt/index.rst)
has the complete signatures.
