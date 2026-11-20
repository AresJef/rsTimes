# Move or change dates inside a query

## Preserve a nanosecond tail when moving to the next month

(expr-fit-date-in-next-month)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({
    "event": pl.Series([1706659200000000123, None], dtype=pl.Datetime("ns", "UTC")),
})
expr = pl.col("event").pldt.to_next_month()
print(frame.lazy().select(expr).collect()["event"].to_physical().to_list())
```

**Output**

```text
[1709164800000000123, None]
```

January 31 moves to February 29 in 2024. Calendar selectors
use the existing dtype and preserve the clock at its precision.
Read the [calendar guide](pldt-calendar.md) for month, quarter,
weekday and date-field meanings.

## Replace a field from a companion column

(expr-replace-field-by-column)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({
    "event": pl.Series([0, 0, None], dtype=pl.Datetime("us")),
    "day": [2, 3, None],
})
expr = pl.col("event").pldt.replace(day=pl.col("day"))
print(frame.select(expr)["event"].to_list())
```

**Output**

```text
[datetime.datetime(1970, 1, 2, 0, 0), datetime.datetime(1970, 1, 3, 0, 0), None]
```

Companion columns pair by position. A scalar broadcasts across the
current logical group. An optional replacement value of None keeps
the existing field. An integer increment for `add` or `sub`
must be present. Use the [execution guide](expressions-execution.md)
for literal columns, aggregate scalars and groups.

## Apply an exact Delta in a query

(expr-apply-concrete-delta)=
```python
import polars as pl
from rstimes import Delta
import rstimes.pldt

frame = pl.DataFrame({
    "event": pl.Series([123456789, None], dtype=pl.Datetime("ns")),
})
expr = pl.col("event").pldt.add_delta(Delta(nanoseconds=1))
print(frame.lazy().select(expr).collect()["event"].to_physical().to_list())
```

**Output**

```text
[123456790, None]
```

`add_delta` and `sub_delta` capture their concrete Delta rules
when the expression is created. Use an exact-size Delta vector when
each logical row needs a different rule. An Object column or a
dynamic Python arithmetic override cannot serve as an Expr Delta.

Date transformations retain the existing storage unit.
To convert, pass a target unit of `"ms"`, `"us"` or `"ns"` to
`.pldt.as_unit`.
`round_ok=False` requires exact representation at the target unit.
Relative components combine before the final precision check.
