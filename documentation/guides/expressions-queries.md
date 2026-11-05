# Query dates, differences, and a captured clock

Library Expr queries return native Polars columns. Integer queries use Int64
with nulls. Boolean date predicates use Boolean and False at nulls. ISO calendar
output is a Struct with UInt32 children and an outer null. These types are
checked in actual select, collect and streaming execution below.

## All integer queries and predicates

```{doctest} expr-calendar-integer-and-boolean-queries
>>> from datetime import date
>>> import time
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt
>>> def check(frame, expression, dtype, expected):
...     assert isinstance(expression, pl.Expr)
...     expression = expression.alias('result')
...     query = frame.lazy().select(expression)
...     assert query.collect_schema() == {'result': dtype}
...     for result in (frame.select(expression), query.collect(), query.collect(engine='streaming')):
...         assert result.schema == {'result': dtype} and type(result['result']) is pl.Series
...         assert result['result'].to_list() == expected
>>> tick = int(np.datetime64('2024-02-29T12:34:56.123456789', 'ns').astype(np.int64))
>>> frame = pl.DataFrame({'event': pl.Series([tick, None], dtype=pl.Datetime('ns'))})
>>> properties = {'year': 2024, 'month': 2, 'day': 29, 'hour': 12, 'minute': 34, 'second': 56, 'millisecond': 123, 'microsecond': 123456, 'nanosecond': 789, 'weekday': 3, 'quarter': 1, 'day_of_year': 60, 'days_in_month': 29}
>>> methods = {'isoyear': 2024, 'isoweek': 9, 'isoweekday': 4, 'days_in_year': 366, 'days_bf_year': 738885, 'days_in_quarter': 91, 'days_bf_quarter': 0, 'day_of_quarter': 60, 'days_bf_month': 31, 'day_of_month': 29}
>>> for name, expected in {**properties, **methods}.items():
...     expression = getattr(pl.col('event').pldt, name)
...     check(frame, expression() if name in methods else expression, pl.Int64, [expected, None])
>>> for method, target in [('is_year', 2024), ('is_quarter', 1), ('is_month', 'February'), ('is_weekday', 'Thursday'), ('is_day', 29)]:
...     check(frame, getattr(pl.col('event').pldt, method)(target), pl.Boolean, [True, False])
>>> check(frame, pl.col('event').pldt.is_leap_year, pl.Boolean, [True, False])
>>> check(frame, pl.col('event').pldt.is_long_year(), pl.Boolean, [False, False])
>>> check(frame, pl.col('event').pldt.is_month(13), pl.Boolean, [False, False])
>>> check(frame, pl.col('event').pldt.leap_bt_year(2025), pl.Int64, [1, None])
>>> check(frame, pl.col('event').pldt.isocalendar(), pl.Struct({'year': pl.UInt32, 'week': pl.UInt32, 'day': pl.UInt32}), [{'year': 2024, 'week': 9, 'day': 4}, None])
>>> dates = pl.DataFrame({'event': [date(2024, 2, 29), None]})
>>> check(dates, pl.col('event').pldt.year, pl.Int64, [2024, None])
```

Ordinary weekday numbers are Monday=0; ISO weekday numbers are Monday=1.
`nanosecond` is the 0–999 tail after microseconds. `leap_bt_year` counts the
lower-inclusive range, regardless of direction. Matching targets broadcast
only when scalar; optional-looking null targets are still errors for these
required query arguments.

## Native row targets and ISO capacity

```{doctest} expr-query-row-arguments-and-errors
>>> rows = pl.DataFrame({'event': pl.Series([0, 2678400000000000, None], dtype=pl.Datetime('ns')), 'month': [1, 2, 3]})
>>> check(rows, pl.col('event').pldt.is_month(pl.col('month')), pl.Boolean, [True, True, False])
>>> check(rows, pl.col('event').pldt.is_month(pl.col('month').min()), pl.Boolean, [True, False, False])
>>> for build, error in [(lambda: pl.col('event').pldt.is_quarter(True), TypeError), (lambda: pl.col('event').pldt.is_day(None), TypeError), (lambda: pl.col('event').pldt.is_weekday('unknown'), ValueError)]:
...     try:
...         build()
...     except error:
...         continue
...     raise AssertionError('invalid query target was accepted')
>>> signed = pl.DataFrame({'event': pl.Series([-62167219200000000], dtype=pl.Datetime('us'))})
>>> check(signed, pl.col('event').pldt.isoyear(), pl.Int64, [-1])
>>> for execute in (lambda: signed.select(pl.col('event').pldt.isocalendar()), lambda: signed.lazy().select(pl.col('event').pldt.isocalendar()).collect()):
...     try:
...         execute()
...     except pl.exceptions.PolarsError as error:
...         assert 'UInt32' in str(error)
...     else:
...         raise AssertionError('a negative ISO year fit UInt32')
```

