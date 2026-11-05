# Native date container transformations and mutation

Inherited Series operations have native return and mutation rules. The verified
native date results on this page are ordinary Series except where Pldt is
explicitly asserted. Names, exact ns ticks, UTC metadata, nulls and changes to
the receiver are checked separately. Do not infer a deep copy or a Pldt result
from a native operation's name.

## Names, nulls, clipping and interpolation

`alias` and `rename` return a named Pldt without changing the original name.
Forward/backward filling propagates exact date ticks. `drop_nulls` removes null
rows; `drop_nans` leaves this nonfloating date dtype unchanged, including its
null. Native `fill_nan` rejects Datetime rather than treating null as NaN.

Native linear interpolation accepts dates and preserves the exact ns in the
verified interval. The `interpolate_by` numerical kernel has a different dtype
contract and rejects Datetime values even with a valid numerical axis.

```{doctest} inherited-pldt-native-fills-and-casts
>>> from collections import Counter
>>> from datetime import datetime, timezone
>>> import polars as pl
>>> from rstimes import Pldt
>>> first, last, replacement = 1704067200000000123, 1704240000000000789, 1704326400000000456
>>> ticks = [first, None, last]
>>> value = Pldt(pl.Series('event', ticks, dtype=pl.Datetime('ns', 'UTC')))
>>> def check(result, expected, cls=pl.Series, name='event', dtype=pl.Datetime('ns', 'UTC')):
...     assert type(result) is cls and result.name == name and result.dtype == dtype
...     assert result.to_physical().to_list() == expected
>>> check(value.alias('alias'), ticks, Pldt, 'alias')
>>> check(value.rename('renamed'), ticks, Pldt, 'renamed')
>>> value.name
'event'
>>> check(value.forward_fill(), [first, first, last])
>>> check(value.backward_fill(), [first, last, last])
>>> check(value.drop_nulls(), [first, last])
>>> check(value.drop_nans(), ticks)
>>> def error_name(call):
...     try:
...         call()
...     except Exception as error:
...         return type(error).__name__
...     raise AssertionError('an error was required')
>>> error_name(lambda: value.fill_nan(0))
'InvalidOperationError'
>>> check(value.interpolate(), [first, 1704153600000000456, last])
>>> spaced = Pldt(pl.Series('event', [first, None, None, last], dtype=value.dtype))
>>> check(spaced.interpolate(), [first, 1704124800000000345, 1704182400000000567, last])
>>> check(spaced.interpolate(method='nearest'), [first, first, last, last])
>>> error_name(lambda: value.interpolate_by(pl.Series('axis', [0, 1, 2])))
'InvalidOperationError'
>>> lower = pl.Series('lower', [first], dtype=value.dtype)
>>> upper = pl.Series('upper', [last], dtype=value.dtype)
>>> outside = Pldt(pl.Series('event', [first - 10, last + 10, None], dtype=value.dtype))
>>> check(outside.clip(lower, upper), [first, last, None])
>>> check(value.clip(datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 3, tzinfo=timezone.utc)), [first, None, 1704240000000000000])
>>> check(value.cast(pl.Int64), ticks, dtype=pl.Int64)
>>> check(value.cast(pl.Datetime('us', 'UTC')), [1704067200000000, None, 1704240000000000], Pldt, dtype=pl.Datetime('us', 'UTC'))
>>> check(value.cast(pl.Date), [19723, None, 19725], dtype=pl.Date)
>>> check(value.cum_count(), [1, 1, 2], dtype=pl.UInt32)
>>> check(value.cum_count(reverse=True), [2, 1, 1], dtype=pl.UInt32)
```

`cast` is an explicit native conversion and can discard precision or change the
dtype. It differs from checked rsTimes output/unit interfaces. Cumulative count
counts non-null values; its output at a missing row is a count, not null.
For date filling, give the scalar expression the complete date dtype. The
following calls keep the source's ns unit, UTC timezone and existing date ticks.
The scalar expression is also executed in a collected lazy query.

```{doctest} inherited-pldt-native-fill-and-shift
>>> fill = pl.lit(replacement, dtype=value.dtype)
>>> check(value.fill_null(fill), [first, replacement, last])
>>> check(value.shift(1), [None, first, None])
>>> check(value.shift(1, fill_value=fill), [replacement, first, None])
>>> check(value.shift(-1), [None, last, None])
>>> lazy = value.to_frame().lazy().select(pl.col('event').fill_null(fill))
>>> check(lazy.collect()['event'], [first, replacement, last])
>>> value.to_physical().to_list() == ticks
True
```

## Whole-value replacement and nullable selection

Native `replace` changes matching whole date values, rather than date fields.
The explicit native date Series operands below can represent all ns digits.
A microsecond Python datetime at midnight does not match a date 123 ns later.
`replace_strict` rejects unmapped values unless a default is supplied. None is
an explicit missing default, while omitting the default preserves the strict
completeness requirement.

`zip_with` chooses this receiver at True mask positions and the other Series at
False or null mask positions in these verified profiles. It returns Pldt for
the matching date dtype, unlike several native transformation helpers.

