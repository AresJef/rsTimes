# Attach, convert, or remove a Polars date timezone

The Datetime dtype stores one zone for the whole column. Use a supported
IANA name, UTC, or a standard fixed offset that can be represented by an
equivalent native zone. For example, Asia/Shanghai and UTC are ordinary
targets. A fractional fixed offset or custom timezone rule can describe
an aware source instant. Choose a supported target for the resulting dtype.

## Interpret wall clocks and convert their instants

(pldt-attach-and-convert-zone)=
```python
import polars as pl
import rstimes.pldt

clock = pl.Series("event", [28_800_000_000, None], dtype=pl.Datetime("us"))
regional = clock.pldt.tz_localize("Asia/Shanghai")
utc = regional.tz_convert("UTC")
print(regional.isoformat().to_list())
print(utc.isoformat().to_list())
```

**Output**

```text
['1970-01-01T08:00:00+08:00', None]
['1970-01-01T00:00:00+00:00', None]
```

| Call | Meaning |
| --- | --- |
| `tz_localize(zone)` | Interpret naive clock fields as local to the supplied zone. |
| `tz_localize(None)` or `tz_switch(None)` | Remove the zone and keep local clock fields. |
| `tz_convert(zone)` | Convert an aware instant to a new zone. `None` returns a UTC clock with no zone. |
| `tz_switch(zone, base_tz=...)` | Supply the source zone for naive data. `naive=True` keeps the converted clock without its zone. |
| `astimezone()` | Use the system-local zone as the target. |

(pldt-zone-metadata)=
## Inspect the zone stored by the column

`tzinfo` is the normalized Python representation of the column's zone.
Read `dtype.time_zone` for the Polars name. Region names in source
text require Configs registration. A target argument takes a supported
zone directly.

## Select an occurrence of a repeated clock

(pldt-choose-repeated-clock)=
```python
from rstimes import Pldt

events = Pldt(
    ["2024-11-03 01:30", None, "2024-11-03 01:30"],
    tz="America/New_York", ambiguous=[True, False, False],
)
print(events.tz_convert("UTC").isoformat().to_list())
```

**Output**

```text
['2024-11-03T05:30:00+00:00', None, '2024-11-03T06:30:00+00:00']
```

The Boolean mask spans every input position, including nulls. For
this New York transition True selects the DST occurrence. Use
`ambiguous="raise"`, `"NaT"` or `"infer"` when that policy
fits. Inference uses the original row order and needs sufficient evidence.

(pldt-handle-missing-clock)=
## Resolve a missing clock

For missing clocks, `nonexistent` supports `"raise"`, `"NaT"`,
`"shift_forward"`, `"shift_backward"` and one timedelta.
Boundary shifts select the nearest real clock at the current unit.
A timedelta moves by the specified amount and must land on a valid
clock. Explicit `"NaT"` handles the corresponding timezone ambiguity
or gap. Invalid date text still raises a parsing error.

## Convert an aware datetime that uses business timezone rules

(pldt-business-zone-as-source)=
```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from rstimes import Pldt

class BusinessZone(ZoneInfo):
    def utcoffset(self, value):
        return timedelta(hours=2)

source = datetime(2024, 1, 1, 12, tzinfo=BusinessZone("UTC"))
events = Pldt([source], tz="UTC")
print(events.isoformat().to_list())
```

**Output**

```text
['2024-01-01T10:00:00+00:00']
```

The aware source supplies its actual two-hour offset. A file-backed or
custom rule that cannot be encoded in a native dtype raises
`ValueError` when supplied as a target. Use a standard named
target. See [troubleshooting](../troubleshooting.md) for more
error cases.
