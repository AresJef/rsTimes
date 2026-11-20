# The inherited native Polars .dt namespace

## Read the native epoch coordinate

(ref-pldt-native-epoch)=
```python
from rstimes import Pldt

events = Pldt([0, 1_250_000_000, None], unit="ns", tz="UTC", name="event")
seconds = events.dt.epoch("s")
print(seconds.to_list())
```

**Output**

```text
[0, 1, None]
```

`Pldt.dt` is Polars' original temporal namespace. Its methods keep Polars
parameter names, result types and errors. They do not automatically use
`.pldt` rules. In particular, native `.dt` date results are ordinary Series,
native nanosecond is the complete fraction, weekday uses ISO numbering, and
native predicates propagate nulls.

The following examples call every inherited `.dt` method on an actual Pldt.
Literal calendar/physical answers were checked independently with a standalone
Polars Series. See the [upstream temporal API](https://docs.pola.rs/api/python/stable/reference/series/temporal.html)
for its complete parameter reference; dependency versions in this site's
verification record identify the actual behavior tested here.

## Native integer and Boolean fields

## Native date transformations and zone roles

Native field replacement is `.dt.replace`, native unit casting is
`.dt.cast_time_unit`, and whole-value replacement remains `Series.replace`.
`combine` uses the local date and retains the aware source zone in the tested
native API. It is not a promise of naive output. Converting a timezone keeps
the instant; replacing it reinterprets the clock. Native timezone replacement
uses the keyword `non_existent`, distinct from rsTimes' `nonexistent`.

Native casting can deliberately lose precision. Use the corresponding checked
rsTimes operation when its documented unit, capacity or localization rules are
needed. Native business calendars accept explicit week masks and holiday dates;
the example excludes Friday March 1, so Thursday February 29 moves to Monday
March 4 while keeping the clock.

## Text and Python scalar exits

Native strftime uses its own directives and fraction rules. `%f` is nine-digit
nanoseconds even on ms/us native storage, whereas rsTimes strftime uses six
digits for those units. The native `min`/`max` methods here return standard
Python datetime and intentionally limit fractions to microseconds.

## Duration totals reject a Datetime receiver

All seven visible `total_*` methods require Duration. They reject the Pldt
Datetime receiver with the same native error as a plain Datetime Series.
Subtracting dates produces the appropriate native Duration Series; the second
half demonstrates the methods on that supported dtype. This does not claim
Duration is a Pldt storage dtype.

The [rsTimes eager guide](../guides/pldt.md) and
[native output guide](../guides/pldt-output.md) cover the `.pldt` contract.
Do not interchange native and rsTimes namespace names based on similar spelling.

## Native namespace indexing protocol

`x.dt[item]` delegates to native Series indexing. A scalar returns a standard
Python datetime or None and therefore truncates nanoseconds to microseconds.
A slice or integer gather returns an ordinary native Series with its exact
date unit and null bitmap. Upstream's int-only method annotation does not fully
express the observed slice/gather runtime support.
