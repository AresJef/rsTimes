# Version-specific inherited pandas entries

Inherited method availability follows the installed pandas version. This page
covers every entry found only in a compatibility profile. The tested profiles
are pandas 2.3.3, 3.0.6 and 3.1.0; it does not predict method availability in
unreleased dependency versions. The public coverage table records the actual
profile required for each entry.

## Legacy type predicates, formatting and sorting

With pandas 2.3, the eight legacy dtype predicates below return False on Pddt
and emit FutureWarning. They describe the date dtype, not its integer storage.
`format` returns a list of display strings and also emits FutureWarning.
`sort` raises TypeError because an Index cannot sort its values in place; use
`sort_values` to obtain a new index. These ten entries are absent from the two
tested pandas 3 profiles.

```{doctest} inherited-pddt-legacy-pandas2
>>> import warnings
>>> import pandas as pd
>>> from rstimes import Pddt
>>> value = Pddt(['2024-01-01', None], unit='ns', tz='UTC', name='event')
>>> legacy_predicates = ['holds_integer', 'is_boolean', 'is_categorical', 'is_floating', 'is_integer', 'is_interval', 'is_numeric', 'is_object']
>>> if pd.__version__.startswith('2.3.'):
...     for method in legacy_predicates:
...         with warnings.catch_warnings(record=True) as caught:
...             warnings.simplefilter('always')
...             result = getattr(value, method)()
...         assert type(result) is bool and result is False
...         assert any(isinstance(w.message, FutureWarning) and method in str(w.message) for w in caught)
...     with warnings.catch_warnings(record=True) as caught:
...         warnings.simplefilter('always')
...         formatted = value.format()
...     assert type(formatted) is list and formatted == ['2024-01-01 00:00:00+00:00', 'NaT']
...     assert any(isinstance(w.message, FutureWarning) and 'format' in str(w.message) for w in caught)
...     try:
...         value.sort()
...     except TypeError as error:
...         assert 'sort_values' in str(error)
...     else:
...         raise AssertionError('sort must reject in-place Index sorting')
... else:
...     assert pd.__version__.startswith(('3.0.', '3.1.'))
...     assert all(not hasattr(value, method) for method in legacy_predicates + ['format', 'sort'])
```

Use pandas' current dtype inspection interfaces for new applications, and use
rsTimes strftime when a date format rather than a debug representation is
wanted. The [pandas Index reference](https://pandas.pydata.org/pandas-docs/stable/reference/indexing.html)
tracks the provider's current replacement interfaces.

## pandas 3.1 whole-value replacement

The tested pandas 3.1 Index adds a direct `replace` method. It replaces matching
whole values and returns ordinary DatetimeIndex for the date example below.
It is distinct from the rsTimes field replacement at `value.pddt.replace(...)`.
The direct method is absent in pandas 2.3 and 3.0, so use the namespace path for
rsTimes date-field changes across all supported profiles.

```{doctest} inherited-pddt-pandas31-replace
>>> if pd.__version__.startswith('3.1.'):
...     replacement = pd.Timestamp('2024-01-02', tz='UTC')
...     result = value.replace(pd.Timestamp('2024-01-01', tz='UTC'), replacement)
...     assert type(result) is pd.DatetimeIndex and result.unit == 'ns' and str(result.tz) == 'UTC'
...     assert result.asi8.tolist() == [1704153600000000000, -9223372036854775808]
...     assert result.name == 'event' and value.asi8.tolist() == [1704067200000000000, -9223372036854775808]
... else:
...     assert pd.__version__.startswith(('2.3.', '3.0.')) and not hasattr(value, 'replace')
```

## Changed defaults and explicit missing-fill markers

The callable signatures also differ at `fillna` and `take`. With pandas 2.3,
omitting `fillna`'s value is allowed; pandas 3 requires that argument. The
legacy `downcast` argument exists only in pandas 2.3 and is deprecated. For
portable calls, pass the date value explicitly and omit `downcast`.

For `take`, an ordinary negative position selects from the end. To insert a
missing date at -1, pass `allow_fill=True, fill_value=pd.NaT` explicitly. The
older `fill_value=True` marker works in the tested pandas 2.3/3.0 profiles but
is a TypeError in pandas 3.1, which validates the supplied date fill value.
`OMITTED` in the per-entry signature means leave the argument out; it is a
provider sentinel and is distinct from passing None.

```{doctest} inherited-pddt-versioned-defaults
>>> ordered = Pddt(['2024-01-01', '2024-01-03'], unit='ns', tz='UTC')
>>> ordered.take([0, -1]).asi8.tolist()
[1704067200000000000, 1704240000000000000]
>>> ordered.take([0, -1], allow_fill=False).asi8.tolist()
[1704067200000000000, 1704240000000000000]
>>> filled = ordered.take([0, -1], allow_fill=True, fill_value=pd.NaT)
>>> (type(filled) is Pddt, filled.unit, str(filled.tz), filled.asi8.tolist())
(True, 'ns', 'UTC', [1704067200000000000, -9223372036854775808])
>>> if pd.__version__.startswith('3.1.'):
...     try:
...         ordered.take([0, -1], allow_fill=True, fill_value=True)
...     except TypeError as error:
...         assert 'bool' in str(error)
...     else:
...         raise AssertionError('Boolean fill is not a date in pandas3.1')
... else:
...     assert ordered.take([0, -1], allow_fill=True, fill_value=True).asi8.tolist() == [1704067200000000000, -9223372036854775808]
>>> if pd.__version__.startswith('2.3.'):
...     assert type(ordered.fillna()) is Pddt
...     with warnings.catch_warnings(record=True) as caught:
...         warnings.simplefilter('always')
...         result = value.fillna(pd.Timestamp('2024-01-02', tz='UTC'), downcast=None)
...     assert type(result) is pd.DatetimeIndex and result.asi8.tolist() == [1704067200000000000, 1704153600000000000]
...     assert any(isinstance(w.message, FutureWarning) and 'downcast' in str(w.message) for w in caught)
... else:
...     try:
...         ordered.fillna()
...     except TypeError as error:
...         assert 'value' in str(error)
...     else:
...         raise AssertionError('pandas3 requires an explicit fill value')
```
