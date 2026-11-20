# Native summaries, ordering and date analysis

## Get the position of the earliest date

(ref-pldt-native-argmin)=
```python
from rstimes import Pldt

events = Pldt([9, None, 5], unit="ns", tz="UTC")
print(events.arg_min())
```

**Output**

```text
2
```

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

## Distinct values, counts and row ordering

`mode`, `unique`, top/bottom selection and rank return ordinary native Series.
`unique(maintain_order=True)` uses first occurrence order. Top/bottom selection
does not promise sorted output, so its result is checked as a multiset.
`arg_sort` returns row positions; a rank is a row value, not a position.

Scalar lookup matches the value you supply. Standard datetime has microsecond
resolution; use it on the explicit microsecond column below. `index_of`
returns an integer position or None. `search_sorted` requires sorted data;
vector input produces a native index Series, while scalar input produces int.

## Date categories and numeric-only boundaries

`bin_intervals` accepts actual date breakpoints. `bin_ranks` groups sorted
positions and can split equal values across bins. `bin_quantiles` requires
numeric input; `hist` also requires numerical data. They reject this date
column rather than choosing elapsed or calendar units for you.

The inherited `cut` and `qcut` compatibility methods are deprecated in the
verified native provider. Their small example uses physical microsecond
breakpoints and explicit labels. Prefer date breakpoints with `bin_intervals`
for new date-category code.

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

Use `describe` as a readable summary, not a persistent date representation.
See the [rsTimes difference guide](../guides/pldt-differences.md),
[native window examples](inherited-pldt-windows.md), and the
[provider reference](https://docs.pola.rs/api/python/stable/reference/series/index.html)
for parameter details of inherited methods.