## Every difference unit and inclusive rule

`.pldt.diff` counts buckets, self minus target. It does not mean the inherited
native adjacent-element diff. Numeric targets are seconds, and aware targets
use UTC coordinates. A valid minimum Int64 difference remains a value, not a
missing marker.

```{doctest} expr-all-boundary-differences
>>> late = pl.DataFrame({'event': pl.Series([1706745600000000000, None], dtype=pl.Datetime('ns'))})
>>> units = {'Y': 0, 'Q': 0, 'M': 1, 'W': 0, 'D': 1, 'h': 1, 'm': 1, 'min': 1, 's': 1, 'ms': 1000, 'us': 1000000, 'ns': 1000000000}
>>> for unit, expected in units.items():
...     check(late, pl.col('event').pldt.diff('2024-01-31 23:59:59', unit), pl.Int64, [expected, None])
>>> signed = pl.DataFrame({'event': pl.Series([-2, -1, 0, 1, 2, None], dtype=pl.Datetime('ns'))})
>>> for absolute in (False, True):
...     for inclusive, adjustment in [('one', 0), ('both', 1), ('neither', -1)]:
...         values = [abs(v) if absolute else v for v in [-2, -1, 0, 1, 2]]
...         expected = [v + (-adjustment if v < 0 else adjustment) for v in values] + [None]
...         check(signed, pl.col('event').pldt.diff(np.datetime64(0, 'ns'), 'ns', absolute, inclusive), pl.Int64, expected)
>>> minimum = pl.DataFrame({'event': pl.Series([-2**63, None], dtype=pl.Datetime('ns'))})
>>> check(minimum, pl.col('event').pldt.diff(np.datetime64(0, 'ns'), 'ns'), pl.Int64, [-2**63, None])
>>> targets = pl.DataFrame({'event': pl.Series([0, 1, 2, None], dtype=pl.Datetime('us')), 'target': [0, 0, 0, 0]})
>>> check(targets, pl.col('event').pldt.diff(pl.col('target').min(), 'us'), pl.Int64, [0, 1, 2, None])
>>> check(targets, pl.col('event').pldt.diff(pl.col('target'), 'us'), pl.Int64, [0, 1, 2, None])
```

## A real captured-clock example

`is_past` and `is_future` capture one reference when the Expr is created.
Re-executing it does not move that reference. Build a fresh Expr to ask about
the current instant again. Comparisons are strict; null dates match neither.
This example uses the real system clock and waits about two seconds to cross
its target, without substituting a clock callback.

```{doctest} expr-real-clock-snapshot
>>> def demonstrate_snapshot():
...     target = time.time_ns() + 2000000000
...     frame = pl.DataFrame({'event': pl.Series([target, None], dtype=pl.Datetime('ns', 'UTC'))})
...     past = pl.col('event').pldt.is_past()
...     future = pl.col('event').pldt.is_future()
...     assert time.time_ns() < target, 'system stalled during expression creation'
...     deadline = time.monotonic() + 6
...     while time.time_ns() <= target:
...         assert time.monotonic() < deadline, 'system clock did not reach the target'
...         time.sleep(0.02)
...     check(frame, past, pl.Boolean, [False, False])
...     check(frame, future, pl.Boolean, [True, False])
...     check(frame, pl.col('event').pldt.is_past(), pl.Boolean, [True, False])
...     check(frame, pl.col('event').pldt.is_future(), pl.Boolean, [False, False])
...     return (frame.select(past).item(0, 0), frame.select(future).item(0, 0), frame.select(pl.col('event').pldt.is_past()).item(0, 0), frame.select(pl.col('event').pldt.is_future()).item(0, 0))
>>> demonstrate_snapshot()
(False, True, True, False)
```

For naive dates the comparison also needs a valid process-local timezone.
Use explicit aware input when that local interpretation is not intended.
