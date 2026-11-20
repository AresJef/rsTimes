# Find or count Pydt calendar boundaries

## Get the start of the month

(pydt-start-of-month)=
```python
from rstimes import Pydt

value = Pydt(2024, 2, 15, 12)
print(value.to_start_of("M").isoformat())
```

**Output**

```text
2024-02-01T00:00:00
```

`to_start_of` moves to the first available instant within the period.
`to_end_of` moves to its last available instant. A microsecond is the
smallest step. Use `to_first_of` and `to_last_of` to choose the first or
last day while keeping the original clock where possible. `normalize()`
selects the start of the current local day.

## Choose the closest second

(pydt-nearest-second-midpoint)=
```python
from rstimes import Pydt

value = Pydt(2024, 1, 1, 0, 0, 10, 500000)
print(value.round("s").isoformat())
print(value.snap(unit="s").isoformat())
```

**Output**

```text
2024-01-01T00:00:10
2024-01-01T00:00:11
```

At the midpoint, `round` selects the even frequency tick. `snap`
selects the later of two equally close valid starts. `floor` selects
a frequency tick at or before the value. `ceil` selects one at or after.
Use `freq` for fixed-frequency rounding and `unit` for Snap's named
period. Snap also accepts supported weekday and month names.

## Keep a fixed number of fractional digits in the value

(pydt-truncate-fractional-value)=
```python
from rstimes import Pydt

value = Pydt(2024, 1, 1, microsecond=123456)
print(value.fsp(3).isoformat())
```

**Output**

```text
2024-01-01T00:00:00.123000
```

`fsp` truncates the value's fraction to the requested decimal places.
Zero clears the fractional part. Six or more retain its available
microseconds. A negative precision raises `ValueError`.

## Count the midnight boundaries between two datetimes

(pydt-count-crossed-midnights)=
```python
from rstimes import Pydt

early = Pydt(2024, 1, 31, 23, 59, 59)
late = Pydt(2024, 2, 1)
print(late.diff(early, "D"))
```

**Output**

```text
1
```

The two values are separated by one second and cross one day boundary.
`diff` subtracts the other value's unit bucket from the receiver's.
Aware values use UTC coordinates. Both values must be aware or both
must be naive. `absolute` takes the absolute difference before applying
`inclusive`. The default `"one"` keeps the difference. `"both"` increases
its magnitude and `"neither"` decreases it.

Use the [Pydt reference](../api/reference/rstimes/pydt/index.rst) for
supported frequency and boundary names. A valid nonmatch in a boundary
query returns `False`, while an unknown or empty name raises `ValueError`.
