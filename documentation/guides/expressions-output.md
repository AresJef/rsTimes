# Native output columns and Struct expressions

Expr outputs stay inside Polars: numbers, strings, Date, Time, naive Datetime,
and Struct. Every result below is checked after eager select, lazy collect and
streaming execution. Eager DataFrame time tables correspond to one Struct
column in an expression query.

## Numeric and native temporal outputs

Local seconds and microseconds use wall-clock coordinates unless `utc=True`.
Timestamp requests an instant. Integer microseconds floor a nanosecond tail at
this explicit output; Float64 seconds cannot preserve every distant nanosecond.

```{doctest} expr-native-output-types
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt
>>> def check(frame, expression, dtype, expected, physical=False):
...     assert isinstance(expression, pl.Expr)
...     expression = expression.alias('result')
...     query = frame.lazy().select(expression)
...     assert query.collect_schema() == {'result': dtype}
...     for result in (frame.select(expression), query.collect(), query.collect(engine='streaming')):
...         column = result['result']
...         assert result.schema == {'result': dtype} and type(column) is pl.Series
...         assert (column.to_physical().to_list() if physical else column.to_list()) == expected
>>> frame = pl.DataFrame({'event': pl.Series([999, None], dtype=pl.Datetime('ns', 'Asia/Shanghai'))})
>>> outputs = [('toseconds', (), pl.Float64, 28800.000000999), ('toseconds', (True,), pl.Float64, 0.000000999), ('tomicroseconds', (), pl.Int64, 28800000000), ('tomicroseconds', (True,), pl.Int64, 0), ('timestamp', (), pl.Float64, 0.000000999), ('toordinal', (), pl.Int64, 719163)]
>>> for method, arguments, dtype, value in outputs:
...     check(frame, getattr(pl.col('event').pldt, method)(*arguments), dtype, [value, None])
>>> for attribute, dtype, value in [('values_naive', pl.Datetime('ns'), 28800000000999), ('date', pl.Date, 0), ('time', pl.Time, 28800000000999)]:
...     check(frame, getattr(pl.col('event').pldt, attribute), dtype, [value, None], physical=True)
>>> negative = pl.DataFrame({'event': pl.Series([-1, None], dtype=pl.Datetime('ns'))})
>>> check(negative, pl.col('event').pldt.tomicroseconds(), pl.Int64, [-1, None])
```

## Fixed-schema time Structs

The nine fields have fixed native integer child types. Local DST is −1 when
unspecified, 0 for zero, and 1 for a legal nonzero adjustment. UTC uses 0.
A source null is an outer Struct null, rather than a nonnull Struct with
independently guessed child values.

```{doctest} expr-time-table-struct-output
>>> keys = ['tm_year', 'tm_mon', 'tm_mday', 'tm_hour', 'tm_min', 'tm_sec', 'tm_wday', 'tm_yday', 'tm_isdst']
>>> dtypes = [pl.Int64, pl.Int8, pl.Int8, pl.Int8, pl.Int8, pl.Int8, pl.Int8, pl.Int16, pl.Int8]
>>> dtype = pl.Struct(dict(zip(keys, dtypes)))
>>> local = dict(zip(keys, [1970, 1, 1, 8, 0, 0, 3, 1, 0]))
>>> utc = dict(zip(keys, [1970, 1, 1, 0, 0, 0, 3, 1, 0]))
>>> check(frame, pl.col('event').pldt.timedf(), dtype, [local, None])
>>> check(frame, pl.col('event').pldt.utctimedf(), dtype, [utc, None])
>>> for method in ('timedf', 'utctimedf'):
...     empty = pl.DataFrame({'event': pl.Series([], dtype=pl.Datetime('ns', 'UTC'))})
...     check(empty, getattr(pl.col('event').pldt, method)(), dtype, [])
>>> expanded = frame.lazy().select(pl.col('event').pldt.timedf().alias('clock')).unnest('clock').collect()
>>> (expanded.schema == dict(zip(keys, dtypes)), expanded.row(0), expanded.row(1))
(True, (1970, 1, 1, 8, 0, 0, 3, 1, 0), (None, None, None, None, None, None, None, None, None))
```

