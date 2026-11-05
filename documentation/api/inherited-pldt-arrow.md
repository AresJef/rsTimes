# Native Arrow interchange for an rsTimes date column

The inherited `to_arrow` helper returns a PyArrow array. The Arrow stream
protocol exposes a PyCapsule to a compatible consumer; `pyarrow.chunked_array`
can consume the Pldt directly. These native interfaces preserve the source
date dtype and null validity in the examples below. They do not apply NumPy's
NaT-sentinel convention to an otherwise valid minimum signed integer.

These examples require the optional PyArrow package. The stream is an
interchange protocol, not a persistent serialization format or a Pldt copy.

```{doctest} inherited-pldt-native-arrow
>>> import polars as pl
>>> import pyarrow as pa
>>> from rstimes import Pldt
>>> ticks = [1704067200000000123, None, 1704240000000000789]
>>> value = Pldt(pl.Series('event', ticks, dtype=pl.Datetime('ns', 'UTC')))
>>> array = value.to_arrow()
>>> (isinstance(array, pa.TimestampArray), array.type == pa.timestamp('ns', 'UTC'), array.null_count)
(True, True, 1)
>>> array.cast(pa.int64()).to_pylist() == ticks
True
>>> array.is_null().to_pylist()
[False, True, False]
>>> capsule = value.__arrow_c_stream__()
>>> type(capsule).__name__
'PyCapsule'
>>> chunks = pa.chunked_array(value)
>>> (isinstance(chunks, pa.ChunkedArray), chunks.type == pa.timestamp('ns', 'UTC'), chunks.null_count)
(True, True, 1)
>>> chunks.cast(pa.int64()).to_pylist() == ticks
True
>>> empty = value.clear().to_arrow()
>>> (isinstance(empty, pa.TimestampArray), empty.type == array.type, len(empty))
(True, True, 0)
>>> edge = Pldt(pl.Series('edge', [-9223372036854775808, None], dtype=value.dtype))
>>> for exported in [edge.to_arrow(), pa.chunked_array(edge)]:
...     assert exported.type == pa.timestamp('ns', 'UTC') and exported.null_count == 1
...     assert exported.cast(pa.int64()).to_pylist() == [-9223372036854775808, None]
>>> value.to_physical().to_list() == ticks
True
```

The name belongs to the source Series or an enclosing table; the Arrow array
itself carries a dtype and values rather than a Series name. For a named native
table, use [DataFrame export](inherited-pldt-representations.md). For checked
NumPy output, unit conversion and standard Python precision, use the
[rsTimes output guide](../guides/pldt-output.md).
