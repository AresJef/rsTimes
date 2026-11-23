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
Relative components combine before the final precision check.

## Convert a column's unit inside a query

(pldt-expr-as-unit)=
```python
import polars as pl
import rstimes.pldt

source = pl.Series("event", [-1500, None], dtype=pl.Datetime("ns", "UTC"))
frame = pl.DataFrame([source])
converted = pl.col("event").pldt.as_unit("us")
print(frame.select(converted)["event"].to_physical().to_list())
print(frame.lazy().select(converted).collect()["event"].to_physical().to_list())
```

**Output**

```text
[-2, None]
[-2, None]
```

Choose `"ms"`, `"us"` or `"ns"` as the target unit. The default
rounding picks the earlier tick. Set `round_ok=False` to require an
exact conversion. Select or collect the expression to get the new column.

## Move to the next month or set calendar fields

`to_next_month()` fits January 31 to February 29 and keeps the 14:30 input clock.
`to_datetime(month=2, day=31, hour=9)` also fits to February 29 and sets the hour to 9.
The minute stays at 30, so the second result is 09:30.

(reader-expr-month-and-fields)=
```python
import polars as pl
import rstimes.pldt

source = pl.Series('event', ['2024-01-31 14:30']).str.to_datetime(time_unit='us')
frame = pl.DataFrame([source])
moved = pl.col('event').pldt.to_next_month()
edited = pl.col('event').pldt.to_datetime(month=2, day=31, hour=9)
print(frame.select(moved.pldt.strftime('%Y-%m-%d %H:%M'))['event'].to_list()[0])
print(frame.select(edited.pldt.strftime('%Y-%m-%d %H:%M'))['event'].to_list()[0])
```

**Output**

```text
2024-02-29 14:30
2024-02-29 09:30
```


## Subtract a calendar month through Delta

Subtracting a one-month Delta from January 31 lands on December 31 of the
previous year. December has a 31st, and the clock stays at 14:30.

(reader-expr-subtract-delta)=
```python
import polars as pl
import rstimes.pldt
from rstimes import Delta

source = pl.Series('event', ['2024-01-31 14:30']).str.to_datetime(time_unit='us')
frame = pl.DataFrame([source])
delta = Delta(months=1)
moved = pl.col('event').pldt.sub_delta(delta)
print(frame.select(moved.pldt.strftime('%Y-%m-%d %H:%M'))['event'].to_list()[0])
```

**Output**

```text
2023-12-31 14:30
```
