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
