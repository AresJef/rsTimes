# Inherited pandas indexing and labels

## Find an exact date label

(ref-pddt-exact-label)=
```python
from rstimes import Pddt

dates = Pddt(["2024-01-01", "2024-01-03"], unit="us", name="event")
print(int(dates.get_loc("2024-01-03")))
```

**Output**

```text
1
```

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

Date-index values are immutable through item assignment. `name` is metadata and
can be changed with the naming methods later on this page.

## Duplicate labels and alignment positions

`get_loc` can return an integer for a unique label, a slice for a contiguous
monotonic duplicate run, or a Boolean mask. The missing value in `value` makes
this sample nonmonotonic, so its duplicate lookup returns a mask.
`get_indexer` requires a unique source index; the other two indexer methods
handle duplicate sources. A missing target has position -1.

## Time-of-day and as-of lookups

The time selectors return NumPy integer positions. They inspect local clock
fields in the receiver's timezone. As-of lookup finds the last valid label at
or before a requested instant on a sorted index. `asof_locs` additionally takes
a Boolean validity mask matching the source length.

## A single level, names and equality

A Pddt has one level. `get_level_values(0)` returns a Pddt; removing its only
level is an error. `rename` and `set_names` return a named Pddt by default, or
return None and update metadata when `inplace=True`. Value equality ignores a
name difference; `identical` includes metadata, and `is_` tests identity of the
underlying index identity token. None of them is a vectorized date comparison.
