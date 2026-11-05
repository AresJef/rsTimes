# Native frames, dummy columns and initialization text

Inherited Polars export helpers return native containers or text. A DataFrame's
date column can retain exact ns even though converting its cells to standard
Python datetime would limit fractions to microseconds. Check the actual date
column when exact interchange matters.

## Native DataFrame and one-hot columns

`to_frame` returns a Polars DataFrame with the date column's unit, timezone,
name, values and validity. An explicit column name affects the returned frame,
not the original Pldt. This is a native container conversion, not a deep-copy
ownership promise.

`to_dummies` returns UInt8 one-hot columns. Native date labels in these column
names retain the displayed ns fractions; the null category has its own column
by default. These are categorical indicator columns rather than a date dtype.

```{doctest} inherited-pldt-native-frame-and-dummies
>>> import polars as pl
>>> from rstimes import Pldt
>>> ticks = [1704067200000000123, None, 1704240000000000789]
>>> value = Pldt(pl.Series('event', ticks, dtype=pl.Datetime('ns', 'UTC')))
>>> frame = value.to_frame()
>>> (type(frame) is pl.DataFrame, frame.schema == {'event': value.dtype}, frame.shape)
(True, True, (3, 1))
>>> frame['event'].to_physical().to_list() == ticks
True
>>> renamed = value.to_frame(name='date')
>>> (renamed.columns, renamed['date'].dtype == value.dtype, renamed['date'].to_physical().to_list() == ticks, value.name)
(['date'], True, True, 'event')
>>> dummies = value.to_dummies()
>>> (type(dummies) is pl.DataFrame, dummies.shape, all(dtype == pl.UInt8 for dtype in dummies.dtypes))
(True, (3, 3), True)
>>> dummies.to_dict(as_series=False)
{'event_2024-01-01 00:00:00.000000123 UTC': [1, 0, 0], 'event_2024-01-03 00:00:00.000000789 UTC': [0, 0, 1], 'event_null': [0, 1, 0]}
>>> no_null_category = value.to_dummies(drop_nulls=True)
>>> (no_null_category.shape, 'event_null' in no_null_category.columns, no_null_category.row(1))
((3, 2), False, (0, 0))
>>> value.to_physical().to_list() == ticks
True
```

## Initialization text and exact reconstruction

`to_init_repr` returns native Series initialization text. The example below
uses a microsecond date column and executes that text in a fixed namespace.
Standard Python datetime values have microsecond resolution. For storing
rsTimes dates with all ns digits, retain physical integer ticks, missingness
and the complete dtype, as shown afterwards.

```{doctest} inherited-pldt-native-initialization-text
>>> import datetime as datetime_module
>>> import zoneinfo
>>> text_value = Pldt(pl.Series('midnight', [1704067200000000, None], dtype=pl.Datetime('us', 'UTC')))
>>> initialization = text_value.to_init_repr()
>>> (type(initialization) is str, initialization.startswith('pl.Series('), 'Datetime' in initialization)
(True, True, True)
>>> reconstructed = eval(initialization, {'pl': pl, 'datetime': datetime_module, 'zoneinfo': zoneinfo})
>>> (type(reconstructed) is pl.Series, reconstructed.dtype == text_value.dtype, reconstructed.to_physical().to_list())
(True, True, [1704067200000000, None])
```

For exact reconstruction, retain explicit integer ticks, validity, unit,
timezone and name. A Python list of physical ticks and None keeps the valid
values separate from missingness; it does not use a NumPy NaT sentinel.

```{doctest} inherited-pldt-exact-native-reconstruction
>>> physical_values = value.to_physical().to_list()
>>> restored = pl.Series(value.name, physical_values, dtype=value.dtype)
>>> (type(restored) is pl.Series, restored.dtype == value.dtype, restored.to_physical().to_list() == ticks)
(True, True, True)
>>> restored_date = Pldt(restored)
>>> (type(restored_date) is Pldt, restored_date.dtype == value.dtype, restored_date.to_physical().to_list() == ticks)
(True, True, True)
```

See the [native Series export reference](https://docs.pola.rs/api/python/stable/reference/series/index.html)
for the provider's options, and [the rsTimes output guide](../guides/pldt-output.md)
for checked NumPy and standard Python precision boundaries.
