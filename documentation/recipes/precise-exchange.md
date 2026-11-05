# Exchange exact dates without confusing a valid value with missingness

An ns Polars date column can contain the minimum signed 64-bit integer as a
valid date and also have a separate null row. NumPy's datetime buffer reserves
that integer for NaT, so those two states cannot both survive a plain NumPy
datetime export. The checked rsTimes exporter rejects that collision by
default. Arrow supplies separate validity and can carry both states.

```{doctest} recipe-exact-arrow-exchange
>>> import numpy as np
>>> import polars as pl
>>> import pyarrow as pa
>>> from rstimes import Pldt
>>> ticks = [-9223372036854775808, None, 1704067200000000123]
>>> source = Pldt(pl.Series('event', ticks, dtype=pl.Datetime('ns', 'UTC')))
>>> source.is_null().to_list()
[False, True, False]
>>> try:
...     source.to_numpy()
... except OverflowError as error:
...     print(type(error).__name__, 'NaT reserved tick' in str(error))
OverflowError True
>>> exported = source.to_arrow()
>>> (isinstance(exported, pa.TimestampArray), exported.type == pa.timestamp('ns', 'UTC'), exported.null_count)
(True, True, 1)
>>> exported.cast(pa.int64()).to_pylist() == ticks
True
>>> restored = Pldt(pl.from_arrow(exported), name=source.name)
>>> (type(restored) is Pldt, restored.name, restored.dtype == source.dtype)
(True, 'event', True)
>>> (restored.to_physical().to_list() == ticks, restored.is_null().to_list())
(True, [False, True, False])
```

If a downstream format intentionally treats the valid minimum as missing,
`allow_nat_collision=True` makes that loss explicit. It does not authorize
other overflow or precision loss. The two first rows below become identical
NaT values, so this output cannot reconstruct the source validity.

```{doctest} recipe-explicit-nat-collision
>>> lossy = source.to_numpy(allow_nat_collision=True)
>>> (type(lossy) is np.ndarray, str(lossy.dtype), np.isnat(lossy).tolist())
(True, 'datetime64[ns]', [True, True, False])
>>> int(lossy.view('i8')[2]) == 1704067200000000123
True
>>> source.to_physical().to_list() == ticks
True
```

Use Arrow or keep explicit integer ticks, validity, unit and timezone for an
exact interchange path. See [checked output](../guides/pldt-output.md) for
other precision/capacity checks, [pandas and Arrow inputs](../guides/pldt-pandas-arrow.md)
for source-type rules, and [native Arrow interchange](../api/inherited-pldt-arrow.md)
for the stream protocol.
