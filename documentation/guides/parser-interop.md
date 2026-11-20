# Read exact ticks from a native date value

Use `parse_to_epoch` when you need integer ticks. Choose `parse` to
obtain a standard Python datetime from a supported scalar.

## Start a Python date at midnight

(parser-date-to-midnight)=
```python
from datetime import date

from rstimes import parse

value = parse(date(2024, 2, 29))
print(value.isoformat())
```

**Output**

```text
2024-02-29T00:00:00
```

The result is a datetime without a timezone. A standard datetime input
keeps any timezone already attached to it.

## Preserve a pandas Timestamp's nanoseconds

(parser-read-pandas-nanoseconds)=
```python
import pandas as pd
from rstimes import parse_to_epoch

stamp = pd.Timestamp(123, unit="ns", tz="UTC")
ticks = parse_to_epoch(stamp, unit="ns")
print(ticks)
```

**Output**

```text
123
```

The integer preserves the original instant and its nanoseconds.
`parse(stamp)` uses the standard datetime's microsecond fields. A
missing pandas `NaT` raises `ValueError` at the integer output.

## Read one non-null Polars Datetime value

(parser-read-polars-datetime-ticks)=
```python
import polars as pl
from rstimes import parse_to_epoch

dtype = pl.Datetime("ns", "UTC")
column = pl.Series("event", [123], dtype=dtype)
ticks = parse_to_epoch(column, unit="ns")
print(ticks)
```

**Output**

```text
123
```

Pass one element in a real Datetime Series. The adapter reads the Series'
declared unit and zone. The default `ignoretz=False` uses the instant.
With `ignoretz=True`, the local clock is interpreted against the epoch.
A null or a length other than one raises `ValueError`. A Series with
another dtype raises `TypeError`.

`input_unit` applies to numeric input. A native date value keeps its
source unit. Use [Pldt](pldt.md) for a whole column.

## Use a scalar datetime's actual offset

An aware datetime contributes its actual offset, including supported
seconds and microseconds. An exception from a timezone callback
propagates to the caller. See [Unix millisecond helpers](unix-milliseconds.md)
for a narrower interface that takes an aware datetime.

NumPy arrays and timedelta64 values are outside the scalar date
inputs. See [parse dates into datetimes or epoch ticks](parsing.md).
