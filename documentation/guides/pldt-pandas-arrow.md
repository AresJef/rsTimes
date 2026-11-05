# Exchange pandas and Arrow timestamps with Pldt

This page uses the optional pandas and PyArrow packages as well as Polars. A
pandas NumPy-backed date column uses NaT's reserved tick. An Arrow-backed
timestamp column instead has independent validity, just like Polars, and can
carry a valid int64 minimum. Pldt reads the actual declared timestamp type.

## pandas native dates

Series, Index, and DatetimeArray inputs keep their unit, timezone, and positional
order. Index labels do not align rows. Seconds become milliseconds. A declared
NaT remains null, and an empty typed input still supplies its date metadata.

```{doctest} pldt-pandas-native-input
>>> from datetime import date
>>> import numpy as np
>>> import pandas as pd
>>> import polars as pl
>>> import pyarrow as pa
>>> from rstimes import Pldt
>>> for unit, destination, expected in [('s', 'ms', [1000, None, -1000]), ('ms', 'ms', [1, None, -1]), ('us', 'us', [1, None, -1]), ('ns', 'ns', [1, None, -1])]:
...     index = pd.DatetimeIndex(np.array([1, -2**63, -1], dtype=f'datetime64[{unit}]'), tz='UTC', name='event')
...     for source in (index, pd.Series(index, index=['z', 'x', 'y'], name='event'), index.array):
...         result = Pldt(source)
...         assert type(result) is Pldt and result.dtype == pl.Datetime(destination, 'UTC')
...         assert result.to_physical().to_list() == expected
...     assert Pldt(index[:0]).dtype == pl.Datetime(destination, 'UTC')
>>> source = pd.Series(pd.DatetimeIndex(['2024-01-01'], tz='Asia/Shanghai'), name='event')
>>> converted = Pldt(source, tz='UTC')
>>> (converted.dtype.time_zone, converted.to_physical().to_list() == source.array.asi8.tolist())
('UTC', True)
```

## Arrow-backed timestamp inputs and return paths

Supply a real pandas Arrow-backed Series, Index, or extension array. For a raw
Arrow timestamp Array or ChunkedArray, first use `pl.from_arrow`; this makes its
unit, timezone, and null bitmap explicit. The example checks every supported
Polars unit with naive, UTC, and named-zone timestamps, including empty,
null-only, and full int64 endpoint columns.

```{doctest} pldt-arrow-timestamp-input
>>> def arrow_series(values, unit='ns', zone='UTC'):
...     dtype = pa.timestamp(unit, tz=zone)
...     return pd.Series(pa.array(values, type=dtype), dtype=pd.ArrowDtype(dtype), name='event')
>>> for unit in ('ms', 'us', 'ns'):
...     for zone in (None, 'UTC', 'Asia/Shanghai'):
...         for values in ([], [None, None], [1, None, -1], [-2**63, None, 2**63 - 1]):
...             series = arrow_series(values, unit, zone)
...             for source in (series, pd.Index(series.array, name='event'), series.array):
...                 for constructor in (Pldt, Pldt.parse):
...                     result = constructor(source)
...                     assert type(result) is Pldt and result.dtype == pl.Datetime(unit, zone)
...                     assert result.to_physical().to_list() == values
...                     assert result.is_null().to_list() == [value is None for value in values]
>>> raw = pa.chunked_array([pa.array([123, None], type=pa.timestamp('ns', tz='UTC')), pa.array([-2**63], type=pa.timestamp('ns', tz='UTC'))])
>>> result = Pldt(pl.from_arrow(raw, rechunk=False))
>>> (result.dtype == pl.Datetime('ns', 'UTC'), result.to_physical().to_list())
(True, [123, None, -9223372036854775808])
>>> for options in ({'use_pyarrow_extension_array': True}, {'types_mapper': pd.ArrowDtype}):
...     exported = result.to_pandas(**options)
...     assert isinstance(exported.dtype, pd.ArrowDtype)
...     restored = Pldt(exported)
...     assert restored.dtype == result.dtype
...     assert restored.to_physical().to_list() == [123, None, -2**63]
>>> seconds = Pldt(arrow_series([1, None, -1], 's'))
>>> (seconds.dtype == pl.Datetime('ms', 'UTC'), seconds.to_physical().to_list())
(True, [1000, None, -1000])
```

Choosing an Arrow export is useful when a valid minimum tick must survive. A
NumPy-backed pandas destination reserves that tick for NaT; Pldt rejects the
collision by default. See [output representations](pldt-output.md) for explicit
loss and copy options.

## Date and clock roles differ from conversion

Ordinary construction with a target timezone converts a known instant.
`fromdatetime(..., tz=...)` instead replaces the source clock's timezone.
`fromdate` selects the source calendar date, drops its clock and zone, and uses
midnight. The repeated hour below has two distinct source instants, both with a
123456789 nanosecond fraction.

