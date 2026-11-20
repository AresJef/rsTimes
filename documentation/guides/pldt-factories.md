# Choose a factory for a Polars date column

A class factory can repeat a scalar with `size`. Omit `size` for a column.
Where a factory accepts multiple components, scalars broadcast to the
common column length. Give every supplied column the same number of rows.

## Interpret epoch seconds or convert an instant

(pldt-attach-or-convert-epoch)=
```python
from rstimes import Pldt

wall = Pldt.fromseconds(0, size=1, tz="Asia/Shanghai")
instant = Pldt.fromtimestamp(0, size=1, tz="Asia/Shanghai")
print(wall.isoformat().to_list())
print(instant.isoformat().to_list())
```

**Output**

```text
['1970-01-01T00:00:00+08:00']
['1970-01-01T08:00:00+08:00']
```

`fromseconds` and `frommicroseconds` decode epoch clock fields before
attaching a requested zone. The microseconds input is an integer.
`fromtimestamp` takes POSIX seconds and converts to the requested zone.
With no zone it returns local clock fields. `utcfromtimestamp` returns
aware UTC. Numeric seconds can supply a nanosecond fraction. `unit`
sets the output representation.

## Decode native calendar coordinates

(pldt-unsigned-calendar-columns)=
```python
import polars as pl
from rstimes import Pldt

years = pl.Series("year", [2024, 2023, None], dtype=pl.UInt16)
days = pl.Series([60, 60, None], dtype=pl.UInt8)
events = years.pldt.fromdayofyear(days)
print(events.isoformat().to_list())
```

**Output**

```text
['2024-02-29T00:00:00', '2023-03-01T00:00:00', None]
```

`fromordinal` uses the proleptic Gregorian calendar. Ordinal 1 represents
0001-01-01, and zero and negative ordinals are valid. `fromisocalendar`
numbers weekdays Monday=1 through Sunday=7. A high week, weekday or
day-of-year selects the final valid position. A value below one raises
for those positions. Native unsigned integer columns, including UInt128,
can supply representable values. An explicit `unit` must be ms, us or ns.

## Combine a date and a native Time column

(pldt-combine-precise-clock)=
```python
from datetime import date

import polars as pl
from rstimes import Pldt

clock = pl.Series("clock", [34_200_000_000_123, None], dtype=pl.Int64).cast(pl.Time)
events = Pldt.combine(date(2024, 1, 2), clock)
print(events.isoformat().to_list())
```

**Output**

```text
['2024-01-02T09:30:00.000000123', None]
```

(pldt-other-date-factory-roles)=
## Use a known source type

| Source | Factory and meaning |
| --- | --- |
| A date | `fromdate` takes its calendar date at midnight and drops the source zone. |
| A datetime | `fromdatetime` keeps a known instant if the target is omitted. An explicit zone reinterprets source clock fields in that zone. |
| A NumPy datetime64 | `fromdatetime64` reads the declared unit and multiplier. |
| ISO text | `fromisoformat` validates ISO input and requires exact output precision. |
| Formatted text | `strptime` uses the supplied format. An explicit coarser unit truncates the fractional part. Configs supplies registered text names. |
| Current time | `now` and `today` read a full local clock by default. `utcnow` is aware UTC. A nonempty call samples once, then repeats the value. |

Zero-size current time results retain dtype. The chosen storage unit
does not describe the precision of the system clock.
