# Native date container transformations and mutation

## Fill a gap from the previous value

(ref-pldt-native-fill)=
```python
from rstimes import Pldt

events = Pldt([5, None, 9], unit="ns", tz="UTC", name="event")
filled = events.fill_null(strategy="forward")
print(filled.to_physical().to_list())
```

**Output**

```text
[5, 5, 9]
```

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

`cast` is an explicit native conversion and can discard precision or change the
dtype. It differs from checked rsTimes output/unit interfaces. Cumulative count
counts non-null values; its output at a missing row is a count, not null.
For date filling, give the scalar expression the complete date dtype. The
following calls keep the source's ns unit, UTC timezone and existing date ticks.
The scalar expression is also executed in a collected lazy query.

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

The original column remains unchanged by the transformations in this section.
Date-field replacement remains a separate rsTimes namespace operation.

## In-place wrapper edits and returned replacements

`extend`, `scatter` and item assignment mutate the chosen Pldt wrapper. They
operate on separate clones below, and the original is checked afterwards.
`set` and `extend_constant` instead return ordinary Series for these calls.
Use a matching date Series with `scatter` to assign new dates with explicit
unit and timezone metadata. Item assignment below clears a value with None.

## Native nested outputs, reshaping and sampling

`repeat_by`, `implode` and a two-dimensional `reshape` produce ordinary nested
Series, rather than Pldt. Their nested date values still carry exact ns and
inner null validity. `explode` on this already flat date column returns an
ordinary flat Series with the same rows.

Sampling and shuffling return ordinary native Series. The checks use actual
seeds, metadata and exact multisets, without promising that a random permutation
will remain identical across different Polars releases.

The [native Polars Series reference](https://docs.pola.rs/api/python/stable/reference/series/index.html)
provides complete parameter choices. Follow the returned native dtype's API
when a transformation leaves a date column for a List, Array, Date or numeric
representation.
