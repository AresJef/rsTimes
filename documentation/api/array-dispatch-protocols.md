# pandas array wrapping and dispatch metadata on Pddt

## Wrap an already computed datetime array

(ref-pddt-wrap-datetime-array)=
```python
import numpy as np
from rstimes import Pddt

source = Pddt([123, None], unit="ns", name="event")
converted = source.__array_wrap__(np.array([456, "NaT"], dtype="datetime64[ns]"))
print(type(converted).__name__, converted.name)
print(converted.isna().tolist())
```

**Output**

```text
DatetimeIndex event
[False, True]
```

Pddt exposes the inherited NumPy/pandas dispatch metadata and wrapping
protocol. Priority values decide dispatch ordering; they are not date ticks,
units or durations. The native wrapping helper returns the container selected
for the supplied result array. It does not promise a Pddt result.

<span id="rstimes.Pddt.__array_wrap__"></span>
<span id="rstimes.Pddt.__array_priority__"></span>
<span id="rstimes.Pddt.__pandas_priority__"></span>

This is an explicit protocol call with the default `context=None` and
`return_scalar=False`. Its result reflects the supplied naive ns array and
retains the receiver's name in this example. It is not a timezone-preserving
conversion of an arbitrary receiver. Use the checked
[Pddt output interfaces](../guides/pddt-output.md) for the conversion you intend.
See [Delta interoperability](../guides/delta-interop.md) for actual array/date
operations rather than interpreting priority metadata as an operation itself.
