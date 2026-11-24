# Resolve timezones in a pandas date index

Each Pddt index has one timezone for the whole index. When text includes
different source offsets or mixes naive and aware values, choose a
target zone. Aware values keep their instant. Naive values take the
target's interpretation of their clock.

## Choose both occurrences of a repeated local time

(pddt-select-dst-occurrences-by-row)=
```python
from rstimes import Pddt

clocks = ["2024-11-03 01:30"] * 2
events = Pddt(
    clocks, tz="America/New_York",
    ambiguous=[True, False], unit="us",
)
for text in events.isoformat():
    print(text)
```

**Output**

```text
2024-11-03T01:30:00-04:00
2024-11-03T01:30:00-05:00
```

In this transition, `True` selects the daylight-saving candidate and
`False` selects the standard-time candidate. These flags use the
pandas candidate convention. When you pass a boolean column, include
one value for every original row. You can also use `"raise"`, `"NaT"`,
or `"infer"`. Inference needs sufficient information in the original
order. The default is to raise on an unresolved repeated clock.

## Move a missing clock to the first valid instant

(pddt-move-missing-clock-forward)=
```python
from rstimes import Pddt

clock = Pddt(["2024-03-10 02:30"], unit="us")
events = clock.tz_localize(
    "America/New_York", nonexistent="shift_forward"
)
print(events.isoformat()[0])
```

**Output**

```text
2024-03-10T03:00:00-04:00
```

`"shift_forward"` chooses the next valid boundary. `"shift_backward"`
chooses the previous valid tick in the index's unit. Pass a timedelta
for a deliberate uniform displacement, such as one hour to get 03:30.
Use `"NaT"` for missing positions caused by this local time problem.
The default is `"raise"`. A bad date string still raises a parsing error.

## Pick the timezone operation

| Task | Method |
| --- | --- |
| Interpret naive local fields | `tz_localize(zone)`. |
| Express the same instant in another zone | `tz_convert(zone)`. |
| Remove the zone and keep the displayed clock | `tz_localize(None)` or `tz_switch(None)`. |
| Remove the zone and show the UTC clock | `tz_convert(None)`. |
| Convert a naive source through a known source zone | `tz_switch(target, base_tz=source)`. |
| Convert to the process-local zone | `astimezone(None)`. |

Register region names written inside a string with `Configs.add_tzone`.
After reading the source region, rsTimes can convert to the target zone.
The explicit `tz` argument and the timezone metadata of native dates
have their own roles. See [parsing settings](configs.md).

## Attach, convert or remove a timezone

(reader-pddt-timezone-choices)=
```python
from rstimes import Pddt

source = Pddt(['2024-01-02 00:00'], unit='us')
tokyo = source.tz_localize('Asia/Tokyo')
utc = tokyo.tz_convert(None)
local_clock = tokyo.tz_localize(None)
aware_utc = tokyo.astimezone('UTC')
switched = source.tz_switch('UTC', base_tz='Asia/Tokyo', naive=True)
print(tokyo.isoformat().tolist()[0])
print(utc.isoformat().tolist()[0])
print(local_clock.isoformat().tolist()[0])
print(aware_utc.isoformat().tolist()[0])
print(switched.isoformat().tolist()[0])
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
