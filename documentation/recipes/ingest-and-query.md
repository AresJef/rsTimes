# Calculate renewal dates from a Polars text feed

Parse the event times as UTC nanosecond dates. Add a calendar month
in the next query stage, when the parsed column is available.

(renewal-calculate-from-text-feed)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({"raw": [
    "2024-01-31T12:00:00.000000123Z",
    None,
    "2024-02-29T12:00:00.000000789Z",
]})
parsed = pl.col("raw").pldt.parse(unit="ns", tz="UTC").alias("event")
renewal = pl.col("event").pldt.add(months=1).alias("renewal")
dates = frame.lazy().with_columns(parsed).select("event", renewal).collect()
print(dates["renewal"].to_physical().to_list())
```

**Output**

```text
[1709208000000000123, None, 1711713600000000789]
```

The renewals are February 29 and March 29 at 12:00 UTC.
The original fractional tails and missing position stay in both
columns. January 31 fits to the final day of February. Continue
with [calendar transformations](../guides/expressions-calendar.md)
or [native formatted output](../guides/expressions-output.md).
