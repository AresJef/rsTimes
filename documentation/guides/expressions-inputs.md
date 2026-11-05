# Parse and construct dates in native queries

An Expr method returns an ordinary `pl.Expr`; the result column appears only
when Polars executes the query. Each successful expression below runs through
both eager `select` and lazy `collect`, with schema and physical values checked.
The helper also runs the streaming engine. It does not use an eager Pldt result
as its expected answer.

## A common execution check

Alias selects the output column name. A collected result is an ordinary Series,
rather than Pldt. Native nulls remain independent of a valid minimum tick.

```{doctest} expr-input-execution-helper
>>> from datetime import date, datetime, time, timezone
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt, Configs
>>> def check_dates(frame, expression, dtype, ticks):
...     assert isinstance(expression, pl.Expr)
...     expression = expression.alias('result')
...     query = frame.lazy().select(expression)
...     assert query.collect_schema() == {'result': dtype}
...     for result in (frame.select(expression), query.collect(), query.collect(engine='streaming')):
...         column = result['result']
...         assert result.schema == {'result': dtype} and type(column) is pl.Series
...         assert column.to_physical().to_list() == ticks
>>> def check_polars_error(frame, expression, word):
...     for run in (lambda: frame.select(expression), lambda: frame.lazy().select(expression).collect()):
...         try:
...             run()
...         except pl.exceptions.PolarsError as error:
...             assert word.lower() in str(error).lower(), str(error)
...         else:
...             raise AssertionError('the invalid query executed successfully')
```

## String parsing needs a static unit

String data cannot supply a precision or zone to a schema-only query planner.
Choose `unit=` for String parsing and choose an explicit target `tz=` when
nonmissing source text contains aware dates. Native typed sources instead
supply their existing schema. Numeric generic parse inputs are already ticks;
numeric `fromseconds` inputs are seconds.

```{doctest} expr-parse-native-and-text
>>> text = pl.DataFrame({'raw': ['1970-01-01T00:00:00.000000123', None, 'NaT']})
>>> check_dates(text, pl.col('raw').pldt.parse(unit='ns'), pl.Datetime('ns'), [123, None, None])
>>> sources = [
...     (pl.Series('raw', [1, None], dtype=pl.Datetime('us', 'UTC')), pl.Datetime('us', 'UTC'), [1, None]),
...     (pl.Series('raw', [0, None], dtype=pl.Date), pl.Datetime('ms'), [0, None]),
...     (pl.Series('raw', [1, None], dtype=pl.Int64), pl.Datetime('ns'), [1, None]),
...     (pl.Series('raw', [1.0, float('nan')]), pl.Datetime('ns'), [1, None]),
...     (pl.Series('raw', [None], dtype=pl.Null), pl.Datetime('ms'), [None]),
...     (pl.Series('raw', [-2**63, None], dtype=pl.Datetime('ns')), pl.Datetime('ns'), [-2**63, None]),
... ]
>>> for column, dtype, ticks in sources:
...     check_dates(pl.DataFrame(column), pl.col('raw').pldt.parse(), dtype, ticks)
>>> numeric = pl.DataFrame({'raw': pl.Series([0, None], dtype=pl.Int64)})
>>> check_dates(numeric, pl.col('raw').pldt.parse(unit='us', tz='Asia/Shanghai'), pl.Datetime('us', 'Asia/Shanghai'), [0, None])
>>> naive = pl.DataFrame({'raw': pl.Series([0, None], dtype=pl.Datetime('us'))})
>>> check_dates(naive, pl.col('raw').pldt.parse(tz='Asia/Shanghai'), pl.Datetime('us', 'Asia/Shanghai'), [-28800000000, None])
>>> check_polars_error(text, pl.col('raw').pldt.parse(), 'unit')
>>> aware_text = pl.DataFrame({'raw': ['1970-01-01T05:30:00+05:30', None]})
>>> check_polars_error(aware_text, pl.col('raw').pldt.parse(unit='ns'), 'tz')
>>> check_dates(aware_text, pl.col('raw').pldt.parse(unit='ns', tz='UTC'), pl.Datetime('ns', 'UTC'), [0, None])
```

