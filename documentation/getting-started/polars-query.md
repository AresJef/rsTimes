# Parse dates in a Polars query

Install the Polars extra with `python -m pip install "rsTimes[polars]==1.1.0"`.
Load `rstimes.pldt` to register `.pldt` on native Polars expressions.

## Convert a text column that contains a null

(getting-started-polars-parse-null)=
```python
import polars as pl
import rstimes.pldt

dates = ["2024-02-29", None]
events = pl.DataFrame({"date": dates})
source = pl.col("date")
parsed = source.pldt.parse(unit="us")
query = events.lazy().select(parsed)
result = query.collect()
column = result["date"]
print(column.dt.date().to_list())
```

**Output**

```text
[datetime.date(2024, 2, 29), None]
```

`collect()` runs the query. The `date` column is a Polars
`Datetime("us")` with no time zone. The second row stays null. The final
line displays the calendar dates.

See [when a date expression runs](../guides/expressions-execution.md) and
[which inputs it can parse](../guides/expressions-inputs.md).
