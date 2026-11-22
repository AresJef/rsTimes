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

## Find the closest period start

(pldt-expr-snap)=
```python
import polars as pl
import rstimes.pldt
frame = pl.DataFrame([pl.Series('event', [43_200_000_000, None], dtype=pl.Datetime('us'))])
expr = pl.col('event').pldt.snap('D')
dates = frame.select(expr)['event']
print(dates.to_physical().to_list())
```

**Output**

```text
[86400000000, None]
```

## Compare a month’s calendar days and exact boundaries

(reader-expr-month-boundaries)=
```python
import polars as pl
import rstimes.pldt

source = pl.Series('event', ['2024-03-15 14:30']).str.to_datetime(time_unit='us')
frame = pl.DataFrame([source])
first = pl.col('event').pldt.to_first_of('M')
start = pl.col('event').pldt.to_start_of('M')
last = pl.col('event').pldt.to_last_of('M')
end = pl.col('event').pldt.to_end_of('M')
print(frame.select(first.pldt.strftime('%Y-%m-%d %H:%M:%S.%f'))['event'].to_list()[0])
print(frame.select(start.pldt.strftime('%Y-%m-%d %H:%M:%S.%f'))['event'].to_list()[0])
print(frame.select(last.pldt.strftime('%Y-%m-%d %H:%M:%S.%f'))['event'].to_list()[0])
print(frame.select(end.pldt.strftime('%Y-%m-%d %H:%M:%S.%f'))['event'].to_list()[0])
checks = frame.lazy().select(first.pldt.is_first_of('M').alias('first'), first.pldt.is_start_of('M').alias('start')).collect()
print(checks['first'][0], checks['start'][0])
```

**Output**

```text
2024-03-01 14:30:00.000000
2024-03-01 00:00:00.000000
2024-03-31 14:30:00.000000
2024-03-31 23:59:59.999999
True False
```

First and last choose calendar days. Start and end choose the first and last valid instants.


## Round to seconds or keep three decimal places

(reader-expr-second-grid)=
```python
import polars as pl
import rstimes.pldt

source = pl.Series('event', ['2024-02-29 12:00:01.567891']).str.to_datetime(time_unit='us')
frame = pl.DataFrame([source])
rounded = pl.col('event').pldt.round('s')
ceiling = pl.col('event').pldt.ceil('s')
below = pl.col('event').pldt.floor('s')
shortened = pl.col('event').pldt.fsp(3)
print(frame.select(rounded.pldt.strftime('%H:%M:%S.%f'))['event'].to_list()[0])
print(frame.select(ceiling.pldt.strftime('%H:%M:%S.%f'))['event'].to_list()[0])
print(frame.select(below.pldt.strftime('%H:%M:%S.%f'))['event'].to_list()[0])
print(frame.select(shortened.pldt.strftime('%H:%M:%S.%f'))['event'].to_list()[0])
```

**Output**

```text
12:00:02.000000
12:00:02.000000
12:00:01.000000
12:00:01.567000
```

These calls preserve the storage unit. Rounding changes the clock value and fsp discards trailing fractional digits.
