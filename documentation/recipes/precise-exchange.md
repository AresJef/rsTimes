# Exchange exact dates through Arrow

Choose a destination with independent validity to transfer the full
Polars date range. The Arrow route requires PyArrow.

## Round-trip a valid minimum tick and a null

(exchange-roundtrip-full-date-tick)=
```python
import polars as pl
from rstimes import Pldt

source = Pldt([-(2**63), None, 123], unit="ns", tz="UTC", name="event")
arrow = source.to_arrow()
restored = Pldt(pl.from_arrow(arrow), name=source.name)
print(restored.to_physical().to_list())
print(restored.is_null().to_list())
```

**Output**

```text
[-9223372036854775808, None, 123]
[False, True, False]
```

The Arrow timestamp type carries the ns unit and UTC. The
example supplies the original name when it constructs the column
from a standalone array.

## Choose what to do at a NumPy NaT collision

NumPy reserves the same minimum tick for NaT.
`Pldt.to_numpy()` raises `OverflowError` at a valid
minimum. Use `allow_nat_collision=True` only if your
destination should treat that date as missing. The valid
minimum and the original null then both become NaT.
Use [checked Polars exports](../guides/pldt-output.md)
and [pandas-backed interchange](../guides/pldt-pandas-arrow.md)
for other destinations.
