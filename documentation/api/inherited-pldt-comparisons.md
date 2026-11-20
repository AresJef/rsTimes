# Native comparisons, membership and protocols

## Compare native dates row by row

(ref-pldt-native-date-comparison)=
```python
from rstimes import Pldt

events = Pldt([9, None, 5], unit="ns", name="event")
thresholds = Pldt([8, 1, 5], unit="ns")
match = events > thresholds
print(match.to_list())
```

**Output**

```text
[True, None, False]
```

Native Polars comparisons return ordinary Boolean Series and propagate nulls.
They differ from rsTimes predicates that deliberately map a missing date to
False. A scalar index equality check is `equals`; elementwise equality is
`eq` or `==`. Native membership, duplicate masks and hashing also have distinct
null and return roles. All calls below run on actual Pldt.

## Elementwise comparison and missing-aware equality

Native `is_close` is a numerical tolerance operation and rejects Datetime; it
is not the rsTimes date-difference interface. `eq_missing` and `ne_missing`
explicitly decide missing-aware equality, producing non-null Boolean results
for the two missing-input rows above.

## Membership, duplicate masks and scalar equality

Use `is_in` for a row mask. Its set input is explicitly a List Series here,
making the membership set explicit.
`nulls_equal=False` propagates source null by default; True allows a null to
match a null set member. In contrast, `item in value` returns one Python bool.

`arg_unique` returns native index positions of first distinct values, including
the missing value. `arg_true` requires Boolean data and rejects a date Series.
`equals` returns a Python bool, includes null equality by default, and can opt
into comparing names; it is not an elementwise mask.

## Hash, truth and display protocols

The Python Series container is unhashable and has no scalar truth value,
including when it is empty. Native `.hash()` instead returns UInt64 row hashes,
including a hash for a null. Equal values have equal hashes in this call, but
row hashes are not a promise of unique identifiers or a stable interchange
format across different Polars releases.

The native display identifies the Pldt wrapper and shows its native date dtype.
Use an explicit date formatter when preparing user-visible date strings.

## Reflected subtraction and explicit date differences

The inherited reflected operator returns a native Duration Series. This
example uses whole-second dates and checks its actual unit, nulls and values.
For rsTimes' date-difference semantics, use forward subtraction or the explicit
`diff` interface; negating a forward result reverses its direction.

For explicit difference units and elapsed/calendar choices, use the
[rsTimes difference guide](../guides/pldt-differences.md). The native
[Polars Series reference](https://docs.pola.rs/api/python/stable/reference/series/index.html)
remains the provider reference for the inherited operations on this page.
