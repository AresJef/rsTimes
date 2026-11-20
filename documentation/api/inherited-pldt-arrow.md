# Native Arrow interchange for an rsTimes date column

## Export a full-range Arrow timestamp array

(ref-pldt-native-arrow-array)=
```python
import pyarrow as pa
from rstimes import Pldt

events = Pldt([-(2**63), None], unit="ns", tz="UTC", name="event")
array = events.to_arrow()
print(array.cast(pa.int64()).to_pylist())
```

**Output**

```text
[-9223372036854775808, None]
```

The inherited `to_arrow` helper returns a PyArrow array. The Arrow stream
protocol exposes a PyCapsule to a compatible consumer; `pyarrow.chunked_array`
can consume the Pldt directly. These native interfaces preserve the source
date dtype and null validity in the examples below. They do not apply NumPy's
NaT-sentinel convention to an otherwise valid minimum signed integer.

These examples require the optional PyArrow package. The stream is an
interchange protocol, not a persistent serialization format or a Pldt copy.

The name belongs to the source Series or an enclosing table; the Arrow array
itself carries a dtype and values rather than a Series name. For a named native
table, use [DataFrame export](inherited-pldt-representations.md). For checked
NumPy output, unit conversion and standard Python precision, use the
[rsTimes output guide](../guides/pldt-output.md).
