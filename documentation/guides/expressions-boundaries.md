# Execute date boundaries and grids

Boundary expressions return native Datetime columns. Their queries return
Boolean columns, with False at source nulls. All examples below execute actual
select, collect and streaming queries; the schema, integer dates and predicate
values are compared with independent literal answers.

## First/last days and first/last representable instants

```{doctest} expr-period-boundaries
>>> from datetime import date, timedelta
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt
>>> def tick(text):
...     return int(np.datetime64(text, 'ns').astype(np.int64))
>>> def check(frame, expression, dtype, expected):
...     assert isinstance(expression, pl.Expr)
...     expression = expression.alias('result')
...     query = frame.lazy().select(expression)
...     assert query.collect_schema() == {'result': dtype}
...     for result in (frame.select(expression), query.collect(), query.collect(engine='streaming')):
...         assert result.schema == {'result': dtype} and type(result['result']) is pl.Series
...         assert result['result'].to_physical().to_list() == expected
>>> frame = pl.DataFrame({'event': pl.Series([tick('2024-02-29T12:34:56.123456789'), None], dtype=pl.Datetime('ns', 'UTC'))})
>>> days = [('Y', '2024-01-01', '2024-12-31'), ('Q', '2024-01-01', '2024-03-31'), ('M', '2024-02-01', '2024-02-29'), ('W', '2024-02-26', '2024-03-03'), ('January', '2024-01-01', '2024-01-31')]
>>> for period, first, last in days:
...     a = pl.col('event').pldt.to_first_of(period)
...     b = pl.col('event').pldt.to_last_of(period)
...     check(frame, a, pl.Datetime('ns', 'UTC'), [tick(first + 'T12:34:56.123456789'), None])
...     check(frame, b, pl.Datetime('ns', 'UTC'), [tick(last + 'T12:34:56.123456789'), None])
...     check(frame, a.pldt.is_first_of(period), pl.Boolean, [True, False])
...     check(frame, b.pldt.is_last_of(period), pl.Boolean, [True, False])
>>> periods = [
...     ('Y', '2024-01-01T00:00:00', '2024-12-31T23:59:59.999999999'),
...     ('Q', '2024-01-01T00:00:00', '2024-03-31T23:59:59.999999999'),
...     ('M', '2024-02-01T00:00:00', '2024-02-29T23:59:59.999999999'),
...     ('W', '2024-02-26T00:00:00', '2024-03-03T23:59:59.999999999'),
...     ('D', '2024-02-29T00:00:00', '2024-02-29T23:59:59.999999999'),
...     ('h', '2024-02-29T12:00:00', '2024-02-29T12:59:59.999999999'),
...     ('min', '2024-02-29T12:34:00', '2024-02-29T12:34:59.999999999'),
...     ('s', '2024-02-29T12:34:56', '2024-02-29T12:34:56.999999999'),
...     ('ms', '2024-02-29T12:34:56.123000', '2024-02-29T12:34:56.123999999'),
...     ('us', '2024-02-29T12:34:56.123456', '2024-02-29T12:34:56.123456999'),
...     ('ns', '2024-02-29T12:34:56.123456789', '2024-02-29T12:34:56.123456789'),
...     ('Monday', '2024-02-26T00:00:00', '2024-02-26T23:59:59.999999999'),
... ]
>>> for period, first, last in periods:
...     a = pl.col('event').pldt.to_start_of(period)
...     b = pl.col('event').pldt.to_end_of(period)
...     check(frame, a, pl.Datetime('ns', 'UTC'), [tick(first), None])
...     check(frame, b, pl.Datetime('ns', 'UTC'), [tick(last), None])
...     check(frame, a.pldt.is_start_of(period), pl.Boolean, [True, False])
...     check(frame, b.pldt.is_end_of(period), pl.Boolean, [True, False])
>>> for unit, scale in [('ms', 1000), ('us', 1000000), ('ns', 1000000000)]:
...     epoch = pl.DataFrame({'event': pl.Series([0, None], dtype=pl.Datetime(unit))})
...     check(epoch, pl.col('event').pldt.to_end_of('D'), pl.Datetime(unit), [86400 * scale - 1, None])
>>> limits = pl.DataFrame({'event': pl.Series([-2**63, 2**63 - 1, None], dtype=pl.Datetime('ns'))})
>>> for method in ('is_first_of', 'is_last_of', 'is_start_of', 'is_end_of'):
...     check(limits, getattr(pl.col('event').pldt, method)('Y'), pl.Boolean, [False, False, False])
```

First/last day selection retains the original clock. Start/end selection uses
the unit's last representable tick. A query can return False for a boundary
outside capacity without trying to construct that boundary.

## Round, floor, ceil, snap, and fractional precision

Date rounding uses positive fixed grids and ties to even. Snap selects a
nearest actual single-period start and resolves a tie later. Fractional
precision truncates only the chosen subsecond part while retaining storage.

