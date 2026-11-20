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
For differences from the preceding row, use the inherited
`event.diff()` Series operation.
