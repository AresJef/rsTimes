# Select calendar boundaries or fixed grids in a query

## End the month at the existing unit

(expr-find-exact-month-end)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({
    "event": pl.Series([0, None], dtype=pl.Datetime("ms", "UTC")),
})
expr = pl.col("event").pldt.to_end_of("M")
print(frame.lazy().select(expr).collect()["event"].to_physical().to_list())
```

**Output**

```text
[2678399999, None]
```

January 1970 ends one millisecond before February 1. Use
`to_first_of`/`to_last_of` to keep the clock on the chosen
calendar day. `to_start_of`/`to_end_of` select the first
or last representable instant of the period. The matching
predicates return Boolean, using False at null dates.

## Round signed ticks to a fixed grid

(expr-round-signed-ticks)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({
    "event": pl.Series([1500, 2500, -1500, None], dtype=pl.Datetime("ns")),
})
expr = pl.col("event").pldt.round("us")
print(frame.select(expr)["event"].to_physical().to_list())
```

**Output**

```text
[2000, 2000, -2000, None]
```

`round` uses the nearest even bucket on a tie. `ceil`
and `floor` choose the grid point in the requested direction.
`snap` finds the nearest actual start of a natural period and
chooses the later instant on a tie. `fsp` truncates the
fractional second using its precision argument. All these date
results retain the existing unit.

For regional clocks, `normalize()` uses the first existing
clock within the same day. Date boundaries can fail at an
unrepresentable edge. Pick a Datetime input for period selection.
Fixed grids can also promote a native Date.
