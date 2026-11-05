# Apply a calendar change across scalar, pandas and Polars dates

Use Delta to describe a change, then choose the date container for your data.
The example starts on January 31 at noon. Adding one month reaches February 29
in leap year 2024. Adding 30 calendar days instead reaches March 1. A month is
not a fixed number of days, and a clamped month change need not be reversible.

```{doctest} recipe-calendar-scalar
>>> from datetime import datetime
>>> from rstimes import Delta, Pydt
>>> start = Pydt(2024, 1, 31, 12)
>>> monthly = Delta(months=1)
>>> renewal = start + monthly
>>> (type(renewal) is Pydt, renewal.isoformat())
(True, '2024-02-29T12:00:00')
>>> (start + Delta(days=30)).isoformat()
'2024-03-01T12:00:00'
>>> (renewal - monthly).isoformat()
'2024-01-29T12:00:00'
>>> start.isoformat()
'2024-01-31T12:00:00'
```

For batches, Pddt supplies a pandas DatetimeIndex subclass and Pldt supplies a
Polars Series subclass. Both batches below carry a 123 ns tail and a missing
row. The same Delta retains that tail while each container keeps its own
missing-value representation and unit metadata.

```{doctest} recipe-calendar-batches
>>> import numpy as np
>>> import pandas as pd
>>> import polars as pl
>>> from rstimes import Pddt, Pldt
>>> first, expected = 1706702400000000123, 1709208000000000123
>>> indexed = Pddt([first, None], unit='ns', name='event')
>>> column = Pldt([first, None], unit='ns', name='event')
>>> index_result, column_result = indexed + monthly, column + monthly
>>> (type(index_result) is Pddt, index_result.name, index_result.unit)
(True, 'event', 'ns')
>>> type(index_result.asi8[0]) is np.int64
True
>>> (int(index_result.asi8[0]) == expected, pd.isna(index_result[1]))
(True, True)
>>> (type(column_result) is Pldt, column_result.name, column_result.dtype)
(True, 'event', Datetime(time_unit='ns', time_zone=None))
>>> column_result.to_physical().to_list() == [expected, None]
True
>>> (int(indexed.asi8[0]) == first, column.to_physical().to_list() == [first, None])
(True, True)
```

A standard datetime/Pydt destination has microsecond resolution. Delta keeps
exact ns internally, then applies the destination's final rounding rule.
Adding one ns to this scalar leaves it unchanged; adding one ns to either
ns batch changes its stored tick. Do not infer a common output resolution
from the common Delta input.

```{doctest} recipe-calendar-destination-resolution
>>> fine = Delta(nanoseconds=1)
>>> (type(start + fine) is Pydt, start + fine == start)
(True, True)
>>> int((indexed + fine).asi8[0]) == first + 1
True
>>> (column + fine).to_physical().to_list() == [first + 1, None]
True
```

This recipe deliberately uses naive local fields. For aware dates, read the
container's [scalar](../guides/pydt-timezones.md),
[pandas](../guides/pddt-timezones.md), or
[Polars](../guides/pldt-timezones.md) timezone guide before choosing repeated-
or missing-time behavior. For complete relative and absolute fields, see
[Delta](../guides/delta.md).
