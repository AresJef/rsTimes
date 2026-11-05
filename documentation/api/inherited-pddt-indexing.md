# Inherited pandas indexing and labels

Pddt keeps pandas Index selection and alignment rules. Position selection and
label lookup have different return roles: one position returns a pandas
Timestamp or NaT; a slice or integer/Boolean gather returns Pddt. Lookup methods
return positions, slices or masks for use by the caller. Label slice endpoints
are inclusive, whereas Python positional slice stops are exclusive.

See the [pandas indexing reference](https://pandas.pydata.org/pandas-docs/stable/reference/indexing.html)
for complete provider parameters. The examples below run on actual Pddt, keep
ns storage and UTC metadata on date-index results, and assert duplicate/missing
lookup behavior explicitly.

## Scalar, slice, gather and iteration

```{doctest} inherited-pddt-position-selection
>>> import numpy as np
>>> import pandas as pd
>>> from rstimes import Pddt
>>> ticks = [1704067200000000000, 1704240000000000000, 1704240000000000000, -9223372036854775808]
>>> value = Pddt(['2024-01-01', '2024-01-03', '2024-01-03', None], unit='ns', tz='UTC', name='event')
>>> scalar = value[0]
>>> (type(scalar) is pd.Timestamp, scalar.isoformat(), value[-1] is pd.NaT)
(True, '2024-01-01T00:00:00+00:00', True)
>>> def check_dates(result, expected, name='event'):
...     assert type(result) is Pddt and result.unit == 'ns' and str(result.tz) == 'UTC'
...     assert result.asi8.tolist() == expected and result.name == name
>>> check_dates(value[1:3], ticks[1:3])
>>> check_dates(value[[2, 0]], [ticks[2], ticks[0]])
>>> check_dates(value[np.array([True, False, False, True])], [ticks[0], ticks[3]])
>>> check_dates(value[0:0], [])
>>> (len(value), [None if x is pd.NaT else x.isoformat() for x in value])
(4, ['2024-01-01T00:00:00+00:00', '2024-01-03T00:00:00+00:00', '2024-01-03T00:00:00+00:00', None])
>>> ('2024-01-01' in value, pd.NaT in value, '2024-01-02' in value)
(True, True, False)
>>> def error_name(call):
...     try:
...         call()
...     except Exception as error:
...         return type(error).__name__
...     raise AssertionError('an error was required')
>>> error_name(lambda: value.__setitem__(0, pd.Timestamp('2024-01-02', tz='UTC')))
'TypeError'
>>> error_name(lambda: value[10])
'IndexError'
>>> error_name(lambda: value[[True, False]])
'IndexError'
```

Date-index values are immutable through item assignment. `name` is metadata and
can be changed with the naming methods later on this page.

## Duplicate labels and alignment positions

`get_loc` can return an integer for a unique label, a slice for a contiguous
monotonic duplicate run, or a Boolean mask. The missing value in `value` makes
this sample nonmonotonic, so its duplicate lookup returns a mask.
`get_indexer` requires a unique source index; the other two indexer methods
handle duplicate sources. A missing target has position -1.

```{doctest} inherited-pddt-label-indexers
>>> ordered = Pddt(['2024-01-01', '2024-01-02', '2024-01-03'], unit='ns', tz='UTC', name='event')
>>> (int(ordered.get_loc('2024-01-02')), type(value.get_loc('2024-01-03')) is np.ndarray, value.get_loc('2024-01-03').tolist())
(1, True, [False, True, True, False])
>>> target = pd.DatetimeIndex(['2024-01-03', '2024-01-04'], tz='UTC')
>>> ordered.get_indexer(target).tolist()
[2, -1]
>>> value.get_indexer_for(target).tolist()
[1, 2, -1]
>>> indexer, missing_targets = value.get_indexer_non_unique(target)
>>> (indexer.tolist(), missing_targets.tolist())
([1, 2, -1], [1])
>>> ordered.get_indexer(pd.DatetimeIndex(['2024-01-02 12:00'], tz='UTC'), method='pad').tolist()
[1]
>>> ordered.get_indexer(pd.DatetimeIndex(['2024-01-02 12:00'], tz='UTC'), method='nearest', tolerance=pd.Timedelta('1h')).tolist()
[-1]
>>> error_name(lambda: value.get_indexer(target))
'InvalidIndexError'
>>> error_name(lambda: ordered.get_loc('2024-01-04'))
'KeyError'
>>> (int(ordered.get_slice_bound('2024-01-02', 'left')), int(ordered.get_slice_bound('2024-01-02', 'right')))
(1, 2)
>>> selection = ordered.slice_indexer('2024-01-01', '2024-01-02')
>>> (isinstance(selection, slice), selection.start, int(selection.stop), selection.step)
(True, 0, 2, None)
>>> tuple(int(x) for x in ordered.slice_locs('2024-01-01', '2024-01-02'))
(0, 2)
>>> check_dates(ordered[selection], [1704067200000000000, 1704153600000000000])
```

## Time-of-day and as-of lookups

The time selectors return NumPy integer positions. They inspect local clock
fields in the receiver's timezone. As-of lookup finds the last valid label at
or before a requested instant on a sorted index. `asof_locs` additionally takes
a Boolean validity mask matching the source length.

```{doctest} inherited-pddt-time-indexers
>>> ordered.indexer_at_time('00:00').tolist()
[0, 1, 2]
>>> ordered.indexer_between_time('00:00', '01:00').tolist()
[0, 1, 2]
>>> ordered.indexer_between_time('00:00', '01:00', include_start=False).tolist()
[]
>>> latest = ordered.asof(pd.Timestamp('2024-01-02 12:00', tz='UTC'))
>>> (type(latest) is pd.Timestamp, latest.isoformat())
(True, '2024-01-02T00:00:00+00:00')
>>> where = pd.DatetimeIndex(['2023-12-31', '2024-01-02 12:00'], tz='UTC')
>>> ordered.asof_locs(where, np.ones(3, dtype=bool)).tolist()
[-1, 1]
>>> ordered.asof_locs(where, np.array([True, False, True])).tolist()
[-1, 0]
```

## A single level, names and equality

A Pddt has one level. `get_level_values(0)` returns a Pddt; removing its only
level is an error. `rename` and `set_names` return a named Pddt by default, or
return None and update metadata when `inplace=True`. Value equality ignores a
name difference; `identical` includes metadata, and `is_` tests identity of the
underlying index identity token. None of them is a vectorized date comparison.

```{doctest} inherited-pddt-label-metadata
>>> check_dates(value.get_level_values(0), ticks)
>>> error_name(lambda: value.droplevel(0))
'ValueError'
>>> error_name(lambda: value.get_level_values(1))
'IndexError'
>>> renamed = value.rename('renamed')
>>> check_dates(renamed, ticks, 'renamed')
>>> named = value.set_names(['named'])
>>> check_dates(named, ticks, 'named')
>>> (value.name, value.equals(renamed), value.identical(renamed), value.is_(value))
('event', True, False, True)
>>> named.rename('inplace', inplace=True) is None
True
>>> named.set_names(['final'], inplace=True) is None
True
>>> (named.name, list(named.names), value.name)
('final', ['final'], 'event')
>>> one = Pddt(['2024-01-01'], unit='ns', tz='UTC')
>>> (type(one.item()) is pd.Timestamp, one.item().isoformat())
(True, '2024-01-01T00:00:00+00:00')
>>> error_name(lambda: value.item())
'ValueError'
```
