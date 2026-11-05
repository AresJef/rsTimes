# Units, exact values and missing dates

A date value needs its unit, timezone interpretation and validity as well as
an integer. Changing one of those can change the represented instant or make
an otherwise valid value unrepresentable in a destination.

| Container | Resolution/storage | Missing-value role |
|---|---|---|
| Delta | Exact ns for fixed relative amounts, with calendar months/years kept separately | Unset absolute fields use None; this is not a missing timestamp |
| Pydt / standard datetime | Microsecond destination, year 1 through 9999 | A scalar date is not a nullable date column |
| Pddt | pandas datetime storage, including `s`, `ms`, `us` and `ns` | NaT reserves the minimum signed 64-bit tick |
| Pldt | Polars Datetime `ms`, `us` or `ns` | Null validity is separate; the minimum signed 64-bit tick can be valid |
| `.pldt` Expr | Static result dtype chosen for the query | Null positions are checked in the executed result |

An ns storage dtype limits the representable date range compared with a
coarser unit. rsTimes does not silently change a fixed requested unit or
discard fractions to make explicit date construction fit. An intentional
conversion such as `as_unit` has its own stated behavior; it differs from a
checked exact output conversion.

Delta retains exact ns until a destination is selected. Projecting to
datetime/Pydt/timedelta then performs that destination's microsecond rounding.
Applying the same Delta to an ns Pddt/Pldt can retain an extra ns that the
scalar destination cannot represent. See [Delta destination rounding](../guides/delta.md)
and [cross-container results](../recipes/calendar-across-containers.md).

Pldt's valid minimum and a null must stay distinguishable unless you explicitly
choose a destination that cannot keep them apart. NumPy datetime and pandas
reserve that minimum for NaT. The checked Pldt NumPy exporter rejects the
collision by default; `allow_nat_collision=True` explicitly accepts that one
loss. It does not waive unrelated capacity or precision checks. See
[the exact exchange recipe](../recipes/precise-exchange.md).

A standard Python datetime value has microsecond resolution even when it came
from a date column stored in ns. Use the column's physical ticks or a suitable
Arrow interchange path when every ns matters. A readable scalar display is
not an exact ns serialization.

Detailed, executed rules are in the
[Pddt construction](../guides/pddt.md),
[Pddt output](../guides/pddt-output.md),
[Pldt construction](../guides/pldt.md), and
[Pldt output](../guides/pldt-output.md) guides.
