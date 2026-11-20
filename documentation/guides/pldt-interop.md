# Read native date arrays into Pldt

## Convert a NumPy seconds array

(pldt-read-numpy-seconds)=
```python
import numpy as np
from rstimes import Pldt

source = np.array([1, -1, "NaT"], dtype="datetime64[s]")
events = Pldt(source, name="event")
print(events.to_physical().to_list())
```

**Output**

```text
[1000, -1000, None]
```

Pldt uses milliseconds for a seconds source when no unit is given.
It reads the actual NumPy datetime unit, including a supported
multiplier, and preserves logical order for a one-dimensional slice.
Date months and years use Gregorian calendar boundaries. Values
outside the target capacity raise `OverflowError`. Use a finer
unit for exact nanoseconds and a coarser unit for longer ranges.

## Capture a native column before appending to its source

(pldt-capture-date-column)=
```python
import polars as pl
from rstimes import Pldt

source = pl.Series("event", [1, None], dtype=pl.Datetime("ns", "UTC"))
events = Pldt(source, copy=False)
source.append(pl.Series("event", [2], dtype=source.dtype))
print(events.to_physical().to_list())
```

**Output**

```text
[1, None]
```

The result keeps the source unit, name, zone and validity with an
independent Series handle. `copy=False` allows safe sharing.
Use `copy=True` to isolate date buffers. A native Polars Date
column supplies midnight. A Time column is appropriate for
`Pldt.combine` and a Duration column for date arithmetic.

For optional integration with pandas or Arrow-backed dates, see
[exchange timestamps](pldt-pandas-arrow.md). To intentionally
reduce precision, use `as_unit`.
