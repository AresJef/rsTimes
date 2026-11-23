# Find period boundaries and round Polars dates

## Find the end of a calendar month

(pldt-exact-month-boundary)=
```python
from rstimes import Pldt

events = Pldt(["2024-02-15T12:34:56.123456789", None], name="event")
boundary = events.to_end_of("M")
print(boundary.isoformat().to_list())
print(boundary.is_end_of("M").to_list())
```

**Output**

```text
['2024-02-29T23:59:59.999999999', None]
[True, False]
```

`to_first_of` and `to_last_of` leave the clock on the selected
calendar date. `to_start_of` and `to_end_of` use the first or last
representable time within the period. The corresponding predicates
return Boolean Series and use False for a null date. See the
[API reference](../api/index.md) for each method's period names.

(pldt-calendar-clock-edge)=
## Find the first valid clock of a day

`normalize()` returns the start of the existing local day. It uses
the first valid clock on a day with a midnight transition. If a
required edge cannot fit in the current dtype, a transformation can
raise `OverflowError`. With a finer period than the available
storage grid, an existing value is already on that grid.

## Round to the nearest fixed tick

(pldt-round-ties-even)=
```python
from rstimes import Pldt

events = Pldt([1500, 2500, -1500, None], unit="ns")
rounded = events.pldt.round("us")
print(rounded.to_physical().to_list())
```

**Output**

```text
[2000, 2000, -2000, None]
```

Use `.pldt.round`, `.pldt.floor` and `.pldt.ceil` with positive
fixed frequencies or a timedelta. A midpoint rounds to an even
bucket, and these operations retain the input date unit.

## Choose the nearest natural period start

(pldt-snap-period-start)=
```python
from rstimes import Pldt

events = Pldt(["2024-01-02 12:30", None])
print(events.snap("h").isoformat().to_list())
```

**Output**

```text
['2024-01-02T13:00:00', None]
```

`snap` uses the nearest actual period start and selects the later
instant on a tie. It accepts natural periods and recognized month or
weekday names. Use `fsp(precision)` to truncate just the fractional
second within the existing date unit.

## Find the closest period start

(pldt-series-snap)=
```python
import polars as pl
import rstimes.pldt

source = pl.Series("event", ["2024-01-02 11:59", "2024-01-02 12:00", None])
source = source.str.to_datetime(time_unit="us")
dates = source.pldt.snap("D")
print(dates.isoformat().to_list())
```

**Output**

```text
['2024-01-02T00:00:00', '2024-01-03T00:00:00', None]
```

## Compare a month’s calendar days and exact boundaries

(reader-pldt-month-boundaries)=
```python
from rstimes import Pldt

source = Pldt(['2024-03-15 14:30'], unit='us')
first = source.to_first_of('M')
start = source.to_start_of('M')
last = source.to_last_of('M')
end = source.to_end_of('M')
print(first.strftime('%Y-%m-%d %H:%M:%S.%f').to_list()[0])
print(start.strftime('%Y-%m-%d %H:%M:%S.%f').to_list()[0])
print(last.strftime('%Y-%m-%d %H:%M:%S.%f').to_list()[0])
print(end.strftime('%Y-%m-%d %H:%M:%S.%f').to_list()[0])
print(first.is_first_of('M')[0], first.is_start_of('M')[0])
```

**Output**

```text
2024-03-01 14:30:00.000000
2024-03-01 00:00:00.000000
2024-03-31 14:30:00.000000
2024-03-31 23:59:59.999999
True False
```

First and last choose calendar days. Start and end choose the first and last valid instants.


## Compare a month’s calendar days and exact boundaries on a Series

Start with a native Polars Series to call its registered accessor. The
Pldt example above starts with a concrete date column instead.

(reader-series-month-boundaries)=
```python
import polars as pl
import rstimes.pldt

source = pl.Series('event', ['2024-03-15 14:30']).str.to_datetime(time_unit='us')
first = source.pldt.to_first_of('M')
start = source.pldt.to_start_of('M')
last = source.pldt.to_last_of('M')
end = source.pldt.to_end_of('M')
print(first.strftime('%Y-%m-%d %H:%M:%S.%f').to_list()[0])
print(start.strftime('%Y-%m-%d %H:%M:%S.%f').to_list()[0])
print(last.strftime('%Y-%m-%d %H:%M:%S.%f').to_list()[0])
print(end.strftime('%Y-%m-%d %H:%M:%S.%f').to_list()[0])
first_day = pl.Series(first).pldt
print(first_day.is_first_of('M')[0], first_day.is_start_of('M')[0])
```

**Output**

```text
2024-03-01 14:30:00.000000
2024-03-01 00:00:00.000000
2024-03-31 14:30:00.000000
2024-03-31 23:59:59.999999
True False
```

First and last choose calendar days. Start and end choose the first and last valid instants.


## Round to seconds or keep three decimal places

(reader-pldt-second-grid)=
```python
from rstimes import Pldt

source = Pldt(['2024-02-29 12:00:01.567891'], unit='us')
rounded = source.pldt.round('s')
ceiling = source.pldt.ceil('s')
below = source.pldt.floor('s')
shortened = source.fsp(3)
print(rounded.strftime('%H:%M:%S.%f').to_list()[0])
print(ceiling.strftime('%H:%M:%S.%f').to_list()[0])
print(below.strftime('%H:%M:%S.%f').to_list()[0])
print(shortened.strftime('%H:%M:%S.%f').to_list()[0])
```

**Output**

```text
12:00:02.000000
12:00:02.000000
12:00:01.000000
12:00:01.567000
```

These calls preserve the storage unit. Rounding changes the clock value and fsp discards trailing fractional digits.


## Round to seconds or keep three decimal places on a Series

(reader-series-second-grid)=
```python
import polars as pl
import rstimes.pldt

source = pl.Series('event', ['2024-02-29 12:00:01.567891']).str.to_datetime(time_unit='us')
rounded = source.pldt.round('s')
ceiling = source.pldt.ceil('s')
below = source.pldt.floor('s')
shortened = source.pldt.fsp(3)
print(rounded.strftime('%H:%M:%S.%f').to_list()[0])
print(ceiling.strftime('%H:%M:%S.%f').to_list()[0])
print(below.strftime('%H:%M:%S.%f').to_list()[0])
print(shortened.strftime('%H:%M:%S.%f').to_list()[0])
```

**Output**

```text
12:00:02.000000
12:00:02.000000
12:00:01.000000
12:00:01.567000
```

These calls preserve the storage unit. Rounding changes the clock value and fsp discards trailing fractional digits.
