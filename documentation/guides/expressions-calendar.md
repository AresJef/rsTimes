# Calendar transformations in Expr and LazyFrame

Use `.pldt` on a native Expr for calendar operations. Each expression below
executes in select, collect and streaming with a fixed expected schema and
independent literal date or integer answers. Collected columns are ordinary
Polars Series; no Python row callback simulates the date calculation.

## Execute every calendar selector

This table shares the literal Gregorian answers used in the eager guide. It
does not read the output of an eager product call. The source is a native
Datetime(ns, UTC) column with an exact fraction and a null second row.

```{doctest} expr-calendar-selectors
>>> from datetime import timedelta
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt, Delta
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
>>> def check_error(frame, expression, word):
...     for execute in (lambda: frame.select(expression), lambda: frame.lazy().select(expression).collect()):
...         try:
...             execute()
...         except pl.exceptions.PolarsError as error:
...             assert word.lower() in str(error).lower(), str(error)
...         else:
...             raise AssertionError('invalid query succeeded')
>>> frame = pl.DataFrame({'event': pl.Series([tick('2024-01-31T12:34:56.123456789'), None], dtype=pl.Datetime('ns', 'UTC'))})
>>> selectors = [
...     ('to_year', (1,), {}, '2025-01-31'),
...     ('to_curr_year', (), {'month': 'February', 'day': 31}, '2024-02-29'),
...     ('to_prev_year', (), {'month': 'February', 'day': 31}, '2023-02-28'),
...     ('to_next_year', (), {'month': 'February', 'day': 31}, '2025-02-28'),
...     ('to_quarter', (1,), {}, '2024-04-30'),
...     ('to_curr_quarter', (), {'month': 3, 'day': 31}, '2024-03-31'),
...     ('to_prev_quarter', (), {'month': 2, 'day': 31}, '2023-11-30'),
...     ('to_next_quarter', (), {'month': 2, 'day': 31}, '2024-05-31'),
...     ('to_month', (1,), {}, '2024-02-29'),
...     ('to_curr_month', (), {'day': 1}, '2024-01-01'),
...     ('to_prev_month', (), {'day': 1}, '2023-12-01'),
...     ('to_next_month', (), {'day': 1}, '2024-02-01'),
...     ('to_weekday', (1,), {'weekday': 'Monday'}, '2024-02-05'),
...     ('to_curr_weekday', (), {'weekday': 0}, '2024-01-29'),
...     ('to_prev_weekday', (), {'weekday': 'Monday'}, '2024-01-22'),
...     ('to_next_weekday', (), {'weekday': 'Monday'}, '2024-02-05'),
...     ('to_monday', (), {}, '2024-01-29'),
...     ('to_tuesday', (), {}, '2024-01-30'),
...     ('to_wednesday', (), {}, '2024-01-31'),
...     ('to_thursday', (), {}, '2024-02-01'),
...     ('to_friday', (), {}, '2024-02-02'),
...     ('to_saturday', (), {}, '2024-02-03'),
...     ('to_sunday', (), {}, '2024-02-04'),
...     ('to_day', (1,), {}, '2024-02-01'),
...     ('to_yesterday', (), {}, '2024-01-30'),
...     ('to_tomorrow', (), {}, '2024-02-01'),
... ]
>>> for method, args, options, expected in selectors:
...     expression = getattr(pl.col('event').pldt, method)(*args, **options)
...     check(frame, expression, pl.Datetime('ns', 'UTC'), [tick(expected + 'T12:34:56.123456789'), None])
```

Weekday numbers are Monday=0. Previous/next weekday methods choose that weekday
in the previous/next calendar week. Quarter month selectors are positions 1–3.

## Fitted fields, strict replacement, and optional None

`to_date`/`to_datetime` fit a legal day intent to the resulting month.
`.pldt.replace` requires a valid full date. Fields accept scalar or row Expr
arguments. Native null integer fields have the optional None meaning and
retain the old field. Missing relative counts instead remain invalid.

```{doctest} expr-calendar-fields-and-rows
>>> check(frame, pl.col('event').pldt.to_datetime(month=2, day=31, hour=0), pl.Datetime('ns', 'UTC'), [tick('2024-02-29T00:34:56.123456789'), None])
>>> check(frame, pl.col('event').pldt.to_date(month=2, day=31), pl.Datetime('ns', 'UTC'), [tick('2024-02-29T12:34:56.123456789'), None])
>>> check(frame, pl.col('event').pldt.to_time(hour=0, nanosecond=0), pl.Datetime('ns', 'UTC'), [tick('2024-01-31T00:34:56.123456000'), None])
>>> for fields, fraction in [({'microsecond': 1}, '000001000'), ({'nanosecond': 2}, '123456002'), ({'microsecond': 1, 'nanosecond': 2}, '000001002')]:
...     expression = pl.col('event').pldt.replace(**fields)
...     check(frame, expression, pl.Datetime('ns', 'UTC'), [tick('2024-01-31T12:34:56.' + fraction), None])
>>> check(frame, pl.col('event').pldt.replace(tzinfo=None), pl.Datetime('ns'), [tick('2024-01-31T12:34:56.123456789'), None])
>>> check_error(frame, pl.col('event').pldt.replace(month=2), 'day')
>>> rows = pl.DataFrame({'event': pl.Series([tick('2024-01-31'), tick('2025-03-31'), None], dtype=pl.Datetime('ns')), 'month': [2, 4, None], 'day': [31, 30, None], 'offset': [1, -1, 0]})
>>> check(rows, pl.col('event').pldt.to_date(month=pl.col('month'), day=pl.col('day')), pl.Datetime('ns'), [tick('2024-02-29'), tick('2025-04-30'), None])
>>> check(rows, pl.col('event').pldt.replace(day=pl.col('day')), pl.Datetime('ns'), [tick('2024-01-31'), tick('2025-03-30'), None])
>>> check(rows, pl.col('event').pldt.to_day(pl.col('offset').max()), pl.Datetime('ns'), [tick('2024-02-01'), tick('2025-04-01'), None])
>>> check_error(rows, pl.col('event').pldt.to_day(pl.col('offset').head(1)), 'length')
```

