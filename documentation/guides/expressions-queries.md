# Match dates, count boundaries, or read calendar fields

## Compare a month with another column

(expr-match-month-column)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({
    "event": pl.Series([0, 2678400000000000, None], dtype=pl.Datetime("ns")),
    "month": [1, 1, 3],
})
expr = pl.col("event").pldt.is_month(pl.col("month")).alias("match")
print(frame.lazy().select(expr).collect()["match"].to_list())
```

**Output**

```text
[True, False, False]
```

A genuine scalar broadcasts and two columns pair by position.
A missing target for a date predicate is an error. Missing
source dates yield False. Integer calendar queries return nullable
Int64. `weekday` counts Monday as 0, and `isoweekday()`
counts it as 1.

## Count month crossings

(expr-count-month-crossings)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({
    "event": pl.Series([1706745600000000000, None], dtype=pl.Datetime("ns")),
})
expr = pl.col("event").pldt.diff("2024-01-31 23:59:59", "M").alias("months")
print(frame.select(expr)["months"].to_list())
```

**Output**

```text
[1, None]
```

`.pldt.diff` counts calendar or fixed-unit buckets, including
before the epoch. Aware inputs use UTC. Numeric targets are epoch
seconds. Output is Int64 with null propagation and checked
capacity. The native `Expr.diff()` operation calculates a
difference from the previous row.

## Read an ISO calendar Struct

(expr-iso-field-structure)=
```python
import polars as pl
import rstimes.pldt

source = pl.Series("event", ["2021-01-01", None]).str.to_datetime(time_unit="us")
frame = source.to_frame()
expr = pl.col("event").pldt.isocalendar()
print(frame.lazy().select(expr).collect()["event"].to_list())
```

**Output**

```text
[{'year': 2020, 'week': 53, 'day': 5}, None]
```

Use `struct.field("week")` for just the ISO week. The `year` field uses
`Int64` and can be negative. The `week` and `day` fields use `UInt32`.
A missing date gives a null Struct. A date outside the range supported
for its named time zone raises `polars.exceptions.ComputeError` when
`select` or `collect` evaluates that row. The message can report its
position in the input batch.

(expr-clock-reference)=
## Compare with a captured clock

`is_past()` and `is_future()` capture a reference clock at
expression creation. Rebuild the expression to compare with a new
instant. Comparisons are strict and a missing date matches neither.
