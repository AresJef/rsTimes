# Query an rsTimes date column with native SQL

## Order nonnull native dates in SQL

(ref-pldt-native-sql-sort)=
```python
from rstimes import Pldt

events = Pldt([9, None, 5], unit="ns", tz="UTC", name="event")
ordered = events.sql("SELECT event FROM self WHERE event IS NOT NULL ORDER BY event")
print(ordered["event"].to_physical().to_list())
```

**Output**

```text
[5, 9]
```

The inherited `sql` helper executes a query against the Pldt receiver and
returns an ordinary Polars DataFrame. Its default table name is `self`;
`table_name` can give it an explicit query name. The returned date column
retains its unit, timezone and validity. This helper does not return a Pldt
or a deferred LazyFrame.

Use [rsTimes lazy expressions](../guides/expressions.md) when composing `.pldt`
operations in a query plan. The inherited SQL helper follows the
[native SQL API](https://docs.pola.rs/api/python/stable/reference/series/api/polars.Series.sql.html)
for its query language and provider stability policy.
