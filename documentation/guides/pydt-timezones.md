# Attach or convert a timezone on one datetime

Attach a zone to local clock fields. Convert the zone when the value
already represents an instant.

## Interpret a local time and read it in UTC

(pydt-local-clock-to-utc)=
```python
from rstimes import Pydt

wall = Pydt(2024, 1, 1, 8)
local = wall.tz_localize("Asia/Shanghai")
in_utc = local.tz_convert("UTC")
print(in_utc.isoformat())
```

**Output**

```text
2024-01-01T00:00:00+00:00
```

Localization interprets 08:00 in Shanghai. Conversion expresses that
same instant at midnight UTC.

| Operation | When to use it |
| --- | --- |
| `tz_localize(zone)` | Attach a zone to a naive clock. An aware source raises `ValueError`. |
| `tz_localize(None)`, `replace(tzinfo=None)` | Keep the clock and remove its zone. |
| `tz_convert(zone)` | Convert an aware instant. A naive source raises `ValueError`. |
| `tz_convert(None)` | Convert to UTC, then remove the zone. |
| `astimezone(None)` | Convert to the process-local region. |
| `tz_switch(zone, base_tz=..., naive=...)` | For a naive source, give the source zone. Use `naive=True` to return the target clock without its zone. |
| `tz_switch(None)` | Remove the zone and keep the present clock. |

## Choose the first or second occurrence of a repeated clock

(pydt-fall-back-folds)=
```python
from rstimes import Pydt

zone = "America/New_York"
first = Pydt(
    2024, 11, 3, 1, 30, tzinfo=zone, fold=0
)
second = first.replace(fold=1)
print(first.isoformat())
print(second.isoformat())
```

**Output**

```text
2024-11-03T01:30:00-04:00
2024-11-03T01:30:00-05:00
```

`fold=0` chooses the first occurrence and `fold=1` the second. A
nonexistent regional clock, such as 02:30 in New York on March 10, 2024,
raises `ValueError` on strict construction. Use a valid clock or start
from a known instant. Use calendar methods for time-of-day scheduling
and convert both dates to UTC before subtracting if you need the actual
elapsed time across a transition.

## Convert a Pydt through its public timezone method

Use `value.tz_convert(zone)` or `value.astimezone(zone)`. An external
`ZoneInfo.fromutc(value)` call or an explicit `datetime.astimezone`
descriptor can apply Pydt calendar arithmetic inside the conversion.
During the repeated New York hour, the external path can choose the later
instant. For external timezone code, construct a standard datetime
with the same fields, zone, and fold.

Region names use IANA time zones. A supported pytz input is resolved
using its effective region name. The `local` service resolves the
process-local region on first use and reuses the first successful
identity. See the [Pydt reference](../api/reference/rstimes/pydt/index.rst)
for the timezone inspection methods.

## Attach, convert or remove a timezone

(reader-pydt-timezone-choices)=
```python
from rstimes import Pydt

source = Pydt.fromisoformat('2024-01-02 00:00')
tokyo = source.tz_localize('Asia/Tokyo')
utc = tokyo.tz_convert(None)
local_clock = tokyo.tz_localize(None)
aware_utc = tokyo.astimezone('UTC')
switched = source.tz_switch('UTC', base_tz='Asia/Tokyo', naive=True)
print(tokyo.isoformat())
print(utc.isoformat())
print(local_clock.isoformat())
print(aware_utc.isoformat())
print(switched.isoformat())
```

**Output**

```text
2024-01-02T00:00:00+09:00
2024-01-01T15:00:00
2024-01-02T00:00:00
2024-01-01T15:00:00+00:00
2024-01-01T15:00:00
```

Removing a zone with tz_localize keeps the clock. Passing None to tz_convert keeps the instant as a UTC clock.
