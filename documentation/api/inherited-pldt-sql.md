# Query an rsTimes date column with native SQL

The inherited `sql` helper executes a query against the Pldt receiver and
returns an ordinary Polars DataFrame. Its default table name is `self`;
`table_name` can give it an explicit query name. The returned date column
retains its unit, timezone and validity. This helper does not return a Pldt
or a deferred LazyFrame.

```{doctest} inherited-pldt-native-sql
>>> import polars as pl
>>> from rstimes import Pldt
>>> first, last = 1704067200000000123, 1704240000000000789
>>> ticks = [last, None, first, last]
>>> value = Pldt(pl.Series('event', ticks, dtype=pl.Datetime('ns', 'UTC')))
>>> selected = value.sql('SELECT event FROM self WHERE event IS NOT NULL ORDER BY event')
>>> (type(selected) is pl.DataFrame, selected.schema == {'event': value.dtype}, selected.shape)
(True, True, (3, 1))
>>> selected['event'].to_physical().to_list()
[1704067200000000123, 1704240000000000789, 1704240000000000789]
>>> missing = value.sql('SELECT event FROM dates WHERE event IS NULL', table_name='dates')
>>> (type(missing) is pl.DataFrame, missing.schema == {'event': value.dtype}, missing['event'].to_physical().to_list())
(True, True, [None])
>>> value.to_physical().to_list() == ticks
True
```

Use [rsTimes lazy expressions](../guides/expressions.md) when composing `.pldt`
operations in a query plan. The inherited SQL helper follows the
[native SQL API](https://docs.pola.rs/api/python/stable/reference/series/api/polars.Series.sql.html)
for its query language and provider stability policy.
