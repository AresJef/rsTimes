# Inherited pandas container operations

Pddt inherits selection, set operations and alignment from pandas. Date results
do not all preserve the subclass. The tested calls below return Pddt for
selection, deletion, uniqueness, sorting and several set operations;
`append`, `fillna`, `shift` and `symmetric_difference` return ordinary
DatetimeIndex. In the tested pandas 3.1 profile, `putmask` and `where` also
return ordinary DatetimeIndex; they retain Pddt with pandas 2.3 and 3.0.
`factorize` returns a NumPy code array and ordinary
DatetimeIndex. Wrap a valid date result with `Pddt(result)` when you need the
rsTimes interface again.

Inputs, return types, exact UTC ns ticks, names and missing values are checked
below in each supported dependency profile. Complete provider parameters are in
the [pandas Index reference](https://pandas.pydata.org/pandas-docs/stable/reference/indexing.html).

## Selection, masks and missing values

`delete`, `take`, `repeat` and `insert` use positions. `drop` uses labels.
`putmask` replaces True positions; `where` keeps True positions and replaces
False positions. `dropna` removes NaT. `fillna` leaves valid dates untouched.

```{doctest} inherited-pddt-container-selection
>>> import numpy as np
>>> import pandas as pd
>>> from rstimes import Pddt
>>> first, second, third, missing = 1704067200000000000, 1704153600000000000, 1704240000000000000, -9223372036854775808
>>> value = Pddt(['2024-01-03', '2024-01-01', '2024-01-03', None], unit='ns', tz='UTC', name='event')
>>> other = Pddt(['2024-01-02', '2024-01-03'], unit='ns', tz='UTC', name='event')
>>> replacement = pd.Timestamp('2024-01-02', tz='UTC')
>>> def check(result, ticks, cls=Pddt, name='event'):
...     assert type(result) is cls and result.unit == 'ns' and str(result.tz) == 'UTC'
...     assert result.asi8.tolist() == ticks and result.name == name
>>> check(value.delete(1), [third, third, missing])
>>> check(value.drop([pd.Timestamp('2024-01-01', tz='UTC')]), [third, third, missing])
>>> check(value.drop([pd.Timestamp('2024-01-20', tz='UTC')], errors='ignore'), [third, first, third, missing])
>>> check(value.dropna(), [third, first, third])
>>> check(value.fillna(replacement), [third, first, third, second], pd.DatetimeIndex)
>>> mask_type = {'2.3': Pddt, '3.0': Pddt, '3.1': pd.DatetimeIndex}['.'.join(pd.__version__.split('.')[:2])]
>>> check(value.putmask([True, False, False, False], replacement), [second, first, third, missing], mask_type)
>>> check(value.where([False, True, True, False], replacement), [second, first, third, second], mask_type)
>>> check(value.insert(1, replacement), [third, second, first, third, missing])
>>> check(value.take([1, 0]), [first, third])
>>> check(value.repeat(2), [third, third, first, first, third, third, missing, missing])
>>> check(value.append(other), [third, first, third, missing, second, third], pd.DatetimeIndex)
>>> check(value.shift(1, freq='D'), [third + 86400000000000, second, third + 86400000000000, missing], pd.DatetimeIndex)
>>> value.asi8.tolist() == [third, first, third, missing]
True
>>> def error_name(call):
...     try:
...         call()
...     except Exception as error:
...         return type(error).__name__
...     raise AssertionError('an error was required')
>>> error_name(lambda: value.drop([pd.Timestamp('2024-01-20', tz='UTC')]))
'KeyError'
>>> error_name(lambda: value.putmask([True], replacement))
'ValueError'
>>> error_name(lambda: value.shift(1))
'NullFrequencyError'
```

A `shift` frequency changes date labels. It does not insert missing rows or
shift row positions. When the receiver has no frequency, pass an explicit
frequency; otherwise pandas raises NullFrequencyError.

## Duplicates, ordering and sets

`drop_duplicates(keep=...)` chooses which duplicate occurrence to retain;
`unique` keeps first occurrence order. `union` can preserve the maximum duplicate
multiplicity present in either operand, so it is not an instruction to remove
all duplicates. Sorting can optionally return a NumPy permutation indexer.

```{doctest} inherited-pddt-sets-and-ordering
>>> value.duplicated().tolist()
[False, False, True, False]
>>> check(value.drop_duplicates(), [third, first, missing])
>>> check(value.drop_duplicates(keep=False), [first, missing])
>>> check(value.unique(), [third, first, missing])
>>> (value.nunique(), value.nunique(dropna=False))
(2, 3)
>>> check(value.difference(other), [first, missing])
>>> check(value.intersection(other), [third])
>>> check(value.union(other), [first, second, third, third, missing])
>>> check(value.symmetric_difference(other), [first, second, missing], pd.DatetimeIndex)
>>> sorted_value, permutation = value.sort_values(return_indexer=True)
>>> check(sorted_value, [first, third, third, missing])
>>> (type(permutation) is np.ndarray, permutation.tolist())
(True, [1, 0, 2, 3])
>>> sorted_level, permutation = value.sortlevel()
>>> check(sorted_level, [missing, first, third, third])
>>> permutation.tolist()
[3, 1, 0, 2]
>>> value.argsort().tolist()
[1, 0, 2, 3]
>>> ordered = Pddt(['2024-01-01', '2024-01-03'], unit='ns', tz='UTC', name='event')
>>> int(ordered.searchsorted(replacement))
1
>>> ordered.searchsorted(pd.DatetimeIndex(['2023-12-31', '2024-01-03'], tz='UTC')).tolist()
[0, 1]
```

## Alignment, encoding and grouping

`reindex` and `join(return_indexers=True)` return the new index and integer
indexers. A -1 marks a label missing from an operand. `reindex` rejects a source
with duplicate labels. `factorize` gives missing values code -1 by default;
`value_counts(dropna=False)` can count the missing label explicitly.

```{doctest} inherited-pddt-align-and-group
>>> target, positions = ordered.reindex(other)
>>> check(target, [second, third])
>>> (type(positions) is np.ndarray, positions.tolist())
(True, [-1, 1])
>>> error_name(lambda: value.reindex(other))
'ValueError'
>>> joined, left_positions, right_positions = ordered.join(other, how='outer', return_indexers=True)
>>> check(joined, [first, second, third])
>>> (left_positions.tolist(), right_positions.tolist())
([0, -1, 1], [-1, 0, 1])
>>> codes, labels = value.factorize()
>>> (type(codes) is np.ndarray, codes.tolist())
(True, [0, 1, 0, -1])
>>> check(labels, [third, first], pd.DatetimeIndex, None)
>>> counts = value.value_counts(dropna=False, sort=False)
>>> (type(counts) is pd.Series, counts.dtype, counts.tolist())
(True, dtype('int64'), [2, 1, 1])
>>> counts.index.asi8.tolist()
[1704240000000000000, 1704067200000000000, -9223372036854775808]
>>> groups = value.groupby(['a', 'b', 'a', 'b'])
>>> (isinstance(groups, dict), list(groups))
(True, ['a', 'b'])
>>> check(groups['a'], [third, third])
>>> check(groups['b'], [first, missing])
>>> mapped = value.map(lambda date: -1 if date is pd.NaT else date.year)
>>> (type(mapped) is pd.Index, mapped.dtype, mapped.tolist(), mapped.name)
(True, dtype('int64'), [2024, 2024, 2024, -1], 'event')
>>> value.isin(other).tolist()
[True, False, True, False]
>>> (value.isna().tolist(), value.isnull().tolist())
([False, False, False, True], [False, False, False, True])
>>> (value.notna().tolist(), value.notnull().tolist())
([True, True, True, False], [True, True, True, False])
```

`groupby` here groups index labels using the supplied key array and returns a
mapping of keys to Pddt values. It is not DataFrameGroupBy. The `map` result
family follows what the callable returns; integer output is an ordinary Index.
Callback errors remain the provider's responsibility.