```{doctest} expr-rounding-snap-fsp
>>> ties = pl.DataFrame({'event': pl.Series([1500, 2500, -1500, -2500, None], dtype=pl.Datetime('ns'))})
>>> answers = {'round': [2000, 2000, -2000, -2000, None], 'floor': [1000, 2000, -2000, -3000, None], 'ceil': [2000, 3000, -1000, -2000, None]}
>>> for method, expected in answers.items():
...     for grid in ('us', timedelta(microseconds=1)):
...         check(ties, getattr(pl.col('event').pldt, method)(grid), pl.Datetime('ns'), expected)
>>> middle = pl.DataFrame({'event': pl.Series([tick('2024-01-02T12:30'), None], dtype=pl.Datetime('ns'))})
>>> check(middle, pl.col('event').pldt.round('h'), pl.Datetime('ns'), [tick('2024-01-02T12:00'), None])
>>> check(middle, pl.col('event').pldt.snap('h'), pl.Datetime('ns'), [tick('2024-01-02T13:00'), None])
>>> check(middle, pl.col('event').pldt.round('15min'), pl.Datetime('ns'), [tick('2024-01-02T12:30'), None])
>>> for period, expected in [('Y', '2024-01-01'), ('Q', '2024-04-01'), ('M', '2024-03-01'), ('W', '2024-03-04'), ('D', '2024-03-01'), ('h', '2024-02-29T13:00'), ('min', '2024-02-29T12:35'), ('s', '2024-02-29T12:34:56'), ('Monday', '2024-03-04'), ('January', '2024-01-01')]:
...     check(frame, pl.col('event').pldt.snap(period), pl.Datetime('ns', 'UTC'), [tick(expected), None])
>>> fractions = pl.DataFrame({'event': pl.Series([123456789, None], dtype=pl.Datetime('ns'))})
>>> for precision, expected in [(0, 0), (1, 100000000), (2, 120000000), (3, 123000000), (4, 123400000), (5, 123450000), (6, 123456000), (7, 123456700), (8, 123456780), (9, 123456789), (12, 123456789)]:
...     check(fractions, pl.col('event').pldt.fsp(precision), pl.Datetime('ns'), [expected, None])
```

## Native timezone edges and failures

A missing midnight starts at the first existing clock in that day. Repeated
hours retain the correct occurrence. The below snap/round example intentionally
has different answers, both computed on the actual native timezone timeline.

```{doctest} expr-zone-boundaries-and-errors
>>> sao = pl.DataFrame({'event': pl.Series([tick('2018-11-04T14:00'), None], dtype=pl.Datetime('ns', 'America/Sao_Paulo'))})
>>> check(sao, pl.col('event').pldt.normalize(), pl.Datetime('ns', 'America/Sao_Paulo'), [tick('2018-11-04T03:00'), None])
>>> repeated = pl.DataFrame({'event': pl.Series([tick('2024-11-03T06:30'), None], dtype=pl.Datetime('ns', 'America/New_York'))})
>>> check(repeated, pl.col('event').pldt.to_start_of('h'), pl.Datetime('ns', 'America/New_York'), [tick('2024-11-03T06:00'), None])
>>> check(repeated, pl.col('event').pldt.to_end_of('h'), pl.Datetime('ns', 'America/New_York'), [tick('2024-11-03T06:59:59.999999999'), None])
>>> first = pl.DataFrame({'event': pl.Series([tick('2024-11-03T05:30'), None], dtype=pl.Datetime('ns', 'America/New_York'))})
>>> check(first, pl.col('event').pldt.snap('h'), pl.Datetime('ns', 'America/New_York'), [tick('2024-11-03T06:00'), None])
>>> check(first, pl.col('event').pldt.round('h'), pl.Datetime('ns', 'America/New_York'), [tick('2024-11-03T07:00'), None])
>>> for build, error in [(lambda: pl.col('event').pldt.to_first_of('D'), ValueError), (lambda: pl.col('event').pldt.to_start_of('15min'), ValueError), (lambda: pl.col('event').pldt.round('0s'), ValueError), (lambda: pl.col('event').pldt.fsp(True), TypeError)]:
...     try:
...         build()
...     except error:
...         continue
...     raise AssertionError('invalid static options were accepted')
>>> native_date = pl.DataFrame({'event': pl.Series([date(1970, 1, 2), None], dtype=pl.Date)})
>>> check(native_date, pl.col('event').pldt.snap('D'), pl.Datetime('ms'), [86400000, None])
>>> for execute in (lambda: native_date.select(pl.col('event').pldt.normalize()), lambda: limits.lazy().select(pl.col('event').pldt.to_start_of('Y')).collect()):
...     try:
...         execute()
...     except pl.exceptions.PolarsError:
...         continue
...     raise AssertionError('dtype or capacity failure was not propagated')
```

Boundaries require a prepared Datetime column. Grid operations can promote Date
without guessing how to parse String. Static option errors occur at creation;
native schema/value failures retain Polars' execution-phase error family.
