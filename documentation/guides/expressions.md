# Dates in Polars expressions

Import `Pldt` from `rstimes` to register `.pldt` on Polars Series and Expr. An expression
method returns a native `polars.Expr`. Execute it with `select`, or with
`collect` in a lazy query, to obtain data.

## Parse a text column lazily

The first input lies 123 nanoseconds after the Unix epoch. The second is null.
Parsing keeps the nanosecond resolution and the missing position.

```{doctest} expr-lazy-parse
>>> import polars as pl
>>> from rstimes import Pldt
>>> frame = pl.DataFrame({'raw': ['1970-01-01T00:00:00.000000123', None]})
>>> expression = pl.col('raw').pldt.parse(unit='ns').alias('time')
>>> isinstance(expression, pl.Expr)
True
>>> result = frame.lazy().select(expression).collect()
>>> eager = frame.select(expression)
>>> eager.equals(result)
True
>>> (result.shape, result.schema == {'time': pl.Datetime('ns')})
((2, 1), True)
>>> (type(result['time']) is pl.Series, result['time'].to_physical().to_list())
(True, [123, None])
```

The collected column is a Polars Series. Use `Pldt` when you want its concrete
eager class. Null validity is independent of the integer date value; a valid
minimum signed integer is not automatically a null in Polars.

Expr has a static result schema, so String parsing requires an explicit unit
and aware text requires an explicit target zone. Use the
[input and factory guide](expressions-inputs.md) for actual executed examples,
configuration snapshots and errors. A Python option error can occur when an
Expr is created; schema- or row-dependent errors can wait until select/collect.

Not every eager method has an expression counterpart. `fromdatetime64`,
`date_range`, `now`, `today` and `utcnow` are eager factories. Explicit Python
object exits such as `datetime()` and `timetz`, and whole-column Python timezone
metadata, belong to eager columns. An eager completed native Series can be used
as a literal in a query, as shown in [date ranges](pldt-ranges.md).
