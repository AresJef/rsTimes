# Inherited pandas container operations

## Select unique nonmissing dates

(ref-pddt-drop-missing-duplicates)=
```python
from rstimes import Pddt

dates = Pddt(["2024-02-29", None, "2024-02-29", "2024-03-01"], unit="us", name="event")
selected = dates.dropna().unique()
print(selected.isoformat().tolist())
```

**Output**

```text
['2024-02-29T00:00:00', '2024-03-01T00:00:00']
```

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

A `shift` frequency changes date labels. It does not insert missing rows or
shift row positions. When the receiver has no frequency, pass an explicit
frequency; otherwise pandas raises NullFrequencyError.

## Duplicates, ordering and sets

`drop_duplicates(keep=...)` chooses which duplicate occurrence to retain;
`unique` keeps first occurrence order. `union` can preserve the maximum duplicate
multiplicity present in either operand, so it is not an instruction to remove
all duplicates. Sorting can optionally return a NumPy permutation indexer.

## Alignment, encoding and grouping

`reindex` and `join(return_indexers=True)` return the new index and integer
indexers. A -1 marks a label missing from an operand. `reindex` rejects a source
with duplicate labels. `factorize` gives missing values code -1 by default;
`value_counts(dropna=False)` can count the missing label explicitly.

`groupby` here groups index labels using the supplied key array and returns a
mapping of keys to Pddt values. It is not DataFrameGroupBy. The `map` result
family follows what the callable returns; integer output is an ordinary Index.
Callback errors remain the provider's responsibility.
