# Build a native date column with Pldt

Install the Polars extra. `Pldt` is a Polars Series subclass with Datetime
storage, one timezone in its dtype and independent null validity. Pass a
one-dimensional collection. Select a DataFrame column explicitly.

## Parse a text column

(pldt-parse-event-series)=
```python
import polars as pl
import rstimes.pldt

text = pl.Series("event", ["29/02/2024", None])
events = text.pldt.parse(dayfirst=True)
print(events.isoformat().to_list())
```

**Output**

```text
['2024-02-29T00:00:00', None]
```

Use `import rstimes.pldt` or `from rstimes import Pldt` to register the
namespace. A Series call returns a computed Pldt. For a date expression,
see [compute an Expr](expressions.md). To supply missing Y/M/D fields in
partial text, give `default` a complete date. A recognized missing token
keeps its position. Unrecognized input raises a parsing error. Set
`strict=True` to reject explicitly out-of-range fields. The default
parser can fit recognized fields to their valid ranges.

## Choose the storage unit

| Input with no explicit unit | Initial storage |
| --- | --- |
| Native Polars Datetime | The declared ms, us or ns unit. |
| Native Date, supported dates coarser than milliseconds, empty or all-missing untyped input | Milliseconds. |
| Ordinary date strings and Python datetimes | Microseconds. Seven to nine fractional text digits declare ns. |
| Bare ticks | Nanoseconds. |

An explicit `unit` is checked for both precision and int64 capacity.
Mixed sources use a common resolution. Untyped missing data and a typed
empty column can infer different units. Use lists, tuples, generators,
one-dimensional arrays or supported Series. Provide a scalar in a
one-element list. Mapping, set, nested rows, unsupported temporal dtypes
and tables require an explicit transformation before construction.

## Read an endpoint tick without losing its validity

(pldt-read-independent-null-mask)=
```python
from rstimes import Pldt

events = Pldt([-(2**63), None], unit="ns", name="event")
print(events.to_physical().to_list())
print(events.is_null().to_list())
```

**Output**

```text
[-9223372036854775808, None]
[False, True]
```

The full int64 range can carry valid values. NumPy and NumPy-backed pandas
reserve the minimum datetime tick for NaT. [Choose an output representation](pldt-output.md)
before exporting an endpoint.

## Convert to a coarser unit

(pldt-floor-unit-conversion)=
```python
from rstimes import Pldt

events = Pldt([1500, -1500, None], unit="ns")
coarse = events.as_unit("us")
print(coarse.to_physical().to_list())
```

**Output**

```text
[1, -2, None]
```

Pass a target unit of `"ms"`, `"us"` or `"ns"`. The default rounding
selects the earlier tick. Set `round_ok=False` to require an exact
conversion. If exact conversion raises `ValueError`, choose a finer
target unit or allow rounding with `round_ok=True`.
Ordinary date operations preserve the current unit.
See [native input and ownership](pldt-interop.md) for source dtypes and
[choose a factory](pldt-factories.md) for specific date roles.
