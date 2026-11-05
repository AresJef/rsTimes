# Bring native date buffers into Pldt

Read the declared unit and the real missing representation before converting a
column. NumPy reserves its minimum int64 date tick for NaT. Polars stores nulls in
a separate bitmap, so its minimum tick can be a valid date. Pldt follows the
source representation when reading it.

## NumPy dates, layout, and ownership

Native NumPy dates from years through nanoseconds are supported, including unit
multipliers. Seconds become milliseconds because Polars has no Datetime(s).
Calendar months use their actual first day, rather than a fixed average number
of seconds. Source NaT stays missing. A strided or nonnative byte-order array
retains its logical row order.

```{doctest} pldt-numpy-input-storage
>>> from datetime import date, datetime, timedelta
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt
>>> cases = [
...     ('s', [1, -1, -2**63], 'ms', [1000, -1000, None]),
...     ('us', [1, -1, -2**63], 'us', [1, -1, None]),
...     ('ns', [123, -123, -2**63], 'ns', [123, -123, None]),
...     ('10D', [0, 1, -1], 'ms', [0, 864000000, -864000000]),
...     ('M', [0, 1, 2], 'ms', [0, 2678400000, 5097600000]),
...     ('Y', [0, 1], 'ms', [0, 31536000000]),
... ]
>>> for unit, ticks, destination, expected in cases:
...     source = np.array(ticks, dtype=f'datetime64[{unit}]')
...     result = Pldt(source)
...     assert type(result) is Pldt and result.dtype == pl.Datetime(destination)
...     assert result.to_physical().to_list() == expected
>>> strided = np.array([1, 99, -1, 99, 2, 99], dtype='datetime64[us]')[::2]
>>> for source in (strided, strided.astype(strided.dtype.newbyteorder('S'))):
...     assert Pldt(source).to_physical().to_list() == [1, -1, 2]
>>> raw = np.array([1, 2], dtype=np.int64)
>>> captured = Pldt(raw, unit='ns', copy=False)
>>> raw[0] = 99
>>> captured.to_physical().to_list()
[1, 2]
>>> arrays = (np.array([], dtype='datetime64[ns]'), np.array(['NaT'], dtype='datetime64[us]'))
>>> [(Pldt(source).dtype == pl.Datetime(unit), Pldt(source).is_null().to_list()) for source, unit in zip(arrays, ('ns', 'us'))]
[(True, []), (True, [True])]
```

`copy=False` permits safe sharing; it does not promise that writable external
storage remains borrowed. Use `copy=True` when requesting explicit isolation.
Never infer buffer sharing from equal values or from a matching version label.

## Polars dates retain their own metadata

Date uses midnight and an inferred millisecond unit. Datetime keeps its unit,
zone, chunks, and validity, including empty or null-only columns. A constructor
result is an independent Series shell: appending to the original shell does not
extend the captured result.

```{doctest} pldt-native-column-storage
>>> for unit in ('ms', 'us', 'ns'):
...     for values in ([], [None, None], [-2**63, None, 2**63 - 1]):
...         source = pl.Series('event', values, dtype=pl.Datetime(unit, 'UTC'))
...         result = Pldt(source)
...         assert type(result) is Pldt and result.dtype == source.dtype
...         assert result.name == 'event' and result.to_physical().to_list() == values
...         assert result.is_null().to_list() == [value is None for value in values]
>>> chunks = pl.concat([pl.Series('event', [1, None], dtype=pl.Datetime('ns')), pl.Series('event', [2], dtype=pl.Datetime('ns'))], rechunk=False)
>>> captured = Pldt(chunks.slice(1, 2))
>>> returned = chunks.append(pl.Series('event', [3], dtype=chunks.dtype))
>>> (captured.to_physical().to_list(), returned is chunks)
([None, 2], True)
>>> source = pl.Series('day', [date(1970, 1, 2), None], dtype=pl.Date)
>>> (Pldt(source).dtype == pl.Datetime('ms'), Pldt(source).to_physical().to_list())
(True, [86400000, None])
>>> clock = pl.Series('clock', [34200000000123, None], dtype=pl.Int64).cast(pl.Time)
>>> combined = Pldt.combine([date(2024, 1, 2), date(2024, 1, 2)], clock, unit='ns')
>>> (combined.dtype == pl.Datetime('ns'), combined.isoformat(timespec='nanoseconds').to_list())
(True, ['2024-01-02T09:30:00.000000123', None])
>>> for invalid in (clock, pl.Series([1], dtype=pl.Duration('ns')), pl.Series([True]), pl.Series([[1]])):
...     try:
...         Pldt(invalid)
...     except TypeError:
...         continue
...     raise AssertionError('a non-date dtype was guessed to be a date')
```

Time has a clock role in `combine`, and Duration has an arithmetic role. Neither
is date data for the constructor. Use native integer physical values together
with `is_null()` when transporting valid minimum ticks; exporting only Python
datetime objects also limits years and precision.

## Explicit precision and capacity boundaries

Construction with `unit=` is lossless. Use `as_unit` to request a deliberate
coarser representation; its default floors negative values, too. Subnanosecond
NumPy dates and a destination outside int64 capacity are rejected.

```{doctest} pldt-input-conversion-errors
>>> fine = Pldt([1500, -1500, None], unit='ns')
>>> fine.as_unit('us').to_physical().to_list()
[1, -2, None]
>>> for action, expected_error in (
...     (lambda: Pldt(np.array([1500], dtype='datetime64[ns]'), unit='us'), ValueError),
...     (lambda: fine.as_unit('us', round_ok=False), ValueError),
...     (lambda: Pldt(np.array([2**63 - 1], dtype='datetime64[s]')), OverflowError),
...     (lambda: Pldt(np.array(['2500-01-01'], dtype='datetime64[us]'), unit='ns'), OverflowError),
...     (lambda: Pldt(np.array([1], dtype='datetime64[ps]')), ValueError),
...     (lambda: Pldt(np.array([[1]])), ValueError),
... ):
...     try:
...         action()
...     except expected_error:
...         continue
...     raise AssertionError('the conversion boundary was not enforced')
>>> fine.to_physical().to_list()
[1500, -1500, None]
```

For pandas and Arrow timestamp inputs, see the separate
[pandas and Arrow exchange guide](pldt-pandas-arrow.md).