## ISO, explicit fractions, and localized text

ISO timespec aliases truncate display only. `strftime('%f')` uses nine digits
at ns storage and six at ms/us. Explicit `%.1f`–`%.9f` emits a dot and that many
fraction digits; `%.0f` emits nothing. CLDR locale names come from bundled data,
without a runtime Babel requirement.

```{doctest} expr-text-output-and-locales
>>> fraction = pl.DataFrame({'event': pl.Series([123456789, None], dtype=pl.Datetime('ns'))})
>>> specs = {'auto': '00:00:00.123456789', 'hours': '00', 'h': '00', 'minutes': '00:00', 'm': '00:00', 'min': '00:00', 'seconds': '00:00:00', 's': '00:00:00', 'milliseconds': '00:00:00.123', 'ms': '00:00:00.123', 'microseconds': '00:00:00.123456', 'us': '00:00:00.123456', 'nanoseconds': '00:00:00.123456789', 'ns': '00:00:00.123456789'}
>>> for timespec, clock in specs.items():
...     check(fraction, pl.col('event').pldt.isoformat(sep='日', timespec=timespec), pl.String, ['1970-01-01日' + clock, None])
>>> fractions = ['', '.1', '.12', '.123', '.1234', '.12345', '.123456', '.1234567', '.12345678', '.123456789']
>>> for precision, expected in enumerate(fractions):
...     check(fraction, pl.col('event').pldt.strftime('%.' + str(precision) + 'f'), pl.String, [expected, None])
>>> for unit, tick, expected in [('ms', 123, '123000'), ('us', 123456, '123456'), ('ns', 123456789, '123456789')]:
...     typed = pl.DataFrame({'event': pl.Series([tick, None], dtype=pl.Datetime(unit))})
...     check(typed, pl.col('event').pldt.strftime('%f'), pl.String, [expected, None])
>>> texts = [('ctime', (), 'Thu Jan  1 08:00:00 1970'), ('month_name', (), 'January'), ('month_name', ('zh_CN',), '一月'), ('weekday_name', ('fr_FR',), 'jeudi'), ('tzname', (), 'CST')]
>>> for method, arguments, expected in texts:
...     check(frame, getattr(pl.col('event').pldt, method)(*arguments), pl.String, [expected, None])
>>> naive = pl.DataFrame({'event': pl.Series([0, None], dtype=pl.Datetime('ns'))})
>>> check(naive, pl.col('event').pldt.tzname(), pl.String, [None, None])
>>> for build, error in [(lambda: pl.col('event').pldt.isoformat(sep=''), ValueError), (lambda: pl.col('event').pldt.isoformat(timespec='bad'), ValueError), (lambda: pl.col('event').pldt.strftime(None), TypeError), (lambda: pl.col('event').pldt.month_name('no_such_locale'), ValueError)]:
...     try:
...         build()
...     except error:
...         continue
...     raise AssertionError('invalid static output option was accepted')
```

## A collected Series uses its native export protocol

An expression result is an ordinary Polars Series. Its native NumPy export can
turn a valid minimum tick into NaT. Wrap a collected Datetime column in Pldt
when requesting Pldt's checked export behavior. That wrapper preserves native
dates and nulls before the explicit exit; its default export rejects the loss.

```{doctest} expr-collected-native-versus-protected-export
>>> frame = pl.DataFrame({'event': pl.Series([-2**63, None], dtype=pl.Datetime('ns'))})
>>> expression = pl.col('event').pldt.add(nanoseconds=0)
>>> for result in (frame.select(expression), frame.lazy().select(expression).collect()):
...     column = result['event']
...     assert type(column) is pl.Series and column.is_null().to_list() == [False, True]
...     assert np.isnat(column.to_numpy()).tolist() == [True, True]
...     protected = Pldt(column)
...     try:
...         protected.to_numpy()
...     except OverflowError:
...         continue
...     raise AssertionError('Pldt failed to reject the valid-tick/NaT collision')
```

Explicit Python object exits such as `datetime()` and `timetz` require an eager
column. See [Pldt output representations](pldt-output.md) for their deliberate
microsecond truncation, fold and year limits.
