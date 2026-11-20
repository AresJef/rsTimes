# Inherited pandas protocols and unsupported operations

## Compare dates with a NumPy ufunc

(ref-pddt-numpy-equality)=
```python
import numpy as np
from rstimes import Pddt

events = Pddt(["2024-02-29", None], unit="ns")
match = np.equal(events, events)
print(match.tolist())
```

**Output**

```text
[True, False]
```

Pddt inherits pandas' vector comparisons, NumPy dispatch and Index container
protocols. Availability of a Python method name does not mean every dtype
supports its operation. Numeric multiplication, division, powers, bitwise
operations and unary numeric operators are not date transformations. The
examples below exercise each exposed protocol and assert its native error.
See [pandas Index](https://pandas.pydata.org/pandas-docs/stable/reference/indexing.html)
for the complete provider interface.

## Vector comparisons

Comparisons return NumPy Boolean arrays. A missing date compares False for
ordered/equality comparisons and True for inequality in these profiles.
Use an explicit aware timestamp when comparing an aware index.

## NumPy dispatch and reflected date subtraction

`np.asarray` invokes the inherited array protocol. Supplying a datetime dtype
preserves the requested precision but drops timezone metadata after conversion
to UTC. NumPy comparisons and date arithmetic dispatch through
`__array_ufunc__`. In these verified cases, adding an elapsed day produces Pddt,
while subtracting a date produces an ordinary pandas TimedeltaIndex. Timedelta
integer values use that result's actual `unit`.

Reflected subtraction, `timestamp - value`, has the provider's TimedeltaIndex
result; it does not call the rsTimes `diff` method or return Delta objects.
`+=` rebinds an index variable to a new date result; the original immutable
index and aliases retain their dates.

## Explicitly unsupported numeric and Boolean roles

Each method below is exercised on Pddt. TypeError is the expected native result,
including the reflected protocols with an integer left operand. For Boolean
row selection, use an explicit mask. For date arithmetic, use a documented
calendar or elapsed-time operand; raw numeric operators are not a substitute.
The string accessor is likewise unavailable for a date dtype.

An Index has no scalar truth value, including an empty Index, and is unhashable.
Use `empty`, `len`, `isna`, `isin` or a comparison mask according to the task.
The disabled `__hash__` is a protocol boundary, not a callable hash method.

## Display protocols

Display formatting follows pandas and can vary across dependency releases.
`repr`, `str` and the empty `format` specification return strings identifying
Pddt, the values, the missing row and date metadata. A nonempty numeric format
specification is not supported. Use rsTimes strftime for a date format.
