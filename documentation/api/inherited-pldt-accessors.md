# Inherited Polars accessors and generic extensions

## Access date fields through the registered namespace

(ref-pldt-native-registered-accessor)=
```python
from rstimes import Pldt

events = Pldt(["2024-02-29", None], unit="us", name="event")
days = events.pldt.day
print(days.to_list())
```

**Output**

```text
[29, None]
```

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

See the [complete Series namespace](polars-series.rst) for its members and the
[independently executed native .dt namespace](inherited-polars-datetime.md)
for the separate native defaults and return types.

## Dtype-specific accessors

The following reads create native namespace objects. Date data remains date
data. Representative wrong-dtype operations below assert their actual exception
classes. Use the rsTimes date namespace for date operations.

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

The native entry expects an Extension instance despite its broad upstream
dtype annotation. Passing an ordinary numeric dtype is an AssertionError in
the verified profiles; passing an Extension with the wrong storage type is a
SchemaError. Neither error changes the source column.
