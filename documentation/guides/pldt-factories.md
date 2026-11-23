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

## Convert an existing Series of seconds

(pldt-series-fromseconds)=
```python
import polars as pl
from rstimes import Pldt

seconds = pl.Series("seconds", [1, None, -1])
dates = seconds.pldt.fromseconds(unit="ms")
print(dates.to_physical().to_list())
```

**Output**

```text
[1000, None, -1000]
```

The result is a `Pldt` named `seconds` with millisecond resolution.
Each input value is in seconds. The null stays in place.

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

(pldt-locate-wide-tick)=
## Locate an out-of-range tick

When a native integer column contains a value outside signed 64-bit
capacity, eager construction gives the first bad row. Row numbering
starts at zero. A Polars expression reports the position within its
input batch.

(pldt-wide-tick-error)=
```python
import polars as pl
from rstimes import Pldt

ticks = pl.Series("event", [0, None, 2**63], dtype=pl.UInt64)
try:
    Pldt(ticks, unit="ns")
except OverflowError as error:
    print(error)
```

**Output**

```text
Pldt(): data[2]: numeric date tick exceeds signed64
```

Check the source row or correct the integer before constructing the
column. A null value keeps its own validity state.

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

## Parse a fractional second using a format

Use the Series accessor when the raw text is already in a Polars column.

(pldt-series-strptime)=
```python
import polars as pl
import rstimes.pldt
source = pl.Series('event', ['1970-01-01 00:00:00.123456789', None])
dates = source.pldt.strptime('%Y-%m-%d %H:%M:%S.%f', unit='ns')
print(dates.to_physical().to_list())
```

**Output**

```text
[123456789, None]
```


## Build dates from integer microseconds

(pldt-series-frommicroseconds)=
```python
import polars as pl
import rstimes.pldt
source = pl.Series('event', [1, None, -1])
dates = source.pldt.frommicroseconds(unit='ns')
print(dates.to_physical().to_list())
```

**Output**

```text
[1000, None, -1000]
```


## Display POSIX seconds in Tokyo

(pldt-series-fromtimestamp)=
```python
import polars as pl
import rstimes.pldt
source = pl.Series('event', [0, None])
dates = source.pldt.fromtimestamp(tz='Asia/Tokyo', unit='us')
print(dates.dt.strftime('%Y-%m-%d %H:%M %z').to_list())
```

**Output**

```text
['1970-01-01 09:00 +0900', None]
```

## Choose clock coordinates or POSIX instants

The three factories below start with the same numeric value. Compare how
each interprets it before choosing a timezone.

(reader-pldt-three-epoch-inputs)=
```python
from rstimes import Pldt

clock = Pldt.fromseconds(0, tz='Asia/Tokyo', size=1, unit='us')
instant = Pldt.fromtimestamp(0, tz='Asia/Tokyo', size=1, unit='us')
microsecond = Pldt.frommicroseconds(1, tz='Asia/Tokyo', size=1, unit='us')
print(clock.isoformat().to_list()[0])
print(instant.isoformat().to_list()[0])
print(microsecond.isoformat().to_list()[0])
```

**Output**

```text
1970-01-01T00:00:00+09:00
1970-01-01T09:00:00+09:00
1970-01-01T00:00:00.000001+09:00
```


## Keep a source zone or attach another

(reader-pldt-datetime-source-zone)=
```python
from datetime import datetime, timezone
from rstimes import Pldt

source = datetime(1970, 1, 1, tzinfo=timezone.utc)
original = Pldt.fromdatetime(source, size=1)
new_zone = Pldt.fromdatetime(source, tz='Asia/Tokyo', size=1)
print(original.isoformat().to_list()[0])
print(new_zone.isoformat().to_list()[0])
```

**Output**

```text
1970-01-01T00:00:00+00:00
1970-01-01T00:00:00+09:00
```

To keep the instant and change the clock display, use tz_convert after creating the date value or column.


## Keep a source zone or attach another on a Series

(reader-series-datetime-source-zone)=
```python
import polars as pl
import rstimes.pldt

source = pl.Series('event', [0], dtype=pl.Datetime('us', 'UTC'))
original = source.pldt.fromdatetime()
new_zone = source.pldt.fromdatetime(tz='Asia/Tokyo')
print(original.isoformat().to_list()[0])
print(new_zone.isoformat().to_list()[0])
```

**Output**

```text
1970-01-01T00:00:00+00:00
1970-01-01T00:00:00+09:00
```

To keep the instant and change the clock display, use tz_convert after creating the date value or column.


## Read a leap date in ISO format

(reader-pldt-iso-text)=
```python
from rstimes import Pldt

dates = Pldt.fromisoformat(['2024-02-29T03:04:05'], unit='us')
print(dates.isoformat().to_list())
```

**Output**

```text
['2024-02-29T03:04:05']
```


## Read a leap date in ISO format from a Series

(reader-series-iso-text)=
```python
import polars as pl
import rstimes.pldt

raw = pl.Series('event', ['2024-02-29T03:04:05', None])
dates = raw.pldt.fromisoformat(unit='us')
print(dates.isoformat().to_list())
```

**Output**

```text
['2024-02-29T03:04:05', None]
```


## Keep the multiplier of NumPy dates

(reader-pldt-numpy-date-input)=
```python
import numpy as np
from rstimes import Pldt

source = np.array([1, 2], dtype='datetime64[3ms]')
dates = Pldt.fromdatetime64(source)
print(dates.to_physical().to_list())
```

**Output**

```text
[3, 6]
```


## Apply a Python clock to a date column on a Series

(reader-series-combine-clock)=
```python
from datetime import date, time
import polars as pl
import rstimes.pldt

source = pl.Series('event', [date(2024, 2, 29), date(2024, 3, 1)])
dates = source.pldt.combine(time(9, 30), unit='us')
print(dates.isoformat().to_list())
```

**Output**

```text
['2024-02-29T09:30:00', '2024-03-01T09:30:00']
```


## Decode nanoseconds with a supplied format

Use the Pldt factory when a Python list supplies the input.

(reader-pldt-formatted-text)=
```python
from rstimes import Pldt

dates = Pldt.strptime(['1970-01-01 00:00:00.123456789'], '%Y-%m-%d %H:%M:%S.%f', unit='ns')
print(dates.to_physical().to_list())
```

**Output**

```text
[123456789]
```
