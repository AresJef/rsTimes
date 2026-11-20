# Native tensor and plotting exits

## Export precise ticks and a mask to PyTorch

(ref-pldt-torch-integer-ticks)=
```python
from rstimes import Pldt

events = Pldt([123456789, None], unit="ns", tz="UTC")
ticks = events.to_physical().fill_null(0).to_torch()
valid = events.is_not_null().to_torch()
print(ticks.tolist(), valid.tolist())
```

**Output**

```text
[123456789, 0] [True, False]
```

These inherited Polars APIs need their own optional libraries: JAX for
`to_jax`, PyTorch for `to_torch`, and a compatible Altair for `.plot`. They are
not rsTimes runtime requirements or rsTimes extras. The verified optional
profiles use JAX/jaxlib 0.12.0.1, PyTorch 2.15.0 and Altair 6.3.0 with Polars
2.0.0 or 2.1.0. Install appropriate packages for your own platform using their
upstream installation instructions.

A tensor does not carry Datetime unit, timezone or independent null validity.
Direct Datetime conversion is rejected by both tensor exits in these profiles.
For an ordinary date column the dtype rejection is TypeError; a valid minimum
int64 date tick triggers Pldt's NumPy sentinel-collision protection first and
raises OverflowError instead.
For an integer tensor, explicitly export physical ticks, keep the unit/zone as
metadata, and export a separate validity mask. Do not equate a valid int64
minimum tick with a missing row.

## JAX: explicit 64-bit ticks and separate validity

JAX's default configuration can disable 64-bit integers. The tested Polars
exit then attempts an int32 cast and rejects these large epoch ticks with
InvalidOperationError. Enable JAX's 64-bit mode before the integer export.
This is a configuration change in the example process, not a package setting
that rsTimes changes for users.

The zero used to fill a tensor slot is arbitrary storage for an invalid row.
The Boolean mask determines validity. It never changes the valid minimum
int64 tick into a missing date. The original timezone and unit must accompany
the tensor if dates are to be reconstructed.

## PyTorch: integer and Boolean tensors

The native direct ordinary-Datetime exit raises TypeError because NumPy datetime data
is not a supported PyTorch tensor dtype. Physical int64 and Boolean Series
have supported tensor roles. This example verifies exact integer values and
an independent mask; it makes no promise of buffer sharing or GPU placement.

## Altair chart objects and native plotting defaults

Read `.plot` as a namespace. Its `line`, `hist` and `kde` methods return Altair
Chart objects and accept Altair encoding keyword arguments. The chart object's
data and schema are inspected below. Date `line` uses temporal encoding.
The native histogram helper always requests a quantitative bin, and the KDE
helper builds a density transform; their generic availability does not make a
Datetime column a numeric histogram/density measurement.

Use explicit relative elapsed values and label their units for numeric charts.
The final example deliberately uses whole elapsed seconds, discarding fractions
for that plotted measurement. Preserve the original date column for exact ns
work. A visual chart is not an exact integer or timezone data interchange.

These Python methods return chart specifications; rendering is performed by
Altair/Vega in the chosen frontend. The checks above verify object types,
encodings and embedded date/null data. They do not turn date-column histogram
or density specifications into unit-aware statistical computations. See the
[Polars plotting API](https://docs.pola.rs/api/python/stable/reference/series/plot.html)
and [Altair documentation](https://altair-viz.github.io/) for frontend display
and export options.
