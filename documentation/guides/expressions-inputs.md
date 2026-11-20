# Parse or build date columns in native queries

## Normalize aware text to UTC

(expr-parse-aware-text-utc)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({"raw": ["1970-01-01T05:30:00+05:30", None]})
expr = pl.col("raw").pldt.parse(unit="ns", tz="UTC").alias("event")
print(frame.lazy().select(expr).collect()["event"].to_physical().to_list())
```

**Output**

```text
[0, None]
```

Choose `unit` for String input and an explicit target `tz` for
aware text. Native Datetime supplies its known unit and zone. Date
promotes to midnight. Generic numeric parsing uses ticks of the
chosen unit. Use `fromseconds` or `fromtimestamp` for seconds.

An expression captures its effective Configs rules and prepares a
complete `default` when created. The default supplies missing Y/M/D
fields. Subsequent edits affect newly built expressions and new eager
calls. For details, see [execution, grouping and snapshots](expressions-execution.md).

## Build dates from numeric day-of-year columns

(expr-native-unsigned-calendar)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({
    "year": pl.Series([2024, 2023, None], dtype=pl.UInt16),
    "doy": pl.Series([60, 60, None], dtype=pl.UInt8),
})
expr = pl.col("year").pldt.fromdayofyear(pl.col("doy")).alias("event")
print(frame.lazy().select(expr).collect()["event"].to_list())
```

**Output**

```text
[datetime.datetime(2024, 2, 29, 0, 0), datetime.datetime(2023, 3, 1, 0, 0), None]
```

The calendar-coordinate factories default to microseconds. They
accept native integer source types, including UInt128 for values
within the calendar range. Missing source components propagate.
Use a scalar component or a corresponding column. Number ISO
weekdays Monday=1 through Sunday=7.

## Decode a timestamp with a known format

(expr-strptime-chosen-resolution)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({"raw": ["1970-01-01 00:00:00.123456789", None]})
expr = pl.col("raw").pldt.strptime("%Y-%m-%d %H:%M:%S.%f", unit="us").alias("event")
print(frame.select(expr)["event"].to_physical().to_list())
```

**Output**

```text
[123456, None]
```

`strptime` requires a unit when the format reads a fraction
and a target zone when the format reads a zone. It truncates the
fraction to the chosen output unit. Use `fromisoformat` for
strict ISO input. Give `combine` an explicit unit when its
clock column can supply a fractional precision unavailable at
planning time, such as a Time or String expression.

(expr-factory-input-roles)=
## Choose the date factory by input

| Factory | Input role |
| --- | --- |
| `fromseconds`, `frommicroseconds` | Epoch clock coordinates with an optional target zone. |
| `fromtimestamp`, `utcfromtimestamp` | POSIX seconds as instants. Choose a unit for floating seconds. |
| `fromdate`, `fromdatetime` | An actual native Date or Datetime column. |
| `fromordinal`, `fromisocalendar`, `fromdayofyear` | Integer calendar coordinates and components. |
| `fromisoformat`, `strptime` | ISO-only text or explicit format text. |
| `combine` | Calendar date plus a clock from a literal or column. |

## Handle malformed data in an otherwise valid query

(expr-report-invalid-row)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({"raw": ["2024-02-29", "2024-02-30"]})
expr = pl.col("raw").pldt.parse(unit="us", strict=True)
try:
    frame.lazy().select(expr).collect()
except pl.exceptions.PolarsError as error:
    print(type(error).__name__)
```

**Output**

```text
ComputeError
```

Use `strict=True` to reject explicitly out-of-range date fields.
The default parser can fit recognized fields to their valid ranges.

Invalid option values can fail when the Expr is created.
Schema and row failures can occur when Polars plans or executes
the query. An otherwise valid schema does not make malformed
data parseable.
