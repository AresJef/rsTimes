# Native tensor and plotting exits

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

```{doctest} inherited-pldt-jax-export
>>> import jax
>>> import polars as pl
>>> from rstimes import Pldt
>>> def error_name(call):
...     try:
...         call()
...     except Exception as error:
...         return type(error).__name__
...     raise AssertionError('an error was required')
>>> value = Pldt(pl.Series('event', [1704067200000000123, None, -9223372036854775808], dtype=pl.Datetime('ns', 'UTC')))
>>> ordinary_dates = Pldt(pl.Series('event', [1704067200000000123, None], dtype=value.dtype))
>>> error_name(ordinary_dates.to_jax)
'TypeError'
>>> error_name(value.to_jax)
'OverflowError'
>>> jax.config.update('jax_enable_x64', False)
>>> error_name(lambda: value.to_physical().fill_null(0).to_jax(device='cpu'))
'InvalidOperationError'
>>> jax.config.update('jax_enable_x64', True)
>>> physical = value.to_physical().fill_null(0)
>>> valid = value.is_not_null()
>>> ticks = physical.to_jax(device='cpu')
>>> validity = valid.to_jax(device='cpu')
>>> (isinstance(ticks, jax.Array), str(ticks.dtype), ticks.tolist())
(True, 'int64', [1704067200000000123, 0, -9223372036854775808])
>>> (isinstance(validity, jax.Array), str(validity.dtype), validity.tolist())
(True, 'bool', [True, False, True])
>>> metadata = {'unit': 'ns', 'timezone': 'UTC', 'name': 'event'}
>>> restored_values = [int(tick) if present else None for tick, present in zip(ticks.tolist(), validity.tolist())]
>>> restored = Pldt(pl.Series(metadata['name'], restored_values, dtype=pl.Datetime(metadata['unit'], metadata['timezone'])))
>>> (restored.dtype == value.dtype, restored.to_physical().to_list())
(True, [1704067200000000123, None, -9223372036854775808])
```

The zero used to fill a tensor slot is arbitrary storage for an invalid row.
The Boolean mask determines validity. It never changes the valid minimum
int64 tick into a missing date. The original timezone and unit must accompany
the tensor if dates are to be reconstructed.

## PyTorch: integer and Boolean tensors

The native direct ordinary-Datetime exit raises TypeError because NumPy datetime data
is not a supported PyTorch tensor dtype. Physical int64 and Boolean Series
have supported tensor roles. This example verifies exact integer values and
an independent mask; it makes no promise of buffer sharing or GPU placement.

```{doctest} inherited-pldt-torch-export
>>> import torch
>>> error_name(ordinary_dates.to_torch)
'TypeError'
>>> error_name(value.to_torch)
'OverflowError'
>>> tensor = physical.to_torch()
>>> tensor_valid = valid.to_torch()
>>> (isinstance(tensor, torch.Tensor), tensor.dtype == torch.int64, tensor.tolist())
(True, True, [1704067200000000123, 0, -9223372036854775808])
>>> (isinstance(tensor_valid, torch.Tensor), tensor_valid.dtype == torch.bool, tensor_valid.tolist())
(True, True, [True, False, True])
>>> value.to_physical().to_list()
[1704067200000000123, None, -9223372036854775808]
```

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

```{doctest} inherited-pldt-plotting
>>> import altair as alt
>>> plot_dates = Pldt(pl.Series('event', [1704067200000000123, None, 1704240000000000000], dtype=pl.Datetime('ns', 'UTC')))
>>> chart = plot_dates.plot.line()
>>> specification = chart.to_dict()
>>> (isinstance(chart, alt.Chart), specification['mark']['type'], specification['encoding']['y']['type'])
(True, 'line', 'temporal')
>>> data = specification['datasets'][specification['data']['name']]
>>> [(row['index'], row['event']) for row in data]
[(0, '2024-01-01T00:00:00.000000123+0000'), (1, None), (2, '2024-01-03T00:00:00+0000')]
>>> native_hist = plot_dates.plot.hist()
>>> hist_spec = native_hist.to_dict()
>>> (isinstance(native_hist, alt.Chart), hist_spec['mark']['type'], hist_spec['encoding']['x']['type'], hist_spec['encoding']['x']['bin'])
(True, 'bar', 'quantitative', True)
>>> native_kde = plot_dates.plot.kde()
>>> kde_spec = native_kde.to_dict()
>>> (isinstance(native_kde, alt.Chart), kde_spec['mark']['type'], kde_spec['transform'][0]['density'])
(True, 'area', 'event')
>>> seconds = ((plot_dates.to_physical() // 1000000000) - 1704067200).rename('elapsed_seconds')
>>> seconds.to_list()
[0, None, 172800]
>>> histogram = seconds.plot.hist()
>>> density = seconds.plot.kde()
>>> (histogram.to_dict()['encoding']['x']['field'], density.to_dict()['transform'][0]['density'])
('elapsed_seconds', 'elapsed_seconds')
```

These Python methods return chart specifications; rendering is performed by
Altair/Vega in the chosen frontend. The checks above verify object types,
encodings and embedded date/null data. They do not turn date-column histogram
or density specifications into unit-aware statistical computations. See the
[Polars plotting API](https://docs.pola.rs/api/python/stable/reference/series/plot.html)
and [Altair documentation](https://altair-viz.github.io/) for frontend display
and export options.
