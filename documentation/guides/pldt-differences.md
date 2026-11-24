# Count calendar boundaries or measure elapsed time

## Count month boundaries from a reference

(pldt-count-month-boundary)=
```python
from rstimes import Pldt

event = Pldt(["2024-02-01 00:00:00", None], name="event")
crossings = event.pldt.diff("2024-01-31 23:59:59", "M")
print(crossings.to_list())
```

**Output**

```text
[1, None]
```

`.pldt.diff(target, unit)` returns the difference between unit
buckets, self minus target. The result is an Int64 Series. Calendar
weeks start Monday. Numeric targets are seconds. Aware dates compare
in UTC and naive dates compare in the nominal clock coordinate.
Keep both inputs in the same awareness category. Provide a scalar or
a strictly equal-length target column.

## Compare a native Series with a reference date

(pldt-series-diff)=
```python
import polars as pl
import rstimes.pldt

source = pl.Series("event", ["2024-01-03", None]).str.to_datetime(time_unit="us")
days = source.pldt.diff("2024-01-01", "D")
print(days.to_list())
```

**Output**

```text
[2, None]
```

(pldt-count-endpoint-inclusion)=
## Adjust the signed count

`absolute` applies before `inclusive`. The default `"one"`
preserves the count, `"both"` expands it by one step away from
zero, and `"neither"` removes one step. At zero these choices
return 0, 1 and −1 respectively.

## Subtract the reference to measure elapsed time

(pldt-measure-actual-duration)=
```python
from datetime import datetime

from rstimes import Pldt

event = Pldt(["2024-02-01 00:00:00", None], unit="us")
elapsed = event - datetime(2024, 1, 31, 23, 59, 59)
print(elapsed.to_physical().to_list())
```

**Output**

```text
[1000000, None]
```

This result is a Duration Series with microsecond ticks.

## Measure the time since the preceding row

(pldt-adjacent-duration)=
```python
from rstimes import Pldt

event = Pldt([1001, 2002, None], unit="us", name="event")
elapsed = event.diff()
print(elapsed.to_physical().to_list())
```

**Output**

```text
[None, 1001, None]
```

The inherited `diff()` compares adjacent rows and returns a native
Duration Series in the input unit. The first row has no predecessor.
Subtract a separate date column to compare matching rows instead.
