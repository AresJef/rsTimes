# pandas array wrapping and dispatch metadata on Pddt

Pddt exposes the inherited NumPy/pandas dispatch metadata and wrapping
protocol. Priority values decide dispatch ordering; they are not date ticks,
units or durations. The native wrapping helper returns the container selected
for the supplied result array. It does not promise a Pddt result.

<span id="rstimes.Pddt.__array_wrap__"></span>
<span id="rstimes.Pddt.__array_priority__"></span>
<span id="rstimes.Pddt.__pandas_priority__"></span>

```{doctest} pddt-native-array-dispatch-protocols
>>> import numpy as np
>>> import pandas as pd
>>> from rstimes import Pddt
>>> value = Pddt([123, None], unit='ns', name='event')
>>> (type(value.__array_priority__) is int, value.__array_priority__)
(True, 1000)
>>> (type(value.__pandas_priority__) is int, value.__pandas_priority__)
(True, 2000)
>>> supplied = np.array([456, 'NaT'], dtype='datetime64[ns]')
>>> wrapped = value.__array_wrap__(supplied)
>>> (type(wrapped) is pd.DatetimeIndex, wrapped.name, str(wrapped.dtype), wrapped.tz is None)
(True, 'event', 'datetime64[ns]', True)
>>> wrapped.asi8.tolist()
[456, -9223372036854775808]
>>> (wrapped.isna().tolist(), value.asi8.tolist())
([False, True], [123, -9223372036854775808])
```

This is an explicit protocol call with the default `context=None` and
`return_scalar=False`. Its result reflects the supplied naive ns array and
retains the receiver's name in this example. It is not a timezone-preserving
conversion of an arbitrary receiver. Use the checked
[Pddt output interfaces](../guides/pddt-output.md) for the conversion you intend.
See [Delta interoperability](../guides/delta-interop.md) for actual array/date
operations rather than interpreting priority metadata as an operation itself.
