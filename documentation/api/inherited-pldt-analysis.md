# Native summaries, ordering and date analysis

Pldt inherits native Series analysis helpers. Scalar date reductions return
standard Python `datetime` values, whose fractional resolution is microseconds.
Native date Series results can retain the original ns unit and timezone.
Numerical summaries, row positions, categories and counts have their own
return types. The examples check these roles on an actual rsTimes date column.

## Scalar dates, counts and selected rows

Nulls do not enter the date mean, median or extrema. The three valid dates
below are January 3, January 1 and January 3; their mean is January 2 at 08:00
UTC. `n_unique` includes null as one distinct value. Approximate methods are
estimates in general; their small example results below are not a general
accuracy guarantee.

`min_by` and `max_by` select a date using another column's ordering. In these
calls they return Python datetime scalars. Do not infer an Expr result from a
provider annotation; no expression remains to collect here.

```{doctest} inherited-pldt-native-summaries
>>> from collections import Counter
>>> from datetime import datetime, timezone
>>> import polars as pl
>>> from rstimes import Pldt
>>> first, last = 1704067200000000123, 1704240000000000789
>>> ticks = [last, None, first, last]
>>> value = Pldt(pl.Series('event', ticks, dtype=pl.Datetime('ns', 'UTC')))
>>> expected = {
...     'min': datetime(2024, 1, 1, tzinfo=timezone.utc),
...     'max': datetime(2024, 1, 3, tzinfo=timezone.utc),
...     'mean': datetime(2024, 1, 2, 8, tzinfo=timezone.utc),
...     'median': datetime(2024, 1, 3, tzinfo=timezone.utc),
... }
>>> for name, answer in expected.items():
...     result = getattr(value, name)()
...     assert type(result) is datetime and result == answer and result.utcoffset().total_seconds() == 0
>>> for result in [value.quantile(0.5), value.approx_quantile(0.5)]:
...     assert type(result) is datetime and result == expected['median']
>>> (value.n_unique(), value.approx_n_unique(), value.arg_min(), value.arg_max())
(3, 3, 2, 0)
>>> all(type(x) is int for x in [value.n_unique(), value.approx_n_unique(), value.arg_min(), value.arg_max()])
True
>>> priority = pl.Series('priority', [2, 1, 3, 0])
>>> chosen = [value.min_by(priority), value.max_by(priority)]
>>> (all(type(x) is datetime for x in chosen), chosen == [expected['max'], expected['min']])
(True, True)
>>> (value.clear().min(), value.clear().max(), value.clear().mean(), value.clear().median())
(None, None, None, None)
```

## Distinct values, counts and row ordering

`mode`, `unique`, top/bottom selection and rank return ordinary native Series.
`unique(maintain_order=True)` uses first occurrence order. Top/bottom selection
does not promise sorted output, so its result is checked as a multiset.
`arg_sort` returns row positions; a rank is a row value, not a position.

```{doctest} inherited-pldt-native-ordering
>>> def date_result(result, expected_ticks):
...     assert type(result) is pl.Series and result.name == 'event' and result.dtype == value.dtype
...     assert result.to_physical().to_list() == expected_ticks
>>> date_result(value.mode(), [last])
>>> date_result(value.unique(maintain_order=True), [last, None, first])
>>> counts = value.unique_counts()
>>> (type(counts) is pl.Series, counts.dtype, counts.to_list())
(True, UInt32, [2, 1, 1])
>>> frequencies = value.value_counts()
>>> (type(frequencies) is pl.DataFrame, frequencies.schema == {'event': value.dtype, 'count': pl.UInt32})
(True, True)
>>> dict(zip(frequencies['event'].to_physical().to_list(), frequencies['count'].to_list())) == {last: 2, None: 1, first: 1}
True
>>> positions = value.arg_sort(nulls_last=True)
>>> (type(positions) is pl.Series, positions.dtype == pl.get_index_type(), positions.to_list())
(True, True, [2, 0, 3, 1])
>>> average_rank, dense_rank = value.rank(), value.rank(method='dense')
>>> (type(average_rank) is pl.Series, average_rank.dtype, average_rank.to_list())
(True, Float64, [2.5, None, 1.0, 2.5])
>>> (type(dense_rank) is pl.Series, dense_rank.dtype, dense_rank.to_list())
(True, UInt32, [2, None, 1, 2])
>>> for result, answer in [(value.top_k(2), [last, last]), (value.bottom_k(2), [first, last]), (value.top_k_by(priority, 2), [first, last]), (value.bottom_k_by(priority, 2), [last, None])]:
...     assert type(result) is pl.Series and result.dtype == value.dtype and result.name == 'event'
...     assert Counter(result.to_physical().to_list()) == Counter(answer)
```

Scalar lookup matches the value you supply. Standard datetime has microsecond
resolution; use it on the explicit microsecond column below. `index_of`
returns an integer position or None. `search_sorted` requires sorted data;
vector input produces a native index Series, while scalar input produces int.

