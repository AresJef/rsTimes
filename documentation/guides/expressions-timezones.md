# Localize and convert timezone expressions

An Expr keeps a native Datetime unit and one native timezone. Attachment,
conversion, removal and switching have distinct roles. Each successful example
below executes select, collect and streaming against independent physical
integer answers. Custom ZoneInfo target overrides have a separately disclosed
[known product defect](../compatibility/known-issues.md).

## Attachment, instant conversion, and removal

```{doctest} expr-timezone-operation-roles
>>> from datetime import timedelta
>>> import os, subprocess, sys
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt
>>> def tick(text):
...     return int(np.datetime64(text, 'ns').astype(np.int64))
>>> def check(frame, expression, dtype, values):
...     assert isinstance(expression, pl.Expr)
...     expression = expression.alias('result')
...     query = frame.lazy().select(expression)
...     assert query.collect_schema() == {'result': dtype}
...     for result in (frame.select(expression), query.collect(), query.collect(engine='streaming')):
...         assert result.schema == {'result': dtype} and type(result['result']) is pl.Series
...         assert result['result'].to_physical().to_list() == values
>>> wall = pl.DataFrame({'event': pl.Series([28800000000123, None], dtype=pl.Datetime('ns'))})
>>> aware = pl.DataFrame({'event': pl.Series([123, None], dtype=pl.Datetime('ns', 'Asia/Shanghai'))})
>>> check(wall, pl.col('event').pldt.tz_localize('Asia/Shanghai'), pl.Datetime('ns', 'Asia/Shanghai'), [123, None])
>>> check(aware, pl.col('event').pldt.tz_convert('UTC'), pl.Datetime('ns', 'UTC'), [123, None])
>>> check(aware, pl.col('event').pldt.astimezone('UTC'), pl.Datetime('ns', 'UTC'), [123, None])
>>> check(aware, pl.col('event').pldt.tz_localize(None), pl.Datetime('ns'), [28800000000123, None])
>>> check(aware, pl.col('event').pldt.tz_convert(None), pl.Datetime('ns'), [123, None])
>>> check(aware, pl.col('event').pldt.tz_switch(None), pl.Datetime('ns'), [28800000000123, None])
>>> check(wall, pl.col('event').pldt.tz_switch('UTC', base_tz='Asia/Shanghai', naive=True), pl.Datetime('ns'), [123, None])
```

Removing a zone with localize/switch retains the wall clock. Convert(None)
retains the instant in naive UTC coordinates. A nonempty switch target needs
`base_tz` for a naive source. `astimezone(None)` selects the actual local zone.

## Full-position ambiguity masks and logical-order inference

Boolean choices select actual ordered candidates, independently of DST status.
Masks cover every original row, including null and nonrepeated rows. Inference
uses logical order across chunks; it does not sort or guess the input order.

```{doctest} expr-timezone-ambiguity-policies
>>> local = tick('2024-11-03T01:30:00.000000123')
>>> rows = pl.DataFrame({'event': pl.Series([None, local, tick('2024-11-03T02:30:00.000000123'), local], dtype=pl.Datetime('ns')), 'choice': [True, False, True, True]})
>>> expression = pl.col('event').pldt.tz_localize('America/New_York', ambiguous=pl.col('choice'))
>>> check(rows, expression, pl.Datetime('ns', 'America/New_York'), [None, tick('2024-11-03T06:30:00.000000123'), tick('2024-11-03T07:30:00.000000123'), tick('2024-11-03T05:30:00.000000123')])
>>> first = pl.Series('event', [tick('2024-11-03T00:30'), tick('2024-11-03T01:30')], dtype=pl.Datetime('ns'))
>>> second = pl.Series('event', [tick('2024-11-03T01:30'), tick('2024-11-03T02:30')], dtype=pl.Datetime('ns'))
>>> chunks = pl.concat([first, second], rechunk=False)
>>> chunks.n_chunks()
2
>>> check(pl.DataFrame(chunks), pl.col('event').pldt.tz_localize('America/New_York', ambiguous='infer'), pl.Datetime('ns', 'America/New_York'), [tick('2024-11-03T04:30'), tick('2024-11-03T05:30'), tick('2024-11-03T06:30'), tick('2024-11-03T07:30')])
>>> repeated = pl.DataFrame({'event': pl.Series([local, None], dtype=pl.Datetime('ns'))})
>>> check(repeated, pl.col('event').pldt.tz_localize('America/New_York', ambiguous='NaT'), pl.Datetime('ns', 'America/New_York'), [None, None])
>>> for zone, clock, offsets, dst in [('Europe/Warsaw', '1915-08-04T23:50', (5040, 3600), False), ('Europe/Kyiv', '1990-07-01T01:30', (14400, 10800), True)]:
...     frame = pl.DataFrame({'event': pl.Series([tick(clock), None], dtype=pl.Datetime('ns'))})
...     for choice, offset in zip((True, False), offsets):
...         expression = pl.col('event').pldt.tz_localize(zone, ambiguous=choice)
...         check(frame, expression, pl.Datetime('ns', zone), [tick(clock) - offset * 1000000000, None])
...         check(frame, expression.pldt.is_dst(), pl.Boolean, [dst, False])
```