```{doctest} inherited-pldt-native-replacement
>>> old = pl.Series('old', [first], dtype=value.dtype)
>>> new = pl.Series('new', [replacement], dtype=value.dtype)
>>> check(value.replace(old, new), [replacement, None, last])
>>> check(value.replace(datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 4, tzinfo=timezone.utc)), ticks)
>>> error_name(lambda: value.replace_strict(old, new))
'InvalidOperationError'
>>> check(value.replace_strict(old, new, default=None), [replacement, None, None])
>>> check(value.replace_strict(old, new, default=value), [replacement, None, last])
>>> other = pl.Series('other', [replacement, replacement, replacement], dtype=value.dtype)
>>> check(value.zip_with(pl.Series([True, False, None]), other), [first, replacement, replacement], Pldt)
>>> check(value.reverse(), [last, None, first])
>>> check(value.sort(), [None, first, last], Pldt)
>>> check(value.sort(descending=True, nulls_last=True), [last, first, None], Pldt)
>>> value.to_physical().to_list() == ticks
True
```

The original column remains unchanged by the transformations in this section.
Date-field replacement remains a separate rsTimes namespace operation.

## In-place wrapper edits and returned replacements

`extend`, `scatter` and item assignment mutate the chosen Pldt wrapper. They
operate on separate clones below, and the original is checked afterwards.
`set` and `extend_constant` instead return ordinary Series for these calls.
Use a matching date Series with `scatter` to assign new dates with explicit
unit and timezone metadata. Item assignment below clears a value with None.

```{doctest} inherited-pldt-native-mutation
>>> date_fill = datetime(2024, 1, 2, tzinfo=timezone.utc)
>>> extended = value.clone()
>>> extended.extend(other) is extended
True
>>> check(extended, ticks + [replacement, replacement, replacement], Pldt)
>>> check(value.extend_constant(date_fill, 2), ticks + [1704153600000000000, 1704153600000000000])
>>> check(value.set(pl.Series([True, False, False]), date_fill), [1704153600000000000, None, last])
>>> scattered = value.clone()
>>> scattered.scatter([0, 2], pl.Series('new', [replacement, replacement], dtype=value.dtype)) is scattered
True
>>> check(scattered, [replacement, None, replacement], Pldt)
>>> assigned = value.clone()
>>> assigned[0] = None
>>> check(assigned, [None, None, last], Pldt)
>>> assigned.__setitem__(2, None) is None
True
>>> check(assigned, [None, None, None], Pldt)
>>> value.to_physical().to_list() == ticks
True
```

## Native nested outputs, reshaping and sampling

`repeat_by`, `implode` and a two-dimensional `reshape` produce ordinary nested
Series, rather than Pldt. Their nested date values still carry exact ns and
inner null validity. `explode` on this already flat date column returns an
ordinary flat Series with the same rows.

Sampling and shuffling return ordinary native Series. The checks use actual
seeds, metadata and exact multisets, without promising that a random permutation
will remain identical across different Polars releases.

```{doctest} inherited-pldt-native-nesting-and-sampling
>>> repeated = value.repeat_by(pl.Series([1, 2, 0]))
>>> (type(repeated) is pl.Series, repeated.dtype, repeated.to_physical().to_list())
(True, List(Datetime(time_unit='ns', time_zone='UTC')), [[1704067200000000123], [None, None], []])
>>> packed = value.implode()
>>> (type(packed) is pl.Series, packed.dtype, packed.to_physical().to_list())
(True, List(Datetime(time_unit='ns', time_zone='UTC')), [[1704067200000000123, None, 1704240000000000789]])
>>> matrix = value.reshape((1, 3))
>>> (type(matrix) is pl.Series, matrix.dtype == pl.Array(value.dtype, 3), matrix.to_physical().to_list())
(True, True, [[1704067200000000123, None, 1704240000000000789]])
>>> check(value.explode(), ticks)
>>> shuffled = value.shuffle(seed=42)
>>> (type(shuffled) is pl.Series, shuffled.dtype == value.dtype, shuffled.name, Counter(shuffled.to_physical().to_list()) == Counter(ticks))
(True, True, 'event', True)
>>> shuffled.to_physical().to_list() == value.shuffle(seed=42).to_physical().to_list()
True
>>> sampled = value.sample(n=3, with_replacement=False, seed=42)
>>> (type(sampled) is pl.Series, sampled.dtype == value.dtype, sampled.name, Counter(sampled.to_physical().to_list()) == Counter(ticks))
(True, True, 'event', True)
>>> replacement_sample = value.sample(n=5, with_replacement=True, seed=42)
>>> (type(replacement_sample) is pl.Series, replacement_sample.dtype == value.dtype, len(replacement_sample), set(replacement_sample.to_physical().to_list()) <= set(ticks))
(True, True, 5, True)
```

The [native Polars Series reference](https://docs.pola.rs/api/python/stable/reference/series/index.html)
provides complete parameter choices. Follow the returned native dtype's API
when a transformation leaves a date column for a List, Array, Date or numeric
representation.
