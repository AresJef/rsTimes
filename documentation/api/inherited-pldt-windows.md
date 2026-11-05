# Native windows on an rsTimes date column

Pldt inherits native rolling and cumulative analysis methods. A row window
uses an integer `window_size`; a time window uses a `by` column and a duration
such as `'3s'`. These methods return ordinary native Series. Their statistical
units and numerical precision rules are separate from rsTimes calendar changes
and explicit date differences.

The following data is at 0, 2 and 4 seconds after the Unix epoch, stored in ns
with UTC metadata. This makes the mathematical window answers explicit.

## Row windows returning dates and ranks

The default fixed window needs two valid values when `window_size=2`.
The first result is therefore null. Mean and median return dates at the
window midpoint; min/max return extrema. Native quantile's default nearest
interpolation selects the upper of the two ordered values in this example.
Rank returns Float64, with a null before the full window is available.

```{doctest} inherited-pldt-native-row-windows
>>> import math
>>> import polars as pl
>>> from rstimes import Pldt
>>> ticks = [0, 2000000000, 4000000000]
>>> value = Pldt(pl.Series('event', ticks, dtype=pl.Datetime('ns', 'UTC')))
>>> def check_date(result, expected):
...     assert type(result) is pl.Series and result.name == 'event' and result.dtype == value.dtype
...     assert result.to_physical().to_list() == expected
>>> check_date(value.rolling_min(window_size=2), [None, 0, 2000000000])
>>> check_date(value.rolling_max(window_size=2), [None, 2000000000, 4000000000])
>>> check_date(value.rolling_mean(window_size=2), [None, 1000000000, 3000000000])
>>> check_date(value.rolling_median(window_size=2), [None, 1000000000, 3000000000])
>>> check_date(value.rolling_quantile(0.5, window_size=2), [None, 2000000000, 4000000000])
>>> ranked = value.rolling_rank(window_size=2)
>>> (type(ranked) is pl.Series, ranked.dtype, ranked.name, ranked.to_list())
(True, Float64, 'event', [None, 2.0, 2.0])
>>> nullable = Pldt(pl.Series('event', [0, None, 4000000000], dtype=value.dtype))
>>> check_date(nullable.rolling_min(window_size=2), [None, None, None])
>>> check_date(nullable.rolling_min(window_size=2, min_samples=1), [0, 0, 4000000000])
>>> check_date(value.clear().rolling_min(window_size=2), [])
```

`min_samples` counts non-null observations. It controls whether a result exists;
it does not fill a missing input date. A Datetime return dtype also does not
imply that a numerical statistical kernel is an exact-integer ns algorithm.
Use the explicit rsTimes difference and calendar interfaces for their stated
semantics and precision contracts.

## Time windows with a separate ordering column

The sorted date column below also supplies the `by` axis. With `closed='right'`
and a 3-second window, each row after the first includes the previous and
current dates. The default `min_samples=1` permits a first-row result.
The time axis and the date values are distinct parameter roles even when the
same column supplies both.

```{doctest} inherited-pldt-native-time-windows
>>> check_date(value.rolling_min_by(value, window_size='3s'), [0, 0, 2000000000])
>>> check_date(value.rolling_max_by(value, window_size='3s'), ticks)
>>> check_date(value.rolling_mean_by(value, window_size='3s'), [0, 1000000000, 3000000000])
>>> check_date(value.rolling_median_by(value, window_size='3s'), [0, 1000000000, 3000000000])
>>> check_date(value.rolling_quantile_by(value, window_size='3s', quantile=0.5), ticks)
>>> ranked = value.rolling_rank_by(value, window_size='3s')
>>> (type(ranked) is pl.Series, ranked.dtype, ranked.name, ranked.to_list())
(True, Float64, 'event', [1.0, 2.0, 2.0])
>>> value.to_physical().to_list() == ticks
True
```

## Statistical numerical outputs

For this ns date storage, native standard deviation is a Float64 value in
physical ns and variance is in ns squared. Neither result is a Duration Series.
With the default sample correction `ddof=1`, one observation is insufficient;
two observations separated by 2 seconds have variance `2e18` ns squared and
standard deviation `sqrt(2) * 1e9` ns. The checks use an explicit floating
comparison to those mathematical values.

```{doctest} inherited-pldt-native-window-statistics
>>> for result in [value.rolling_std(window_size=2), value.rolling_std_by(value, window_size='3s')]:
...     assert type(result) is pl.Series and result.dtype == pl.Float64 and result.name == 'event'
...     actual = result.to_list()
...     assert actual[0] is None and len(actual) == 3
...     assert all(math.isclose(x, math.sqrt(2) * 1000000000, rel_tol=1e-12) for x in actual[1:])
>>> for result in [value.rolling_var(window_size=2), value.rolling_var_by(value, window_size='3s')]:
...     assert type(result) is pl.Series and result.dtype == pl.Float64 and result.name == 'event'
...     actual = result.to_list()
...     assert actual[0] is None and len(actual) == 3
...     assert all(math.isclose(x, 2000000000000000000, rel_tol=1e-12) for x in actual[1:])
```

## Numerical-only operations and cumulative expressions

The inherited rolling sum, skew, kurtosis and custom rolling-map kernels below
reject this Datetime dtype. They do not choose an elapsed duration or a calendar
operation for you. If you intend numerical analysis of a duration, first
produce the appropriate duration or numerical column explicitly.

`cumulative_eval` actually executes its expression over expanding windows and
returns a materialized Series. The maximum of each growing prefix is the
current date in this ascending input.

```{doctest} inherited-pldt-native-window-boundaries
>>> def error_name(call):
...     try:
...         call()
...     except Exception as error:
...         return type(error).__name__
...     raise AssertionError('a dtype error was required')
>>> for name in ['rolling_kurtosis', 'rolling_skew', 'rolling_sum']:
...     assert error_name(lambda: getattr(value, name)(window_size=2)) == 'InvalidOperationError'
>>> error_name(lambda: value.rolling_map(lambda window: window.max(), window_size=2))
'InvalidOperationError'
>>> error_name(lambda: value.rolling_sum_by(value, window_size='3s'))
'InvalidOperationError'
>>> check_date(value.cumulative_eval(pl.element().max()), ticks)
>>> value.to_physical().to_list() == ticks
True
```

These are inherited provider operations; the
[native Series reference](https://docs.pola.rs/api/python/stable/reference/series/index.html)
defines their additional statistical options and stability labels. For
rsTimes workflows, continue with [date queries](../guides/pldt-queries.md),
[explicit differences](../guides/pldt-differences.md), or
[lazy date expressions](../guides/expressions.md).