## Rules are captured at expression creation

An expression freezes its effective Configs rules and independent default.
Later mutations do not retarget an already constructed query. A fresh eager
call reads the current configuration. Registered source regions still need an
explicit Expr target timezone.

```{doctest} expr-parser-configuration-snapshot
>>> config = Configs()
>>> config.add_month('jan', 2)
True
>>> frame = pl.DataFrame({'raw': ['14 Jan 2024', None]})
>>> frozen = pl.col('raw').pldt.parse(unit='us', cfg=config)
>>> config.add_month('jan', 3)
True
>>> check_dates(frame, frozen, pl.Datetime('us'), [1707868800000000, None])
>>> frame['raw'].pldt.parse(cfg=config).month.to_list()
[3, None]
>>> region = Configs()
>>> region.add_tzone('America/New_York')
True
>>> regional = pl.DataFrame({'raw': ['2024-01-01 12:00 America/New_York', None]})
>>> check_dates(regional, pl.col('raw').pldt.parse(unit='us', cfg=region, tz='UTC'), pl.Datetime('us', 'UTC'), [1704128400000000, None])
>>> default = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
>>> clock = pl.DataFrame({'raw': ['February 29', None]})
>>> check_dates(clock, pl.col('raw').pldt.parse(unit='us', default=default), pl.Datetime('us'), [1709164800000000, None])
```

## All four numeric factories

Numeric quantity and instant roles match the eager factories. `fromseconds`
and `frommicroseconds` interpret wall coordinates and attach a target zone.
`fromtimestamp` and `utcfromtimestamp` represent instants. Floating seconds need
an explicit output unit for Expr schema planning. Boolean numeric inputs remain
invalid.

```{doctest} expr-numeric-date-factories
>>> seconds = pl.DataFrame({'raw': [0, 1, None]})
>>> micros = pl.DataFrame({'raw': [0, 1000000, None]})
>>> for unit, scale in [('ms', 1000), ('us', 1000000), ('ns', 1000000000)]:
...     for method in ('fromseconds', 'frommicroseconds', 'fromtimestamp', 'utcfromtimestamp'):
...         options = {'unit': unit}
...         if method != 'utcfromtimestamp':
...             options['tz'] = 'UTC'
...         expression = getattr(pl.col('raw').pldt, method)(**options)
...         check_dates(micros if method == 'frommicroseconds' else seconds, expression, pl.Datetime(unit, 'UTC'), [0, scale, None])
>>> zero = pl.DataFrame({'raw': [0, None]})
>>> check_dates(zero, pl.col('raw').pldt.fromseconds(unit='ns', tz='Asia/Shanghai'), pl.Datetime('ns', 'Asia/Shanghai'), [-28800000000000, None])
>>> check_dates(zero, pl.col('raw').pldt.fromtimestamp(unit='ns', tz='Asia/Shanghai'), pl.Datetime('ns', 'Asia/Shanghai'), [0, None])
>>> fractions = pl.DataFrame({'raw': [1e-9, -1e-9, None]})
>>> check_dates(fractions, pl.col('raw').pldt.fromseconds(unit='ns'), pl.Datetime('ns'), [1, -1, None])
>>> check_polars_error(fractions, pl.col('raw').pldt.fromseconds(), 'unit')
>>> check_polars_error(pl.DataFrame({'raw': [True]}), pl.col('raw').pldt.fromseconds(unit='ns'), 'Boolean')
```

## Calendar coordinates and actual date schemas

Year/week/day components can be scalar expressions or row columns. Source nulls
and explicit missing components propagate. Numeric and text data cannot enter
the specialized actual Date/Datetime factories. Calendar factories default to
microseconds; ISO and day-of-year convenience upper selection follows the
same rules as their eager counterparts.

