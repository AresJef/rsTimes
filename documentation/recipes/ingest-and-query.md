# Parse event text and calculate renewal dates

An event feed contains ISO timestamps with ns fractions and missing rows.
Parse it with an explicit unit and target timezone, then add one calendar
month in a second query stage. January 31 clamps to February 29 in 2024;
February 29 advances to March 29. This is a calendar-month operation rather
than a fixed number of seconds.

Importing Pldt registers the `.pldt` expression namespace. Both the eager and
lazy query below actually execute; constructing the expressions is only the
first step.

```{doctest} recipe-event-renewals
>>> import polars as pl
>>> from rstimes import Pldt
>>> frame = pl.DataFrame({'raw': ['2024-01-31T12:00:00.000000123Z', None, '2024-02-29T12:00:00.000000789Z']})
>>> parsed = pl.col('raw').pldt.parse(unit='ns', tz='UTC').alias('when')
>>> renewal = pl.col('when').pldt.add(months=1).alias('renewal')
>>> (type(parsed) is pl.Expr, type(renewal) is pl.Expr)
(True, True)
>>> eager = frame.with_columns(parsed).select('when', renewal)
>>> collected = frame.lazy().with_columns(parsed).select('when', renewal).collect()
>>> (type(eager) is pl.DataFrame, eager.equals(collected), eager.shape)
(True, True, (3, 2))
>>> eager.schema == {'when': pl.Datetime('ns', 'UTC'), 'renewal': pl.Datetime('ns', 'UTC')}
True
>>> eager['when'].to_physical().to_list()
[1706702400000000123, None, 1709208000000000789]
>>> eager['renewal'].to_physical().to_list()
[1709208000000000123, None, 1711713600000000789]
>>> type(eager['renewal']) is pl.Series
True
>>> renewals = Pldt(eager['renewal'])
>>> (type(renewals) is Pldt, renewals.name, renewals.dtype == pl.Datetime('ns', 'UTC'))
(True, 'renewal', True)
>>> renewals.strftime('%Y-%m-%d').to_list()
['2024-02-29', None, '2024-03-29']
>>> frame['raw'].to_list()[1] is None
True
```

The collected columns are native Polars Series. Wrap one in Pldt when you need
the eager rsTimes class; its native date storage keeps the original fractions
and null positions. Keep `ns` until you deliberately choose another unit.

Continue with [expression input rules](../guides/expressions-inputs.md) for
parsing configurations and rejected inputs, [calendar changes](../guides/expressions-calendar.md)
for other date fields, and [date queries](../guides/expressions-queries.md)
for filtering and aggregation.
