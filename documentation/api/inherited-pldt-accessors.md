# Inherited Polars accessors and generic extensions

A namespace is accessed as a property: read `value.pldt`, `value.dt` or
`value.ext`, then use its methods or fields. Do not call the namespace object's
constructor. The inherited `.pldt` accessor uses the same Series namespace as
an ordinary Polars Series; `.dt` remains Polars' native date namespace.

Other dtype namespaces can be visible on a date Series even when their
operations require an Array, Binary, Categorical, List, Map, String or Struct.
Their presence does not convert the date column to that dtype. This reference
records those accessors and their actual date-dtype boundaries rather than
reproducing every unrelated dtype API.

## The registered Series namespace on Pldt

```{doctest} inherited-pldt-registered-accessor
>>> import polars as pl
>>> from rstimes import Pldt
>>> value = Pldt(pl.Series('event', [1704067200000000123, None], dtype=pl.Datetime('ns', 'UTC')))
>>> ordinary = pl.Series('event', [1704067200000000123, None], dtype=value.dtype)
>>> type(value.pldt) is type(ordinary.pldt)
True
>>> years = value.pldt.year
>>> (type(years) is pl.Series, years.dtype, years.name, years.to_list())
(True, Int64, 'event', [2024, None])
>>> converted = value.pldt.as_unit('us')
>>> (type(converted) is Pldt, converted.dtype, converted.to_physical().to_list())
(True, Datetime(time_unit='us', time_zone='UTC'), [1704067200000000, None])
>>> value.to_physical().to_list()
[1704067200000000123, None]
```

See the [complete Series namespace](polars-series.rst) for its members and the
[independently executed native .dt namespace](inherited-polars-datetime.md)
for the separate native defaults and return types.

## Dtype-specific accessors

The following reads create native namespace objects. Date data remains date
data. Representative wrong-dtype operations below assert their actual exception
classes. Use the rsTimes date namespace for date operations.

```{doctest} inherited-pldt-dtype-accessors
>>> expected_accessors = {
...     'arr': 'ArrayNameSpace', 'bin': 'BinaryNameSpace', 'cat': 'CatNameSpace',
...     'list': 'ListNameSpace', 'map': 'MapNameSpace', 'str': 'StringNameSpace',
...     'struct': 'StructNameSpace',
... }
>>> for name, expected_type in expected_accessors.items():
...     assert type(getattr(value, name)).__name__ == expected_type
>>> def error_name(call):
...     try:
...         call()
...     except Exception as error:
...         return type(error).__name__
...     raise AssertionError('a dtype error was required')
>>> error_name(lambda: value.arr.len())
'InvalidOperationError'
>>> error_name(lambda: value.bin.size())
'SchemaError'
>>> error_name(lambda: value.list.len())
'InvalidOperationError'
>>> error_name(lambda: value.map.len())
'InvalidOperationError'
>>> error_name(lambda: value.str.len_chars())
'SchemaError'
>>> error_name(lambda: value.struct.fields)
'SchemaError'
>>> value.dtype
Datetime(time_unit='ns', time_zone='UTC')
```

Use date fields and date formatting from `.pldt` or `.dt` for date data. If your
task actually produces another dtype, operate on that returned native Series
and follow its dtype's API.

## Generic extension storage and wrapping

The generic `.ext` namespace is usable with date storage. `storage()` returns
ordinary Series; a nonextension source is returned without changing its data.
`to(dtype)` wraps the source with an actual `pl.Extension` dtype whose storage
matches the source's complete dtype, including unit and timezone. Its result
is an ordinary extension Series. Extracting storage round-trips the exact
nanoseconds and independent null validity. The original Pldt is unchanged.

The [upstream extension API](https://docs.pola.rs/api/python/stable/reference/series/api/polars.Series.ext.to.html)
is marked unstable by Polars. An extension wrapper has an Extension dtype;
it is not a Pldt date column until its date storage is recovered and wrapped.

```{doctest} inherited-pldt-generic-extension
>>> storage = value.ext.storage()
>>> (type(storage) is pl.Series, storage.dtype == value.dtype, storage.name, storage.to_physical().to_list())
(True, True, 'event', [1704067200000000123, None])
>>> dtype = pl.Extension('rstimes.docs.event', value.dtype, metadata='nanosecond UTC')
>>> wrapped = value.ext.to(dtype)
>>> (type(wrapped) is pl.Series, wrapped.dtype == dtype, wrapped.dtype.ext_name(), wrapped.dtype.ext_metadata())
(True, True, 'rstimes.docs.event', 'nanosecond UTC')
>>> restored = wrapped.ext.storage()
>>> (type(restored) is pl.Series, restored.dtype == value.dtype, restored.name, restored.to_physical().to_list())
(True, True, 'event', [1704067200000000123, None])
>>> error_name(lambda: value.ext.to(pl.Extension('rstimes.docs.wrong', pl.Int64)))
'SchemaError'
>>> error_name(lambda: value.ext.to(pl.Int64))
'AssertionError'
>>> value.to_physical().to_list()
[1704067200000000123, None]
```

The native entry expects an Extension instance despite its broad upstream
dtype annotation. Passing an ordinary numeric dtype is an AssertionError in
the verified profiles; passing an Extension with the wrong storage type is a
SchemaError. Neither error changes the source column.
