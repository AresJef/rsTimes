# Native numerical operations on a date Series

## Read the lower physical date bound

(ref-pldt-native-lower-bound)=
```python
from rstimes import Pldt

events = Pldt([1, None], unit="ns", name="event")
lower = events.lower_bound()
print(lower.to_list())
```

**Output**

```text
[-9223372036854775808]
```

Inherited Polars names do not all have the same date role. Many numeric
operations reject Datetime. Some work on physical ticks and return Float64,
and date-aware cumulative operations return native date Series. Their behavior
is distinct from rsTimes calendar transformations and elapsed differences.

The rejected calls below were independently checked on ordinary Polars Series
before being executed on Pldt. They supply valid numeric parameters; the
expected failure is the receiver's date dtype, rather than a missing argument.
The [Polars Series reference](https://docs.pola.rs/api/python/stable/reference/series/index.html)
provides the complete native parameter reference.

## Explicit date-dtype rejections

Every method named in these tables is called on an actual Pldt. Native
InvalidOperationError, SchemaError and TypeError remain distinct. In particular,
native `floor`, `ceil`, `round` and `truncate` are numerical operations; date
boundary operations are documented through the rsTimes namespace.

Calling `reinterpret()` with neither `signed` nor `dtype` is a different
argument error. The example above explicitly supplies `signed=True`, so it
checks the real nonnumeric-dtype restriction. Native `std` does not produce a
Timedelta for Pldt; the inherited pandas/Pddt reduction has different behavior.

## Unary plus, cumulative extrema and storage bounds

Unary plus returns Pldt with unchanged dates. `cum_max`, `cum_min` and
`shrink_dtype` return ordinary native Series in these verified calls. Cumulative
state continues across a null, while the output at that null remains null.
`lower_bound` and `upper_bound` return a one-element Int64 Series containing
the physical storage bounds, not a Datetime result with an attached unit.

Native scalar extrema return standard datetime with microsecond precision; the
123 ns tail in the maximum is deliberately absent at this scalar exit. Native
peak predicates have provider-specific boundary rules; do not infer a null
just because the row is at an endpoint. A missing data neighbor can produce
a null result, as verified below.

## Numerical kernels that accept physical date ticks

The following native kernels accept Datetime by treating its storage as
numbers. They do not perform calendar square roots, calendar cube roots, or
unit-independent date percentages. Float64 output has no timezone metadata and
can lose integer precision for large epoch ticks. The small ns ticks below make
the independent numerical answers explicit.

Both final inputs represent one second after the epoch, but their native square
roots differ because the stored tick units differ. For a numeric measurement,
convert to the desired elapsed unit explicitly and keep the original dates.

## Exponential weighting: numerical output and time-index restrictions

The ordinary native `ewm_*` kernels below accept date storage and return
Float64 tick statistics. With alpha 1/2, the two observed values 1 and 8 have
adjusted mean 17/3, exponentially weighted sum 8.5, and unbiased variance 24.5.
The output at a null stays null. `ignore_nulls` changes how a gap decays prior
weights.

By contrast, `ewm_mean_by` and `ewm_sum_by` require a numerical value Series
alongside their time index, and reject the Datetime value Series. Supplying a
valid Datetime `by` column does not change that value-dtype restriction.

## Reflected matrix protocol

```{py:method} rstimes.Pldt.__rmatmul__(other)
```

The direct inherited reflected matrix entry also rejects this date dtype.
Its presence is not a date-vector dot-product interface. For date comparisons,
choose an explicit rsTimes date difference and unit.