```{doctest} expr-calendar-and-date-factories
>>> ordinals = pl.DataFrame({'raw': [738945, None, 0]})
>>> check_dates(ordinals, pl.col('raw').pldt.fromordinal(), pl.Datetime('us'), [1709164800000000, None, -62135683200000000])
>>> iso = pl.DataFrame({'year': [2024, 2015, None], 'week': [9, 53, 1], 'weekday': [4, 4, 1]})
>>> check_dates(iso, pl.col('year').pldt.fromisocalendar(pl.col('week'), pl.col('weekday')), pl.Datetime('us'), [1709164800000000, 1451520000000000, None])
>>> years = pl.DataFrame({'year': [2024, 2023, None], 'doy': [60, 60, 1]})
>>> check_dates(years, pl.col('year').pldt.fromdayofyear(pl.col('doy')), pl.Datetime('us'), [1709164800000000, 1677628800000000, None])
>>> check_dates(years, pl.col('year').max().pldt.fromdayofyear(1), pl.Datetime('us'), [1704067200000000])
>>> native = pl.DataFrame({'raw': pl.Series([123, None], dtype=pl.Datetime('ns', 'UTC'))})
>>> check_dates(native, pl.col('raw').pldt.fromdate(unit='ns'), pl.Datetime('ns'), [0, None])
>>> check_dates(native, pl.col('raw').pldt.fromdatetime(), pl.Datetime('ns', 'UTC'), [123, None])
>>> check_dates(native, pl.col('raw').pldt.fromdatetime(tz='Asia/Shanghai'), pl.Datetime('ns', 'Asia/Shanghai'), [-28799999999877, None])
>>> check_polars_error(pl.DataFrame({'raw': ['2024-01-01']}), pl.col('raw').pldt.fromdate(), 'Date')
```

## ISO, explicit formats, and combined clocks

Generic parse, ISO-only input and explicit-format parsing remain distinct.
`strptime` with `%f` needs an explicit unit at expression creation; an explicit
coarser formatted output truncates once at that boundary. A format with a
timezone directive needs an explicit target. A Time/Datetime(ns)/String clock
Expr in `combine` also needs a unit. Concrete clock values can supply known
metadata and are captured before later list edits.

```{doctest} expr-iso-format-and-combine
>>> iso_text = pl.DataFrame({'raw': ['1970-01-01T00:00:00.123456789', None]})
>>> check_dates(iso_text, pl.col('raw').pldt.fromisoformat(unit='ns'), pl.Datetime('ns'), [123456789, None])
>>> formatted = pl.DataFrame({'raw': ['1970-01-01 00:00:00.123456789', None]})
>>> for unit, tick in [('us', 123456), ('ns', 123456789)]:
...     check_dates(formatted, pl.col('raw').pldt.strptime('%Y-%m-%d %H:%M:%S.%f', unit=unit), pl.Datetime(unit), [tick, None])
>>> for action in (lambda: pl.col('raw').pldt.strptime('%Y-%m-%d %H:%M:%S.%f'), lambda: pl.col('raw').pldt.strptime('%Y-%m-%d%z', unit='us')):
...     try:
...         action()
...     except ValueError:
...         continue
...     raise AssertionError('dynamic output schema was accepted')
>>> frame = pl.DataFrame({'day': [date(2024, 1, 2), date(2024, 1, 3)], 'clock': pl.Series([1, None], dtype=pl.Time)})
>>> check_dates(frame, pl.col('day').pldt.combine(pl.col('clock'), unit='ns'), pl.Datetime('ns'), [1704153600000000001, None])
>>> check_polars_error(frame, pl.col('day').pldt.combine(pl.col('clock')), 'unit')
>>> clocks = [time(12), None]
>>> frozen = pl.col('day').pldt.combine(clocks)
>>> clocks[0] = time(1)
>>> check_dates(frame, frozen, pl.Datetime('us'), [1704196800000000, None])
```

Schema- and row-dependent failures use Polars exception classes at execution.
Option-preparation failures can happen while the Expr is built. Both phases
must be handled; constructing an Expr alone does not establish success.
