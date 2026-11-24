# Build a pandas date index with Pddt

Install the pandas extra and pass a one-dimensional collection to
`Pddt`. The result is a pandas DatetimeIndex subclass.

## Build a named index from text

(pddt-create-named-index)=
```python
from rstimes import Pddt

events = Pddt(
    ["2024-02-28", "2024-02-29"],
    unit="us", name="event",
)
print(events.strftime("%Y-%m-%d").tolist())
```

**Output**

```text
['2024-02-28', '2024-02-29']
```

Use the index in a DataFrame or as a date sequence. A single item is a
pandas Timestamp. Date transformations preserve the index's unit, zone,
name, and missing positions. A frequency is retained when it still
describes the result.

## Choose the unit for your source

The supported storage units are `s`, `ms`, `us`, and `ns`. A bare
number is a tick of the chosen unit. For example, `Pddt([1], unit="ms")`
contains a time one millisecond after the epoch.

| Input with no explicit unit | Typical initial unit |
| --- | --- |
| Native dates with a supported declared unit | The source's unit. |
| Python dates or date arrays with units coarser than seconds | Seconds. |
| Python datetimes and valid date strings | Python datetimes use microseconds. Date strings with up to six fractional digits use microseconds. Seven through nine digits use nanoseconds, including trailing zeroes. |
| Untyped empty or all-missing collections | Seconds. |
| Bare numeric input, including an empty native numeric array | Nanoseconds. |

Use a unit that preserves the input. Construction checks precision and
capacity. Ordinary date transformations keep the existing unit.

## Convert deliberately to a coarser unit

(pddt-floor-signed-unit-conversion)=
```python
from rstimes import Pddt

events = Pddt([1500, -1500], unit="ns")
microseconds = events.as_unit("us")
print(microseconds.asi8.tolist())
```

**Output**

```text
[1, -2]
```

`as_unit` selects the earlier tick by default, including for negative
values. Set `round_ok=False` for a checked lossless conversion. A
finer unit may have a narrower calendar range.

## Keep a missing date in its original position

(pddt-report-missing-date)=
```python
from rstimes import Pddt

events = Pddt(["2024-02-29", None], unit="us")
print(events.isna().tolist())
```

**Output**

```text
[False, True]
```

`None`, pandas NaT and NA, typed NumPy date NaT, and supported NaN values
represent missing dates. The complete text tokens `""`, `NaT`, `NAT`,
`nat`, `NaN`, `NAN`, and `nan` also represent missing dates. A bad date
string raises a parsing error. Pass one value as `[value]`.

Inputs can include lists, tuples, generators, one-dimensional NumPy arrays,
pandas collections, and supported Polars Series. Select your date column
explicitly from a DataFrame. See [read native date columns](pddt-interop.md)
for shape, metadata, and interchange rules.

Use the shared parser options for text. A `default` supplies missing date
fields only when needed. A recognized missing value stays missing.
[Date parsing](parsing.md) explains order flags and defaults. See
[choose a date factory](pddt-factories.md) when the source has a known type.
