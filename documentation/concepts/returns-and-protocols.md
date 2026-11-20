# Return types, inheritance and application protocols

Inspect the called entry point to determine the result type.

| Operation | Result |
| --- | --- |
| rsTimes eager date transformation | The specified date class with date metadata and missing positions |
| Field, count or predicate | The specified scalar, array, Index or Series dtype |
| Inherited native method | The provider's return type for that call |
| Date expression | An Expr that produces native columns during execution |
| Application copy or state hook | The legitimate result chosen by the hook |

## Choose the weekday convention you want

(returns-native-and-rstimes-weekday)=
```python
from rstimes import Pldt

dates = Pldt(["1970-01-01", None], unit="us", name="event")
print(dates.pldt.weekday.to_list())
print(dates.dt.weekday().to_list())
```

**Output**

```text
[3, None]
[4, None]
```

The rsTimes weekday convention numbers Monday as 0. The native
Polars `.dt.weekday()` uses Monday=1. For date field
replacement, use `.pddt.replace` or `.pldt.replace`.
For whole-value replacement, use the container's native entry.

An explicit shallow or deep copy preserves core date metadata.
Application hooks can choose their own type and business state.
See [scalar protocols](../guides/pydt-protocols.md),
[pandas copy and state](../guides/pddt-protocols.md), and
[Polars copy and state](../guides/pldt-state.md).