## Gaps use real unit boundaries

`shift_forward` uses the first existing clock after the gap. `shift_backward`
uses the last representable tick before it at the current unit. A timedelta
moves the requested local clock and still must land on a legal time. A NaT
policy creates native nulls and does not hide unrelated parse failures.

```{doctest} expr-timezone-gap-policies
>>> for unit, quantum in [('ms', 1000000), ('us', 1000), ('ns', 1)]:
...     frame = pl.DataFrame({'event': pl.Series([tick('2024-03-10T02:30') // quantum, None], dtype=pl.Datetime(unit))})
...     for policy, expected in [('shift_forward', tick('2024-03-10T07:00') // quantum), ('shift_backward', tick('2024-03-10T07:00') // quantum - 1), (timedelta(hours=1), tick('2024-03-10T07:30') // quantum), ('NaT', None)]:
...         expression = pl.col('event').pldt.tz_localize('America/New_York', nonexistent=policy)
...         check(frame, expression, pl.Datetime(unit, 'America/New_York'), [expected, None])
>>> for zone, clock, expected in [('Australia/Lord_Howe', '2024-10-06T02:15', '2024-10-05T15:30'), ('Pacific/Apia', '2011-12-30T12:30', '2011-12-30T10:00')]:
...     frame = pl.DataFrame({'event': pl.Series([tick(clock), None], dtype=pl.Datetime('ns'))})
...     check(frame, pl.col('event').pldt.tz_localize(zone, nonexistent='shift_forward'), pl.Datetime('ns', zone), [tick(expected), None])
```

## Offset and DST row queries

Offset seconds use Int64 with null at a naive date or source null. DST is a
Boolean query with False at null. A legal nonzero adjustment includes negative
DST; it is not simply a test that an offset increased. These values use the
native backend timezone database, which can differ from a host's ZoneInfo
database for historical or recently revised rules.

```{doctest} expr-timezone-row-queries
>>> values = [tick('2024-01-15T12:00'), tick('2024-07-15T12:00'), None]
>>> for zone, offsets, dst in [(None, [None, None, None], [False, False, False]), ('UTC', [0, 0, None], [False, False, False]), ('America/New_York', [-18000, -14400, None], [False, True, False]), ('Europe/Dublin', [0, 3600, None], [True, False, False])]:
...     frame = pl.DataFrame({'event': pl.Series(values, dtype=pl.Datetime('ns', zone))})
...     check(frame, pl.col('event').pldt.utcoffset_seconds(), pl.Int64, offsets)
...     check(frame, pl.col('event').pldt.is_dst(), pl.Boolean, dst)
```

## Errors and an isolated local-zone default

Schema/value errors occur in Polars execution. Static unsupported policy types
are rejected when an Expr is built. The final child-process example exercises
the actual local-zone default without changing this process's zone cache.

```{doctest} expr-timezone-errors-and-local-default
>>> for frame, expression in [(wall, pl.col('event').pldt.tz_convert('UTC')), (aware, pl.col('event').pldt.tz_localize('UTC')), (wall, pl.col('event').pldt.tz_switch('UTC'))]:
...     for execute in (lambda: frame.select(expression), lambda: frame.lazy().select(expression).collect()):
...         try:
...             execute()
...         except pl.exceptions.PolarsError:
...             continue
...         raise AssertionError('invalid timezone role succeeded')
>>> for build in (lambda: pl.col('event').pldt.tz_localize('UTC', ambiguous=1), lambda: pl.col('event').pldt.tz_localize('UTC', nonexistent=['NaT'])):
...     try:
...         build()
...     except TypeError:
...         continue
...     raise AssertionError('unsupported static policy type succeeded')
>>> program = '\n'.join([
...     'import polars as pl',
...     'from rstimes import Pldt',
...     "frame = pl.DataFrame({'event': pl.Series([0, None], dtype=pl.Datetime('ns', 'UTC'))})",
...     "expression = pl.col('event').pldt.astimezone()",
...     'for result in (frame.select(expression), frame.lazy().select(expression).collect()):',
...     "    assert result.schema == {'event': pl.Datetime('ns', 'Asia/Shanghai')}",
...     "    assert result['event'].to_physical().to_list() == [0, None]",
... ])
>>> completed = subprocess.run([sys.executable, '-I', '-c', program], env=dict(os.environ, TZ='Asia/Shanghai'), capture_output=True, text=True, check=True, timeout=20)
>>> (completed.returncode, completed.stdout, completed.stderr)
(0, '', '')
```
