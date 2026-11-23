# Export Polars dates as numbers, text, or objects

## Get local coordinates or Unix instants

(pldt-export-utc-coordinate)=
```python
from rstimes import Pldt

events = Pldt(["1970-01-01T08:00:00.123456789", None], tz="Asia/Shanghai")
print(events.tomicroseconds().to_list())
print(events.tomicroseconds(utc=True).to_list())
```

**Output**

```text
[28800123456, None]
[123456, None]
```

`tomicroseconds` floors the output to an earlier microsecond and
returns Int64. `toseconds` returns Float64. Both default to local
clock coordinates; `utc=True` uses the UTC instant of an aware
date. `timestamp` returns float Unix seconds and interprets naive
dates in the system-local zone. Use physical ticks, a unit and
validity for exact interchange across the full int64 range.
`values_naive` gives an ordinary native Datetime Series with local
clock fields.

Use `tz_localize` with an explicit ambiguous or nonexistent policy before
`timestamp()` if a naive time is repeated or skipped in the system-local
zone. Without that choice the eager call raises `ValueError`.

Converting to `date` checks the signed 32-bit day range of Polars Date.
`values_naive` checks that the local wall time fits the stored tick unit.
An eager call raises `OverflowError` when either output exceeds its range.

## Format a timestamp with nine fractional digits

(pldt-format-exact-fraction)=
```python
from rstimes import Pldt

events = Pldt([123456789, None], unit="ns")
print(events.strftime("%H:%M:%S%.9f").to_list())
```

**Output**

```text
['00:00:00.123456789', None]
```

ISO formatting uses `timespec` for display width, for example
`"ns"` for nine fractional digits. The default displays a
significant nanosecond tail with nine digits and a whole
microsecond fraction with six. `strftime("%f")` prints the
full fractional digits for the storage resolution, six in ms/us
and nine in ns. The explicit forms `%.0f` through `%.9f` choose
a width. Localized `month_name` and `weekday_name` use the
library's CLDR data.

## Pass Python datetime objects to other code

(pldt-export-python-datetime)=
```python
from rstimes import Pldt

events = Pldt([123456789, None], unit="ns", tz="UTC")
objects = events.datetime()
print([value.microsecond if value is not None else None for value in objects])
```

**Output**

```text
[123456, None]
```

`datetime()` returns a NumPy object array of Pydt and None.
`timetz` provides Python time objects with the same microsecond
precision boundary. Use the native `date` and `time` properties
for Polars Date and Time. Time preserves all nine fraction digits.
The Python datetime year range is 1–9999. The native result
can retain a wider date range at a suitable unit.

(pldt-export-time-table)=
## Export a table of date fields

`timedf()` and `utctimedf()` return DataFrames with nine integer
fields, all null for a missing date. UTC output uses UTC clock fields
for aware dates. Naive clock fields stay the same. See
[Struct output in expressions](expressions-output.md) for the equivalent
usable query results.

## Export a valid minimum tick only after choosing the missing-value policy

(pldt-numpy-explicit-nat-collision)=
```python
import numpy as np
from rstimes import Pldt

events = Pldt([-(2**63), None], unit="ns")
exported = events.to_numpy(allow_nat_collision=True)
print(np.isnat(exported).tolist())
```

**Output**

```text
[True, True]
```

The default `to_numpy()` raises `OverflowError` for this valid
minimum tick. The opt-in above loses the distinction between the
valid tick and null. A NumPy date array has no timezone metadata;
aware values export as UTC ticks. Use
[Arrow-backed exchange](pldt-pandas-arrow.md) to preserve the full
tick and validity.

## Read the ISO calendar at the turn of the year

(pldt-series-isocalendar)=
```python
import polars as pl
import rstimes.pldt

source = pl.Series("event", ["2021-01-01", None]).str.to_datetime(time_unit="us")
dates = source.pldt.isocalendar()
print(dates.to_list())
```

**Output**

```text
[{'year': 2020, 'week': 53, 'day': 5}, None]
```

January 1, 2021 falls in the last ISO week of 2020. The `year` field
uses `Int64` and can be negative. The `week` and `day` fields use
`UInt32`. A missing date gives a null Struct. A date outside the range
supported for its named time zone raises `OverflowError`.

## Read local-clock seconds from dates

(pldt-series-toseconds)=
```python
import polars as pl
import rstimes.pldt
source = pl.Series('event', [0, None], dtype=pl.Datetime('us', 'Asia/Shanghai'))
dates = source.pldt.toseconds()
print(dates.to_list())
```

**Output**

```text
[28800.0, None]
```


## Export integer microseconds from nanosecond dates

(pldt-series-tomicroseconds)=
```python
import polars as pl
import rstimes.pldt
source = pl.Series('event', [-1500, None], dtype=pl.Datetime('ns'))
dates = source.pldt.tomicroseconds()
print(dates.to_list())
```

**Output**

```text
[-2, None]
```


## Read POSIX seconds from timezone-aware dates

(pldt-series-timestamp)=
```python
import polars as pl
import rstimes.pldt
source = pl.Series('event', [0, None], dtype=pl.Datetime('us', 'Asia/Shanghai'))
dates = source.pldt.timestamp()
print(dates.to_list())
```

**Output**

```text
[0.0, None]
```


## Format fractional seconds from stored nanoseconds

(pldt-series-strftime)=
```python
import polars as pl
import rstimes.pldt
source = pl.Series('event', [123_456_789, None], dtype=pl.Datetime('ns'))
dates = source.pldt.strftime('%f|%.3f|%.0f')
print(dates.to_list())
```

**Output**

```text
['123456789|.123|', None]
```


## Read Python date objects from an existing Series

(pldt-series-datetime)=
```python
import polars as pl
import rstimes.pldt
source = pl.Series('event', [1234, None], dtype=pl.Datetime('ns'))
dates = source.pldt.datetime()
print(type(dates[0]).__name__, dates[0].isoformat(), dates[1])
```

**Output**

```text
Pydt 1970-01-01T00:00:00.000001 None
```
