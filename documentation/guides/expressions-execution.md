# Logical rows, grouping, snapshots, and native serialization

Expr arguments belong to the current logical input domain. Scalar aggregates
broadcast; ordinary columns pair by position. Concrete companion vectors must
match that domain. The examples here execute real native select and collect,
including streaming, grouping and windows.

## Chunks, windows, and scalar aggregates

```{doctest} expr-logical-domain-window-and-group
>>> import io, pickle
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt, Delta, Configs
>>> def check(frame, expression, dtype, expected):
...     assert isinstance(expression, pl.Expr)
...     expression = expression.alias('result')
...     query = frame.lazy().select(expression)
...     assert query.collect_schema() == {'result': dtype}
...     for result in (frame.select(expression), query.collect(), query.collect(engine='streaming')):
...         assert result.schema == {'result': dtype} and type(result['result']) is pl.Series
...         assert result['result'].to_physical().to_list() == expected
>>> chunks = pl.concat([pl.Series('event', [0, 1000], dtype=pl.Datetime('ns')), pl.Series('event', [2000, None], dtype=pl.Datetime('ns'))], rechunk=False)
>>> frame = pl.DataFrame({'event': chunks, 'group': ['A', 'B', 'A', 'B'], 'count': [1, 2, 3, 4], 'target': [0, 0, 0, 0]})
>>> chunks.n_chunks()
2
>>> check(frame, pl.col('event').pldt.add_delta(Delta(nanoseconds=1)).over('group'), pl.Datetime('ns'), [1, 1001, 2001, None])
>>> check(frame, pl.col('event').pldt.to_day(pl.col('count').min()).over('group'), pl.Datetime('ns'), [86400000000000, 172800000001000, 86400000002000, None])
>>> check(frame, pl.col('event').pldt.diff(pl.col('target').min(), 'ns').over('group'), pl.Int64, [0, 1000, 2000, None])
>>> expression = pl.col('event').pldt.to_day(1)
>>> eager = frame.group_by('group').agg(expression).sort('group')
>>> lazy = frame.lazy().group_by('group').agg(expression).sort('group').collect()
>>> for result in (eager, lazy):
...     assert result.schema == {'group': pl.String, 'event': pl.List(pl.Datetime('ns'))}
...     assert result['event'].list.eval(pl.element().cast(pl.Int64)).to_list() == [[86400000000000, 86400000002000], [86400000001000, None]]
```

## Concrete vectors and filters

A prepared concrete Delta vector is not a label-indexed lookup. Filtering the
input first changes the number of logical rows and requires a matching vector.
Slicing the already computed result is a distinct operation and retains the
correct original row changes.

```{doctest} expr-concrete-vector-domain
>>> expression = pl.col('event').pldt.add_delta([Delta(nanoseconds=value) for value in (1, 2, 3, 4)])
>>> check(frame, expression, pl.Datetime('ns'), [1, 1002, 2003, None])
>>> sliced = frame.lazy().select(expression).slice(1, 2).collect(engine='streaming')
>>> (sliced.schema == {'event': pl.Datetime('ns')}, sliced['event'].to_physical().to_list())
(True, [1002, 2003])
>>> try:
...     frame.lazy().filter(pl.col('event').is_not_null()).select(expression).collect()
... except pl.exceptions.PolarsError as error:
...     print('length' in str(error).lower())
True
```

## Native snapshots and genuine business overrides

Concrete Delta rules are captured when an Expr is created. A later genuine
class-method edit affects new preparation and eager Python arithmetic, while
the already captured native rule remains unchanged. Dynamic Python callbacks
and an Object/Delta Expr are not silently executed as native date rules.

```{doctest} expr-rule-snapshot-and-dynamic-rejection
>>> class Rule(Delta):
...     pass
>>> rule = Rule(nanoseconds=1)
>>> frozen = pl.col('event').pldt.add_delta(rule)
>>> Rule.__radd__ = lambda self, other: 'new application arithmetic'
>>> check(frame, frozen, pl.Datetime('ns'), [1, 1001, 2001, None])
>>> Pldt([0], unit='ns') + rule
'new application arithmetic'
>>> for build in (lambda: pl.col('event').pldt.add_delta(rule), lambda: pl.col('event').pldt.add_delta(pl.col('change'))):
...     try:
...         build()
...     except TypeError:
...         continue
...     raise AssertionError('a dynamic Python rule was accepted as a concrete native rule')
```

## Default callbacks and configuration snapshot order

An Expr captures configuration before preparing a default callback. An eager
call reads live effective rules during its normal preparation. The following
real callback changes a month token while supplying a complete default date;
it runs once per preparation, rather than once per row or each collect.

```{doctest} expr-default-callback-snapshot-order
>>> config = Configs()
>>> calls = []
>>> class Reference(str):
...     def __str__(self):
...         calls.append('default')
...         config.set_month({'jan': 2})
...         return '14 Jan 2024'
>>> default = Reference('application reference')
>>> text = pl.DataFrame({'raw': ['12:30', None]})
>>> frozen = pl.col('raw').pldt.parse(unit='us', cfg=config, default=default)
>>> _ = config.set_month({'jan': 8})
>>> check(text, frozen, pl.Datetime('us'), [1705235400000000, None])
>>> calls
['default']
>>> eager = text['raw'].pldt.parse(unit='us', cfg=config, default=default)
>>> (eager.to_physical().to_list(), calls)
([1707913800000000, None], ['default', 'default'])
```

## Ordinary native Expr serialization

The result remains a Polars Expr and uses its native serialization protocol.
The installed plugin and captured date rules must remain available when it is
restored. This example serializes and executes its own Expr in one environment;
it does not promise portability of plugin paths or binary formats across
machines, versions or untrusted data.

```{doctest} expr-native-serialization
>>> expression = pl.col('event').pldt.add_delta(Delta(nanoseconds=1)).pldt.strftime('%S%.9f')
>>> restored = [pickle.loads(pickle.dumps(expression)), pl.Expr.deserialize(io.BytesIO(expression.meta.serialize()))]
>>> for value in restored:
...     assert type(value) is pl.Expr
...     for result in (frame.select(value), frame.lazy().select(value).collect()):
...         assert result.schema == {'event': pl.String}
...         assert result['event'].to_list() == ['00.000000001', '00.000001001', '00.000002001', None]
```

For a long-lived workflow, retain explicit source data, schema, configuration
and code, and recreate its queries against the intended installed release.
