# Units, exact values and missing dates

A date value has a storage unit, timezone interpretation and validity.
These properties determine what another representation can carry.

| Representation | Date or change resolution | Missing value |
| --- | --- | --- |
| Delta | Exact ns for fixed relative amounts, with calendar fields stored separately | None leaves an absolute field unspecified |
| Pydt and datetime | Microseconds, years 1–9999 | One scalar date |
| Pddt | Seconds, milliseconds, microseconds or nanoseconds | NaT uses the minimum signed 64-bit tick |
| Pldt | Milliseconds, microseconds or nanoseconds | Native null validity is independent of the tick |
| Expr | Declared by the native result schema | The executed result carries validity |

An ns date range is narrower than a range stored at a coarser unit.
Choose an explicit representation for an exact conversion.
`as_unit` can deliberately select the earlier coarser tick;
`round_ok=False` requires an exact result. Ordinary date
transformations keep their unit.

## Keep an exact change until you choose the result type

(units-project-nanos-at-destination)=
```python
from rstimes import Delta, Pydt

change = Delta(nanoseconds=1500)
date = Pydt(1970, 1, 1) + change
print(date.isoformat())
```

**Output**

```text
1970-01-01T00:00:00.000002
```

Pydt uses microseconds and rounds this midpoint to even.
An ns date collection can carry the original 1500 ns change.
See [the calendar recipe](../recipes/calendar-across-containers.md)
for the different date destinations.

For exact transfer of a valid Polars minimum tick and a null,
use [Arrow-backed exchange](../recipes/precise-exchange.md).
Keep the unit, timezone and validity with a physical integer export.
