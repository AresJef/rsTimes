# Native frames, dummy columns and initialization text

## Make a one-column Polars DataFrame

(ref-pldt-native-frame)=
```python
from rstimes import Pldt

events = Pldt([5, None], unit="ns", tz="UTC", name="event")
frame = events.to_frame()
print(frame.columns)
print(frame["event"].to_physical().to_list())
```

**Output**

```text
['event']
[5, None]
```

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

## Initialization text and exact reconstruction

`to_init_repr` returns native Series initialization text. The example below
uses a microsecond date column and executes that text in a fixed namespace.
Standard Python datetime values have microsecond resolution. For storing
rsTimes dates with all ns digits, retain physical integer ticks, missingness
and the complete dtype, as shown afterwards.

For exact reconstruction, retain explicit integer ticks, validity, unit,
timezone and name. A Python list of physical ticks and None keeps the valid
values separate from missingness; it does not use a NumPy NaT sentinel.

See the [native Series export reference](https://docs.pola.rs/api/python/stable/reference/series/index.html)
for the provider's options, and [the rsTimes output guide](../guides/pldt-output.md)
for checked NumPy and standard Python precision boundaries.
