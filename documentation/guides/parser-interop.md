# Parse native scalar inputs

Use `parse` when you need a datetime object and `parse_to_epoch` when you need
exact integer ticks. Their result destinations have different precision and
capacity. A pandas Timestamp is a datetime input; a Polars Series is a separate
column input supported by the single-value epoch adapter.

## pandas Timestamp precision

The integer result reads the Timestamp's real ticks and unit. Converting it
to a standard datetime instead retains the microsecond fields available to
that destination, without inventing a nanosecond attribute.

```{doctest} parser-pandas-precision
>>> from datetime import datetime, timedelta, timezone, tzinfo
>>> import pandas as pd
>>> from rstimes import parse, parse_to_epoch
>>> source = pd.Timestamp(123, unit='ns', tz='UTC')
>>> plain = parse(source)
>>> (type(plain) is datetime, plain.microsecond, plain.utcoffset() == timedelta(0))
(True, 0, True)
>>> (type(parse_to_epoch(source, unit='ns')) is int, parse_to_epoch(source, unit='ns'))
(True, 123)
>>> regional = source.tz_convert('Asia/Shanghai')
>>> (parse_to_epoch(regional, unit='ns'), parse_to_epoch(regional, unit='ns', ignoretz=True))
(123, 28800000000123)
>>> for missing in (pd.NaT,):
...     try:
...         parse_to_epoch(missing)
...     except ValueError:
...         continue
...     raise AssertionError('NaT is not an epoch value')
```

## One-value Polars Datetime Series

The epoch adapter accepts exactly one non-null value in a real Polars Datetime
Series. It preserves the unit and nanosecond tail. `ignoretz=False` reads the
instant; `True` reads the local clock without its zone offset.

```{doctest} parser-polars-epoch
>>> import polars as pl
>>> column = pl.Series('event', [123], dtype=pl.Datetime('ns', 'UTC'))
>>> regional = column.dt.convert_time_zone('Asia/Shanghai')
>>> (parse_to_epoch(column, unit='ns'), parse_to_epoch(regional, unit='ns'))
(123, 123)
>>> parse_to_epoch(regional, unit='ns', ignoretz=True)
28800000000123
>>> parse_to_epoch(column, unit='ns', input_unit='ms')
123
```

`input_unit` changes numeric input, not a native Datetime column's own unit.
This adapter is not a batch parser. A null value or a Series of length other
than one raises `ValueError`; a non-Datetime Series raises `TypeError`.
`parse()` does not accept a Series as a scalar datetime input. Use Pldt or its
namespace for whole-column work.

```{doctest} parser-polars-rejections
>>> from datetime import date
>>> invalid_columns = ((pl.Series([], dtype=pl.Datetime('ns')), ValueError), (pl.Series([0, 1], dtype=pl.Datetime('ns')), ValueError), (pl.Series([None], dtype=pl.Datetime('ns')), ValueError), (pl.Series([1]), TypeError), (pl.Series([date(2024, 1, 1)], dtype=pl.Date), TypeError))
>>> for column, expected in invalid_columns:
...     try:
...         parse_to_epoch(column)
...     except expected:
...         continue
...     raise AssertionError(column.dtype)
>>> try:
...     parse(pl.Series([0], dtype=pl.Datetime('ns')))
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```

## Fixed offsets and real timezone callbacks

Offsets can include their supported second and microsecond components. They
are not rounded into a guessed region or host-local abbreviation. A callback
inside an actual timezone object keeps its original exception.

```{doctest} parser-offset-and-callback
>>> offset = timezone(timedelta(hours=5, minutes=30, seconds=1, microseconds=500000))
>>> value = datetime(1970, 1, 1, tzinfo=offset)
>>> parse_to_epoch(value, unit='ns')
-19801500000000
>>> failure = RuntimeError('application timezone failed')
>>> class BusinessZone(tzinfo):
...     def utcoffset(self, value):
...         raise failure
>>> value = datetime(2024, 1, 1, tzinfo=BusinessZone())
>>> try:
...     parse_to_epoch(value)
... except RuntimeError as error:
...     print(error is failure)
True
```

NumPy arrays and NumPy timedelta64 values do not become scalar parser dates.
Date-like scalar and one-dimensional date-column workflows have separate
entry points. See the [parsing guide](parsing.md) for scalar defaults, errors,
and result constructors.
