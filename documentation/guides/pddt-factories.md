# Build a pandas date index from known inputs

Use a named factory when you know the meaning of each input. Each date
factory returns a Pddt. A scalar source requires `size`. For a column
source, omit `size`.

## Keep the unit of a typed NumPy NaT

(pddt-broadcast-typed-nat)=
```python
import numpy as np
from rstimes import Pddt

missing = np.datetime64("NaT", "ns")
events = Pddt.fromdatetime64(missing, size=2)
print(events.unit)
print(events.isna().tolist())
```

**Output**

```text
ns
[True, True]
```

The missing scalar still has a declared unit. Broadcasting keeps its unit
and creates two missing rows. A supported native date array can also
carry its unit into the result.

## Build dates beyond the standard datetime range

(pddt-build-wide-calendar-date)=
```python
from rstimes import Pddt

events = Pddt.fromdayofyear(
    10000, 1, size=1, unit="us"
)
print(events.year.tolist())
```

**Output**

```text
[10000]
```

A Pddt index can store years beyond 9999 when the selected unit has
capacity. Use `fromordinal`, `fromisocalendar`, or `fromdayofyear`
for explicit calendar coordinates. Calendar number fields take integers.
For a day of year above the year's last day, the factory selects the
last day. A value below 1 raises an error.

## Convert offsets in formatted text to one zone

(pddt-parse-format-to-utc)=
```python
from rstimes import Pddt

text = [
    "2024-01-01 12:00+0800",
    "2024-01-01 12:00+0900",
]
events = Pddt.strptime(
    text, "%Y-%m-%d %H:%M%z", tz="UTC"
)
for value in events.isoformat():
    print(value)
```

**Output**

```text
2024-01-01T04:00:00+00:00
2024-01-01T03:00:00+00:00
```

`strptime` reads the whole format, uses `cfg` for configured names,
and can truncate a `%f` fraction at the chosen unit. Ordinary parsing
and ISO construction require a lossless representation. Use
`fromisoformat` for supported ISO clocks, week dates, or ordinal dates.
See [timezones in a pandas date index](pddt-timezones.md) for source
offsets, target zones, and ambiguous clocks.

## Choose the factory that matches the source

| Source | Factory |
| --- | --- |
| Python dates | `fromdate` prepares midnight at the given dates. |
| Python datetimes | `fromdatetime` reads clock fields. An explicit zone reinterprets those fields in that zone. |
| NumPy datetime values | `fromdatetime64` reads the declared unit and multiplier. |
| Unix epoch seconds | `fromtimestamp` or `utcfromtimestamp`. |
| Wall-clock coordinates | `fromseconds` or `frommicroseconds`; the latter takes integer microseconds. |
| Separate dates and clocks | `combine` takes date fields from one source and clock fields from the other. |
| Current time | `now`, `today`, or `utcnow`. Nonempty calls repeat one reading. |

When a factory takes several components, a scalar component broadcasts
to the common column length. Provide equal lengths for column components.
If every component is a scalar, give `size`. A one-element collection is
a column. `size=0` makes an empty index with the selected metadata.

See [the Pddt reference](../api/reference/rstimes/pddt/index.rst) for each
factory's argument roles.

## Choose clock coordinates or POSIX instants

(reader-pddt-three-epoch-inputs)=
```python
from rstimes import Pddt

clock = Pddt.fromseconds(0, tz='Asia/Tokyo', size=1, unit='us')
instant = Pddt.fromtimestamp(0, tz='Asia/Tokyo', size=1, unit='us')
microsecond = Pddt.frommicroseconds(1, tz='Asia/Tokyo', size=1, unit='us')
print(clock.isoformat().tolist()[0])
print(instant.isoformat().tolist()[0])
print(microsecond.isoformat().tolist()[0])
```

**Output**

```text
1970-01-01T00:00:00+09:00
1970-01-01T09:00:00+09:00
1970-01-01T00:00:00.000001+09:00
```


## Keep a source zone or attach another

(reader-pddt-datetime-source-zone)=
```python
from datetime import datetime, timezone
from rstimes import Pddt

source = datetime(1970, 1, 1, tzinfo=timezone.utc)
original = Pddt.fromdatetime(source, size=1)
new_zone = Pddt.fromdatetime(source, tz='Asia/Tokyo', size=1)
print(original.isoformat().tolist()[0])
print(new_zone.isoformat().tolist()[0])
```

**Output**

```text
1970-01-01T00:00:00+00:00
1970-01-01T00:00:00+09:00
```

To keep the instant and change the clock display, use tz_convert after creating the date value or column.


## Read a leap date in ISO format

(reader-pddt-iso-text)=
```python
from rstimes import Pddt

dates = Pddt.fromisoformat(['2024-02-29T03:04:05'], unit='us')
print(dates.isoformat().tolist())
```

**Output**

```text
['2024-02-29T03:04:05']
```


## Keep the multiplier of NumPy dates

(reader-pddt-numpy-date-input)=
```python
import numpy as np
from rstimes import Pddt

source = np.array([1, 2], dtype='datetime64[3ms]')
dates = Pddt.fromdatetime64(source)
print(dates.asi8.tolist())
```

**Output**

```text
[3, 6]
```


## Apply a Python clock to a date column

(reader-pddt-combine-clock)=
```python
from datetime import date, time
from rstimes import Pddt

dates = Pddt.combine([date(2024, 2, 29), date(2024, 3, 1)], time(9, 30), unit='us')
print(dates.isoformat().tolist())
```

**Output**

```text
['2024-02-29T09:30:00', '2024-03-01T09:30:00']
```
