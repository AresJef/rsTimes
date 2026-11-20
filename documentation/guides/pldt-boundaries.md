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