```{doctest} inherited-pldt-native-search
>>> microseconds = Pldt(pl.Series('event', [0, 2000000, 4000000, None], dtype=pl.Datetime('us', 'UTC')))
>>> sought = datetime(1970, 1, 1, 0, 0, 2, tzinfo=timezone.utc)
>>> (microseconds.index_of(sought), microseconds.index_of(datetime(2000, 1, 1, tzinfo=timezone.utc)))
(1, None)
>>> type(microseconds.index_of(sought)) is int
True
>>> sorted_dates = microseconds.drop_nulls().sort()
>>> needles = pl.Series('needle', [1000000, 5000000], dtype=microseconds.dtype)
>>> positions = sorted_dates.search_sorted(needles)
>>> (type(positions) is pl.Series, positions.dtype == pl.get_index_type(), positions.to_list())
(True, True, [1, 3])
>>> (type(sorted_dates.search_sorted(sought)) is int, sorted_dates.search_sorted(sought))
(True, 1)
```

## Date categories and numeric-only boundaries

`bin_intervals` accepts actual date breakpoints. `bin_ranks` groups sorted
positions and can split equal values across bins. `bin_quantiles` requires
numeric input; `hist` also requires numerical data. They reject this date
column rather than choosing elapsed or calendar units for you.

The inherited `cut` and `qcut` compatibility methods are deprecated in the
verified native provider. Their small example uses physical microsecond
breakpoints and explicit labels. Prefer date breakpoints with `bin_intervals`
for new date-category code.

```{doctest} inherited-pldt-native-binning
>>> boundary = datetime(1970, 1, 1, 0, 0, 2, tzinfo=timezone.utc)
>>> bins = microseconds.bin_intervals([boundary], labels=['early', 'late'])
>>> (type(bins) is pl.Series, bins.dtype == pl.Enum(['early', 'late']), bins.to_list())
(True, True, ['early', 'late', 'late', None])
>>> rank_bins = microseconds.bin_ranks(2, labels=False)
>>> (type(rank_bins) is pl.Series, rank_bins.dtype, rank_bins.to_list())
(True, UInt32, [0, 0, 1, None])
>>> def error_name(call):
...     try:
...         call()
...     except Exception as error:
...         return type(error).__name__
...     raise AssertionError('an error was required')
>>> error_name(lambda: microseconds.bin_quantiles([0.5], labels=['early', 'late']))
'InvalidOperationError'
>>> error_name(lambda: microseconds.hist(bin_count=2))
'InvalidOperationError'
>>> for result in [microseconds.cut([2000000.0], labels=['early', 'late']), microseconds.qcut([0.5], labels=['early', 'late'])]:
...     assert type(result) is pl.Series and result.dtype.base_type() in (pl.Enum, pl.Categorical)
...     assert result.to_list() == ['early', 'early', 'late', None]
```

## Run lengths, row differences and Python callbacks

`rle` returns a Struct Series of run lengths and date values. Its date storage
retains ns and independent nulls; `rle_id` returns an integer run identifier
for each original row.

Native `diff` subtracts adjacent rows and returns Duration, including nulls
introduced by shifting. It differs from rsTimes `.pldt.diff(other, unit=...)`,
which compares another target with explicit elapsed/calendar choices.

`map_elements` invokes Python on scalar cells. It is an escape hatch for
business callbacks, with standard Python datetime precision and native Series
return rules. Prefer rsTimes date operations or expressions for operations
they already provide. Specify the callback's return dtype.

```{doctest} inherited-pldt-native-runs-and-callbacks
>>> runs = Pldt(pl.Series('event', [first, first, None, None, last], dtype=value.dtype))
>>> encoded = runs.rle()
>>> (type(encoded) is pl.Series, encoded.dtype == pl.Struct({'len': pl.UInt32, 'value': value.dtype}))
(True, True)
>>> encoded.to_physical().to_list()
[{'len': 2, 'value': 1704067200000000123}, {'len': 2, 'value': None}, {'len': 1, 'value': 1704240000000000789}]
>>> identifiers = runs.rle_id()
>>> (type(identifiers) is pl.Series, identifiers.dtype, identifiers.to_list())
(True, UInt32, [0, 0, 1, 1, 2])
>>> difference = value.diff()
>>> (type(difference) is pl.Series, difference.dtype, difference.to_physical().to_list())
(True, Duration(time_unit='ns'), [None, None, None, 172800000000666])
>>> shortened = value.diff(null_behavior='drop')
>>> (type(shortened) is pl.Series, shortened.dtype, shortened.to_physical().to_list())
(True, Duration(time_unit='ns'), [None, None, 172800000000666])
>>> def business_code(date):
...     return {1: 10, 3: 30}.get(date.day, 0)
>>> codes = value.map_elements(business_code, return_dtype=pl.Int64)
>>> (type(codes) is pl.Series, codes.dtype, codes.name, codes.to_list())
(True, Int64, 'event', [30, None, 10, 30])
>>> summary = value.describe()
>>> (type(summary) is pl.DataFrame, summary.schema == {'statistic': pl.String, 'value': pl.String})
(True, True)
>>> summary_values = dict(zip(summary['statistic'].to_list(), summary['value'].to_list()))
>>> [summary_values[k] for k in ['count', 'null_count', 'mean', 'min', 'max']]
['3', '1', '2024-01-02 08:00:00+00:00', '2024-01-01 00:00:00+00:00', '2024-01-03 00:00:00+00:00']
>>> value.to_physical().to_list() == ticks
True
```

Use `describe` as a readable summary, not a persistent date representation.
See the [rsTimes difference guide](../guides/pldt-differences.md),
[native window examples](inherited-pldt-windows.md), and the
[provider reference](https://docs.pola.rs/api/python/stable/reference/series/index.html)
for parameter details of inherited methods.