A scalar aggregate broadcasts. A non-scalar one-row column does not become a
scalar merely because its length is one. Pairing is positional, without an
index-alignment step.

## All relative components and explicit unit changes

The current storage unit stays fixed during date transformations. Relative
components combine before the final precision check, so exact cancellation is
legal. `as_unit` is the explicit unit-changing operation; `round_ok=False`
requires every actual date to fit exactly.

```{doctest} expr-calendar-relative-and-unit
>>> components = [
...     ('years', '2025-01-31T12:34:56.123456789'),
...     ('quarters', '2024-04-30T12:34:56.123456789'),
...     ('months', '2024-02-29T12:34:56.123456789'),
...     ('weeks', '2024-02-07T12:34:56.123456789'),
...     ('days', '2024-02-01T12:34:56.123456789'),
...     ('hours', '2024-01-31T13:34:56.123456789'),
...     ('minutes', '2024-01-31T12:35:56.123456789'),
...     ('seconds', '2024-01-31T12:34:57.123456789'),
...     ('milliseconds', '2024-01-31T12:34:56.124456789'),
...     ('microseconds', '2024-01-31T12:34:56.123457789'),
...     ('nanoseconds', '2024-01-31T12:34:56.123456790'),
... ]
>>> for field, answer in components:
...     for method, value in [('add', 1), ('sub', -1)]:
...         expression = getattr(pl.col('event').pldt, method)(**{field: value})
...         check(frame, expression, pl.Datetime('ns', 'UTC'), [tick(answer), None])
>>> units = [('ms', 1000), ('us', 1000000), ('ns', 1000000000)]
>>> for storage, scale in units:
...     column = pl.DataFrame({'event': pl.Series([-scale, scale, None], dtype=pl.Datetime(storage, 'UTC'))})
...     for target, target_scale in units:
...         check(column, pl.col('event').pldt.as_unit(target, round_ok=False), pl.Datetime(target, 'UTC'), [-target_scale, target_scale, None])
>>> coarse = pl.DataFrame({'event': pl.Series([0, None], dtype=pl.Datetime('us'))})
>>> check(coarse, pl.col('event').pldt.add(microseconds=1, nanoseconds=-1000), pl.Datetime('us'), [0, None])
>>> check_error(coarse, pl.col('event').pldt.add(nanoseconds=1), 'unit')
>>> check_error(coarse, pl.col('event').pldt.sub(nanoseconds=1), 'unit')
>>> check_error(frame, pl.col('event').pldt.to_date(year=2500), 'unit')
```

## Concrete Delta rules and vectors

Use `.pldt.add_delta`/`.pldt.sub_delta` rather than applying ordinary Polars
numeric operators to a Delta. Absolute fields keep their meaning on
subtraction; relative fields change direction. Concrete vectors are captured
at creation, retain full nanoseconds and require the logical input length.

```{doctest} expr-concrete-delta-rules
>>> changes = [
...     (Delta(months=1), '2024-02-29T12:34:56.123456789'),
...     (Delta(days=1), '2024-02-01T12:34:56.123456789'),
...     (Delta(day=1), '2024-01-01T12:34:56.123456789'),
...     (Delta(hour=0), '2024-01-31T00:34:56.123456789'),
...     (Delta(microseconds=1), '2024-01-31T12:34:56.123457789'),
...     (Delta(microseconds=.001), '2024-01-31T12:34:56.123456790'),
...     (Delta(nanoseconds=1), '2024-01-31T12:34:56.123456790'),
...     (Delta(millisecond=1), '2024-01-31T12:34:56.001000000'),
...     (Delta(microsecond=1), '2024-01-31T12:34:56.000001000'),
...     (Delta(microsecond=0), '2024-01-31T12:34:56.000000000'),
...     (Delta(nanosecond=2), '2024-01-31T12:34:56.123456002'),
...     (Delta(month=2, months=1, day=31), '2024-03-31T12:34:56.123456789'),
...     (Delta(weekday=0), '2024-01-29T12:34:56.123456789'),
... ]
>>> for change, answer in changes:
...     check(frame, pl.col('event').pldt.add_delta(change), pl.Datetime('ns', 'UTC'), [tick(answer), None])
>>> check(frame, pl.col('event').pldt.sub_delta(Delta(nanoseconds=1)), pl.Datetime('ns', 'UTC'), [tick('2024-01-31T12:34:56.123456788'), None])
>>> check(frame, pl.col('event').pldt.sub_delta(Delta(day=1)), pl.Datetime('ns', 'UTC'), [tick('2024-01-01T12:34:56.123456789'), None])
>>> dates = pl.DataFrame({'event': pl.Series([tick('2024-01-31'), tick('2024-02-29')], dtype=pl.Datetime('ns'))})
>>> changes = [Delta(months=1), Delta(months=2)]
>>> frozen = pl.col('event').pldt.add_delta(changes)
>>> changes[0] = Delta(days=1)
>>> check(dates, frozen, pl.Datetime('ns'), [tick('2024-02-29'), tick('2024-04-29')])
```

Dynamic Python business arithmetic is an eager protocol. Expr rejects such
rules instead of claiming to run an arbitrary Python override inside the native
kernel. Known custom-timezone product defects remain disclosed separately in
the [known-issues page](../compatibility/known-issues.md).
