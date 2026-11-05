# Native comparisons, membership and protocols

Native Polars comparisons return ordinary Boolean Series and propagate nulls.
They differ from rsTimes predicates that deliberately map a missing date to
False. A scalar index equality check is `equals`; elementwise equality is
`eq` or `==`. Native membership, duplicate masks and hashing also have distinct
null and return roles. All calls below run on actual Pldt.

## Elementwise comparison and missing-aware equality

```{doctest} inherited-pldt-native-comparisons
>>> from datetime import datetime, timezone
>>> import polars as pl
>>> from rstimes import Pldt
>>> first, second = 1704067200000000123, 1704153600000000000
>>> value = Pldt(pl.Series('event', [first, second, None, first], dtype=pl.Datetime('ns', 'UTC')))
>>> other = pl.Series('other', [second, second, None, None], dtype=value.dtype)
>>> def check_mask(result, expected):
...     assert type(result) is pl.Series and result.dtype == pl.Boolean and result.name == 'event'
...     assert result.to_list() == expected
>>> comparisons = {
...     '__eq__': [False, True, None, None], 'eq': [False, True, None, None],
...     '__ne__': [True, False, None, None], 'ne': [True, False, None, None],
...     '__lt__': [True, False, None, None], 'lt': [True, False, None, None],
...     '__le__': [True, True, None, None], 'le': [True, True, None, None],
...     '__gt__': [False, False, None, None], 'gt': [False, False, None, None],
...     '__ge__': [False, True, None, None], 'ge': [False, True, None, None],
... }
>>> for method, expected in comparisons.items():
...     check_mask(getattr(value, method)(other), expected)
>>> check_mask(value.eq_missing(other), [False, True, True, False])
>>> check_mask(value.ne_missing(other), [True, False, False, True])
>>> def error_name(call):
...     try:
...         call()
...     except Exception as error:
...         return type(error).__name__
...     raise AssertionError('an error was required')
>>> error_name(lambda: value.is_close(other))
'InvalidOperationError'
```

Native `is_close` is a numerical tolerance operation and rejects Datetime; it
is not the rsTimes date-difference interface. `eq_missing` and `ne_missing`
explicitly decide missing-aware equality, producing non-null Boolean results
for the two missing-input rows above.

## Membership, duplicate masks and scalar equality

Use `is_in` for a row mask. Its set input is explicitly a List Series here,
making the membership set explicit.
`nulls_equal=False` propagates source null by default; True allows a null to
match a null set member. In contrast, `item in value` returns one Python bool.

```{doctest} inherited-pldt-native-membership
>>> check_mask(value.is_in(other.implode()), [False, True, None, False])
>>> check_mask(value.is_in(other.implode(), nulls_equal=True), [False, True, True, False])
>>> start, end = datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 2, tzinfo=timezone.utc)
>>> check_mask(value.is_between(start, end), [True, True, None, True])
>>> check_mask(value.is_between(start, end, closed='none'), [True, False, None, True])
>>> (end in value, None in value, datetime(2024, 1, 4, tzinfo=timezone.utc) in value)
(True, True, False)
>>> masks = {
...     'is_duplicated': [True, False, False, True], 'is_unique': [False, True, True, False],
...     'is_first_distinct': [True, True, True, False], 'is_last_distinct': [False, True, True, True],
...     'is_null': [False, False, True, False], 'is_not_null': [True, True, False, True],
... }
>>> for method, expected in masks.items():
...     check_mask(getattr(value, method)(), expected)
>>> positions = value.arg_unique()
>>> (type(positions) is pl.Series, positions.dtype == pl.get_index_type(), positions.to_list())
(True, True, [0, 1, 2])
>>> error_name(value.arg_true)
'SchemaError'
>>> (value.equals(value.clone()), value.equals(value.clone(), null_equal=False))
(True, False)
>>> renamed = value.alias('renamed')
>>> (value.equals(renamed), value.equals(renamed, check_names=True))
(True, False)
```

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

```{doctest} inherited-pldt-native-display-and-hash
>>> (error_name(lambda: bool(value)), error_name(lambda: bool(value.clear())), error_name(lambda: hash(value)))
('TypeError', 'TypeError', 'TypeError')
>>> hashes = value.hash()
>>> (type(hashes) is pl.Series, hashes.dtype, hashes.name, hashes.len(), hashes.null_count())
(True, UInt64, 'event', 4, 0)
>>> hashes[0] == hashes[3]
True
>>> with pl.Config(tbl_rows=10):
...     display, text, formatted = repr(value), str(value), format(value, '')
>>> (type(display) is str, "Pldt: 'event'" in display, 'datetime[ns, UTC]' in display, 'null' in display, '2024-01-01' in display)
(True, True, True, True, True)
>>> (text == display, formatted == display)
(True, True)
>>> error_name(lambda: format(value, '.2f'))
'TypeError'
```

The native display identifies the Pldt wrapper and shows its native date dtype.
Use an explicit date formatter when preparing user-visible date strings.

## Reflected subtraction and explicit date differences

The inherited reflected operator returns a native Duration Series. This
example uses whole-second dates and checks its actual unit, nulls and values.
For rsTimes' date-difference semantics, use forward subtraction or the explicit
`diff` interface; negating a forward result reverses its direction.

```{doctest} inherited-pldt-native-reflected-subtraction
>>> aligned = Pldt(pl.Series('event', [1704067200000000000, None], dtype=value.dtype))
>>> target = datetime(2024, 1, 3, tzinfo=timezone.utc)
>>> reflected = target - aligned
>>> (type(reflected) is pl.Series, reflected.dtype, reflected.to_physical().to_list())
(True, Duration(time_unit='us'), [172800000000, None])
>>> direct = aligned.__rsub__(target)
>>> (direct.dtype == reflected.dtype, direct.to_physical().to_list() == reflected.to_physical().to_list())
(True, True)
>>> forward_reversed = -(aligned - target)
>>> (type(forward_reversed) is pl.Series, forward_reversed.dtype, forward_reversed.to_physical().to_list())
(True, Duration(time_unit='ns'), [172800000000000, None])
```

For explicit difference units and elapsed/calendar choices, use the
[rsTimes difference guide](../guides/pldt-differences.md). The native
[Polars Series reference](https://docs.pola.rs/api/python/stable/reference/series/index.html)
remains the provider reference for the inherited operations on this page.
