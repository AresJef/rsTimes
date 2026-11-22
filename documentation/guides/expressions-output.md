# Return native numbers, text, and Structs from expressions

## Select an hour from a time-field Struct

(expr-select-time-field-from-struct)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({
    "event": pl.Series([0, None], dtype=pl.Datetime("us", "Asia/Shanghai")),
})
expr = pl.col("event").pldt.timedf().struct.field("tm_hour").alias("hour")
print(frame.lazy().select(expr).collect()["hour"].to_list())
```

**Output**

```text
[8, None]
```

`timedf()` exposes local clock fields and `utctimedf()` uses UTC
for aware dates. Both expression methods return one Struct. Use
`struct.field` for one field or `unnest` for all nine.
Each missing input stays null. UTC uses zero for `tm_isdst`.
The local field is −1 if unspecified, 0 for zero adjustment,
or 1 for a nonzero DST adjustment.

Local `toseconds` and `tomicroseconds` return Float64 and
Int64. `utc=True` uses an aware date's UTC coordinates.
`timestamp` always represents the instant as Unix seconds.
`date` and `time` use native Polars temporal result dtypes,
and `values_naive` gives native local clock fields without a zone.

## Format a nanosecond date without changing its storage

(expr-format-iso-to-text)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({
    "event": pl.Series([123456789, None], dtype=pl.Datetime("ns")),
})
expr = pl.col("event").pldt.isoformat(timespec="ns").alias("label")
print(frame.select(expr)["label"].to_list())
```

**Output**

```text
['1970-01-01T00:00:00.123456789', None]
```

Set ISO `timespec` to choose text precision.
`strftime("%f")` uses six digits for ms/us and nine for ns.
Explicit `%.1f`–`%.9f` writes a dot and the requested
digits. `%.0f` omits the fraction. Use library locale
names with `month_name` or `weekday_name`.

## Choose a checked array export after collection

A collected column is an ordinary Polars Series. Use
`Pldt(column).to_numpy()` for the rsTimes check against a valid
timestamp colliding with the destination's reserved NaT tick.
For exact transfer of all physical values, retain the native
validity or use a destination with independent validity.
[Choose an eager output](pldt-output.md) for Python objects.

## Read local-clock seconds from dates

(pldt-expr-toseconds)=
```python
import polars as pl
import rstimes.pldt
frame = pl.DataFrame([pl.Series('event', [0, None], dtype=pl.Datetime('us', 'Asia/Shanghai'))])
expr = pl.col('event').pldt.toseconds()
dates = frame.select(expr)['event']
print(dates.to_list())
```

**Output**

```text
[28800.0, None]
```


## Export integer microseconds from nanosecond dates

(pldt-expr-tomicroseconds)=
```python
import polars as pl
import rstimes.pldt
frame = pl.DataFrame([pl.Series('event', [-1500, None], dtype=pl.Datetime('ns'))])
expr = pl.col('event').pldt.tomicroseconds()
dates = frame.select(expr)['event']
print(dates.to_list())
```

**Output**

```text
[-2, None]
```


## Read POSIX seconds from timezone-aware dates

(pldt-expr-timestamp)=
```python
import polars as pl
import rstimes.pldt
frame = pl.DataFrame([pl.Series('event', [0, None], dtype=pl.Datetime('us', 'Asia/Shanghai'))])
expr = pl.col('event').pldt.timestamp()
dates = frame.select(expr)['event']
print(dates.to_list())
```

**Output**

```text
[0.0, None]
```


## Format fractional seconds from stored nanoseconds

(pldt-expr-strftime)=
```python
import polars as pl
import rstimes.pldt
frame = pl.DataFrame([pl.Series('event', [123_456_789, None], dtype=pl.Datetime('ns'))])
expr = pl.col('event').pldt.strftime('%f|%.3f|%.0f')
dates = frame.select(expr)['event']
print(dates.to_list())
```

**Output**

```text
['123456789|.123|', None]
```
