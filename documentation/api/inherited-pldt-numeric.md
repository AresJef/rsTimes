# Native numerical operations on a date Series

Inherited Polars names do not all have the same date role. Many numeric
operations reject Datetime. Some work on physical ticks and return Float64,
and date-aware cumulative operations return native date Series. Their behavior
is distinct from rsTimes calendar transformations and elapsed differences.

The rejected calls below were independently checked on ordinary Polars Series
before being executed on Pldt. They supply valid numeric parameters; the
expected failure is the receiver's date dtype, rather than a missing argument.
The [Polars Series reference](https://docs.pola.rs/api/python/stable/reference/series/index.html)
provides the complete native parameter reference.

## Explicit date-dtype rejections

Every method named in these tables is called on an actual Pldt. Native
InvalidOperationError, SchemaError and TypeError remain distinct. In particular,
native `floor`, `ceil`, `round` and `truncate` are numerical operations; date
boundary operations are documented through the rsTimes namespace.

```{doctest} inherited-pldt-numeric-rejections
>>> import math
>>> from datetime import datetime
>>> import polars as pl
>>> from rstimes import Pldt
>>> value = Pldt(pl.Series('event', [1704067200000000000, 1704153600000000123, None], dtype=pl.Datetime('ns', 'UTC')))
>>> def error_name(call):
...     try:
...         call()
...     except Exception as error:
...         return type(error).__name__
...     raise AssertionError('a dtype rejection was required')
>>> invalid_no_argument = (
...     '__abs__', '__neg__', '__invert__', 'abs',
...     'arccos', 'arccosh', 'arcsin', 'arcsinh', 'arctan', 'arctanh',
...     'bitwise_and', 'bitwise_or', 'bitwise_xor', 'bitwise_count_ones',
...     'bitwise_count_zeros', 'bitwise_leading_ones', 'bitwise_leading_zeros',
...     'bitwise_trailing_ones', 'bitwise_trailing_zeros',
...     'ceil', 'cos', 'cosh', 'cot', 'cum_prod', 'cum_sum', 'degrees',
...     'entropy', 'erf', 'erfc', 'exp', 'floor', 'is_finite', 'is_infinite',
...     'is_nan', 'is_not_nan', 'log', 'log10', 'log1p', 'not_', 'product',
...     'radians', 'round', 'sign', 'sin', 'sinh', 'std', 'sum', 'tan', 'tanh',
...     'truncate', 'var',
... )
>>> for method in invalid_no_argument:
...     assert error_name(lambda: getattr(value, method)()) == 'InvalidOperationError'
>>> for method in ('__and__', '__or__', '__xor__', '__pow__', '__rpow__', 'pow'):
...     assert error_name(lambda: getattr(value, method)(2)) == 'InvalidOperationError'
>>> for method in ('__rand__', '__ror__', '__rxor__'):
...     assert error_name(lambda: getattr(value, method)(2)) == 'SchemaError'
>>> for method in ('__truediv__', '__rtruediv__', '__floordiv__', '__rfloordiv__', '__mod__', '__rmod__', '__mul__', '__rmul__'):
...     assert error_name(lambda: getattr(value, method)(2)) == 'TypeError'
>>> (error_name(value.all), error_name(value.any))
('SchemaError', 'SchemaError')
>>> error_name(lambda: value.round_sig_figs(3))
'InvalidOperationError'
>>> error_name(lambda: value.reinterpret(signed=True))
'InvalidOperationError'
>>> numbers = pl.Series('numbers', [1, 2, 3])
>>> (error_name(lambda: value.dot(numbers)), error_name(lambda: value.__matmul__(numbers)))
('InvalidOperationError', 'InvalidOperationError')
>>> value.to_physical().to_list()
[1704067200000000000, 1704153600000000123, None]
```

Calling `reinterpret()` with neither `signed` nor `dtype` is a different
argument error. The example above explicitly supplies `signed=True`, so it
checks the real nonnumeric-dtype restriction. Native `std` does not produce a
Timedelta for Pldt; the inherited pandas/Pddt reduction has different behavior.

## Unary plus, cumulative extrema and storage bounds

Unary plus returns Pldt with unchanged dates. `cum_max`, `cum_min` and
`shrink_dtype` return ordinary native Series in these verified calls. Cumulative
state continues across a null, while the output at that null remains null.
`lower_bound` and `upper_bound` return a one-element Int64 Series containing
the physical storage bounds, not a Datetime result with an attached unit.

```{doctest} inherited-pldt-native-date-extrema
>>> unchanged = +value
>>> (type(unchanged) is Pldt, unchanged.dtype == value.dtype, unchanged.to_physical().to_list())
(True, True, [1704067200000000000, 1704153600000000123, None])
>>> ordered = Pldt(pl.Series('event', [8, None, 1], dtype=pl.Datetime('ns', 'UTC')))
>>> for method, expected in [('cum_max', [8, None, 8]), ('cum_min', [8, None, 1]), ('shrink_dtype', [8, None, 1])]:
...     result = getattr(ordered, method)()
...     assert type(result) is pl.Series and result.dtype == ordered.dtype and result.name == 'event'
...     assert result.to_physical().to_list() == expected
>>> for method, expected in [('lower_bound', -9223372036854775808), ('upper_bound', 9223372036854775807)]:
...     result = getattr(value, method)()
...     assert type(result) is pl.Series and result.dtype == pl.Int64 and result.name == 'event'
...     assert result.to_list() == [expected]
>>> for method, expected in [('nan_min', '2024-01-01T00:00:00+00:00'), ('nan_max', '2024-01-02T00:00:00+00:00')]:
...     result = getattr(value, method)()
...     assert type(result) is datetime and result.isoformat() == expected
>>> neighbors = Pldt(pl.Series('event', [1, 8, 2], dtype=pl.Datetime('ns', 'UTC')))
>>> for method, expected in [('peak_max', [False, True, False]), ('peak_min', [False, False, False])]:
...     result = getattr(neighbors, method)()
...     assert type(result) is pl.Series and result.dtype == pl.Boolean and result.to_list() == expected
```

```{doctest} inherited-pldt-native-peak-boundaries
>>> valley = Pldt(pl.Series('event', [8, 1, 9], dtype=pl.Datetime('ns', 'UTC')))
>>> valley.peak_min().to_list()
[False, True, False]
>>> missing_neighbor = Pldt(pl.Series('event', [1, 8, None], dtype=pl.Datetime('ns', 'UTC')))
>>> (missing_neighbor.peak_max().to_list(), missing_neighbor.peak_min().to_list())
([False, None, None], [False, False, None])
```

Native scalar extrema return standard datetime with microsecond precision; the
123 ns tail in the maximum is deliberately absent at this scalar exit. Native
peak predicates have provider-specific boundary rules; do not infer a null
just because the row is at an endpoint. A missing data neighbor can produce
a null result, as verified below.

## Numerical kernels that accept physical date ticks

The following native kernels accept Datetime by treating its storage as
numbers. They do not perform calendar square roots, calendar cube roots, or
unit-independent date percentages. Float64 output has no timezone metadata and
can lose integer precision for large epoch ticks. The small ns ticks below make
the independent numerical answers explicit.

```{doctest} inherited-pldt-physical-numerical-kernels
>>> small = Pldt(pl.Series('event', [1, 8, None], dtype=pl.Datetime('ns', 'UTC')))
>>> for method, expected in [('sqrt', [1.0, math.sqrt(8.0), None]), ('cbrt', [1.0, 2.0, None]), ('pct_change', [None, 7.0, None])]:
...     result = getattr(small, method)()
...     assert type(result) is pl.Series and result.dtype == pl.Float64 and result.name == 'event' and len(result) == len(expected)
...     for actual, wanted in zip(result.to_list(), expected):
...         assert actual is None if wanted is None else math.isclose(actual, wanted, rel_tol=1e-15)
>>> (type(small.skew()) is float, math.isclose(small.skew(), 0.0, abs_tol=1e-15), small.kurtosis())
(True, True, -2.0)
>>> same_instant_ns = Pldt(pl.Series('event', [1000000000], dtype=pl.Datetime('ns', 'UTC')))
>>> same_instant_us = Pldt(pl.Series('event', [1000000], dtype=pl.Datetime('us', 'UTC')))
>>> (math.isclose(same_instant_ns.sqrt().item(), math.sqrt(1000000000), rel_tol=1e-15), same_instant_us.sqrt().item())
(True, 1000.0)
```

Both final inputs represent one second after the epoch, but their native square
roots differ because the stored tick units differ. For a numeric measurement,
convert to the desired elapsed unit explicitly and keep the original dates.

## Exponential weighting: numerical output and time-index restrictions

The ordinary native `ewm_*` kernels below accept date storage and return
Float64 tick statistics. With alpha 1/2, the two observed values 1 and 8 have
adjusted mean 17/3, exponentially weighted sum 8.5, and unbiased variance 24.5.
The output at a null stays null. `ignore_nulls` changes how a gap decays prior
weights.

By contrast, `ewm_mean_by` and `ewm_sum_by` require a numerical value Series
alongside their time index, and reject the Datetime value Series. Supplying a
valid Datetime `by` column does not change that value-dtype restriction.

```{doctest} inherited-pldt-exponential-tick-statistics
>>> expected_ewm = {
...     'ewm_mean': [1.0, 17.0 / 3.0, None], 'ewm_sum': [1.0, 8.5, None],
...     'ewm_var': [None, 24.5, None], 'ewm_std': [None, math.sqrt(24.5), None],
... }
>>> for method, expected in expected_ewm.items():
...     result = getattr(small, method)(alpha=0.5)
...     assert type(result) is pl.Series and result.dtype == pl.Float64 and result.name == 'event' and len(result) == len(expected)
...     for actual, wanted in zip(result.to_list(), expected):
...         assert actual is None if wanted is None else math.isclose(actual, wanted, rel_tol=1e-15)
>>> gap = Pldt(pl.Series('event', [1, None, 8], dtype=pl.Datetime('ns', 'UTC')))
>>> with_gap, ignoring_gap = gap.ewm_mean(alpha=0.5).to_list(), gap.ewm_mean(alpha=0.5, ignore_nulls=True).to_list()
>>> (with_gap[:2], ignoring_gap[:2], math.isclose(with_gap[2], 33 / 5, rel_tol=1e-15), math.isclose(ignoring_gap[2], 17 / 3, rel_tol=1e-15))
([1.0, None], [1.0, None], True, True)
>>> clock = pl.Series('clock', [0, 1, 2], dtype=pl.Datetime('ns', 'UTC'))
>>> for method in ('ewm_mean_by', 'ewm_sum_by'):
...     assert error_name(lambda: getattr(small, method)(clock, half_life='1ns')) == 'InvalidOperationError'
```
