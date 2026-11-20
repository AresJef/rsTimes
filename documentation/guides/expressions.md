# Run dates in a Polars query

Load the integration with `import rstimes.pldt`. An Expr namespace
call builds an ordinary Polars expression. The result is a native
Polars column when the query runs.

## Parse text in a lazy DataFrame

(expr-parse-native-query)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({"raw": ["1970-01-01T00:00:00.000000123", None]})
expr = pl.col("raw").pldt.parse(unit="ns").alias("event")
eager = frame.select(expr)
lazy = frame.lazy().select(expr).collect()
print(eager["event"].to_physical().to_list())
print(lazy["event"].to_physical().to_list())
```

**Output**

```text
[123, None]
[123, None]
```

The `event` dtype is Datetime(ns), and the missing row is null.
Set `unit` explicitly for String input. Give aware text a target
`tz`. Native Date and Datetime inputs can supply information
from their declared dtype. Use `collect_schema()` to inspect
the declared output and `collect()` to validate actual rows.

Build a Pldt when you need the eager date class or its checked
exports. Eager-only operations include `fromdatetime64`,
`date_range`, `now`, `today`, `utcnow`,
Python datetime/time exports and Python timezone metadata.
A completed native date Series can be passed as a literal.

Continue with [parse and build date inputs](expressions-inputs.md)
or [pair row arguments, groups and windows](expressions-execution.md).