```{doctest} pldt-arrow-factory-roles
>>> instants = [1730611800123456789, 1730615400123456789]
>>> repeated = arrow_series(instants, zone='America/New_York')
>>> Pldt(repeated, tz='UTC').to_physical().to_list() == instants
True
>>> Pldt.fromdatetime(repeated).to_physical().to_list() == instants
True
>>> Pldt.fromdatetime(repeated, tz='UTC').to_physical().to_list()
[1730597400123456789, 1730597400123456789]
>>> Pldt.fromdate(repeated).isoformat().to_list()
['2024-11-03T00:00:00', '2024-11-03T00:00:00']
>>> clock = arrow_series([1, None, 1001])
>>> combined = Pldt.combine([date(2024, 1, 1)] * 3, clock, unit='ns')
>>> (combined.dtype == pl.Datetime('ns', 'UTC'), combined.to_physical().to_list())
(True, [1704067200000000001, None, 1704067200000001001])
>>> for values in ([], [None, None]):
...     typed = arrow_series(values)
...     assert Pldt.fromdatetime(typed).dtype == pl.Datetime('ns', 'UTC')
...     assert Pldt.fromdate(typed).dtype == pl.Datetime('ns')
...     combined = Pldt.combine([date(2024, 1, 1)] * len(values), typed)
...     assert combined.dtype == pl.Datetime('us', 'UTC')
...     assert combined.to_physical().to_list() == values
```

## Capacity, real exporters, and source changes

Seconds-to-milliseconds scaling and explicit coarser units are checked before a
loss occurs. `fromdatetime64` is specifically for NumPy date sources. A genuine
Arrow exporter must return its declared timestamp dtype and keeps its own
exception object. It is called once for this input.

```{doctest} pldt-arrow-input-protocols
>>> for action, expected_error in (
...     (lambda: Pldt(arrow_series([2**63 - 1], 's')), OverflowError),
...     (lambda: Pldt(arrow_series([1]), unit='us'), ValueError),
...     (lambda: Pldt.fromdatetime64(arrow_series([1])), TypeError),
... ):
...     try:
...         action()
...     except expected_error:
...         continue
...     raise AssertionError('the source-role or precision check was bypassed')
>>> calls = []
>>> marker = RuntimeError('application Arrow export failed')
>>> class BrokenExport(pd.arrays.ArrowExtensionArray):
...     def __arrow_array__(self, *args, **kwargs):
...         calls.append('export')
...         raise marker
>>> try:
...     Pldt(BrokenExport(pa.array([1], type=pa.timestamp('ns'))))
... except RuntimeError as caught:
...     print(caught is marker, calls)
True ['export']
>>> class WrongExport(pd.arrays.ArrowExtensionArray):
...     def __arrow_array__(self, *args, **kwargs):
...         return pa.array([1], type=pa.int64())
>>> try:
...     Pldt(WrongExport(pa.array([1], type=pa.timestamp('ns'))))
... except TypeError as error:
...     print('declared dtype' in str(error))
True
>>> source = arrow_series([-2**63, 11, None]).iloc[::2]
>>> captured = Pldt(source, copy=False)
>>> source.iloc[0] = pd.Timestamp(7, unit='ns', tz='UTC')
>>> captured.to_physical().to_list()
[-9223372036854775808, None]
```

Arrow date32/date64 columns have a date role, rather than timestamp metadata.
They can supply calendar dates but are not accepted by `fromdatetime`.

```{doctest} pldt-arrow-date-role
>>> dtype = pd.ArrowDtype(pa.date32())
>>> dates = pd.Series(pa.array([date(2024, 1, 1), None], type=pa.date32()), dtype=dtype)
>>> Pldt(dates).to_physical().to_list()
[1704067200000, None]
>>> try:
...     Pldt.fromdatetime(dates)
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```
## pandas output and callback ownership

Default pandas output uses its NumPy-backed date representation. An explicit
collision opt-in can turn a valid minimum into NaT; other precision and validity
checks still apply. A real `types_mapper` callback runs against the captured
column. Appending to the receiver inside that callback does not change the
already exported rows. Callback exceptions retain their identity.

```{doctest} pldt-pandas-output-protocol
>>> ordinary = Pldt([0, None, 1], unit='ns', name='event')
>>> exported = ordinary.to_pandas()
>>> (type(exported) is pd.Series, exported.name, str(exported.dtype), exported.array.asi8.tolist())
(True, 'event', 'datetime64[ns]', [0, -9223372036854775808, 1])
>>> for unit in ('ms', 'us', 'ns'):
...     minimum = Pldt([-2**63, None, 1], unit=unit)
...     try:
...         minimum.to_pandas()
...     except OverflowError:
...         pass
...     else:
...         raise AssertionError('a valid tick became NaT without consent')
...     assert minimum.to_pandas(allow_nat_collision=np.bool_(True)).isna().tolist() == [True, True, False]
...     assert minimum.is_null().to_list() == [False, True, False]
>>> captured = Pldt([0, 1], unit='ns')
>>> callbacks = []
>>> def mapper(dtype):
...     callbacks.append(dtype)
...     returned = captured.append(Pldt([2], unit='ns'))
...     assert returned is captured
...     return pd.ArrowDtype(dtype)
>>> exported = captured.to_pandas(types_mapper=mapper)
>>> (len(callbacks), len(captured), pl.from_pandas(exported).to_physical().to_list())
(1, 3, [0, 1])
>>> marker = RuntimeError('application types mapper failed')
>>> callbacks = []
>>> def broken_mapper(dtype):
...     callbacks.append(dtype)
...     raise marker
>>> try:
...     ordinary.to_pandas(types_mapper=broken_mapper)
... except RuntimeError as caught:
...     print(caught is marker, len(callbacks))
True 1
>>> for action in (lambda: ordinary.to_pandas(unknown_keyword=True), lambda: ordinary.to_pandas(allow_nat_collision=1)):
...     try:
...         action()
...     except TypeError:
...         continue
...     raise AssertionError('unsupported export option was accepted')
```
