# Exchange pandas date columns

Use real dtype, unit, timezone, and missing metadata when moving a column.
Converting through Python datetime objects intentionally limits precision to
microseconds and years 1–9999; native NumPy, pandas, Polars, or Arrow exchanges
can retain the date column's nanoseconds.

## Native pandas and NumPy sources

Temporal columns keep their actual unit and timezone, including empty sources.
`copy=True` requests isolation from a mutable input array. A noncontiguous
one-dimensional array is supported without changing its row order.

```{doctest} pddt-native-pandas-numpy-exchange
>>> from datetime import date, datetime, timedelta, timezone
>>> import numpy as np
>>> import pandas as pd
>>> import polars as pl
>>> import pyarrow as pa
>>> from rstimes import Pddt, Delta
>>> original = np.array([1, 2, 'NaT'], dtype='datetime64[ns]')
>>> isolated = Pddt(original, copy=True, name='event')
>>> original[0] = np.datetime64(999, 'ns')
>>> (isolated.asi8.tolist(), isolated.unit, isolated.name)
([1, 2, -9223372036854775808], 'ns', 'event')
>>> strided = np.array([0, 100, 1, 100, 2, 100], dtype='datetime64[us]')[::2]
>>> (Pddt(strided).unit, Pddt(strided).asi8.tolist())
('us', [0, 1, 2])
>>> swapped = strided.astype(strided.dtype.newbyteorder('S'))
>>> Pddt(swapped).asi8.tolist()
[0, 1, 2]
>>> native = pd.DatetimeIndex(np.array([123, 'NaT'], dtype='datetime64[ns]'), tz='UTC', name='event')
>>> for source in (native, native.to_series(index=pd.RangeIndex(2)), native.array):
...     result = Pddt(source)
...     assert type(result) is Pddt and result.unit == 'ns' and str(result.tz) == 'UTC'
...     assert result.asi8.tolist() == [123, -9223372036854775808]
>>> empty = Pddt(native[:0])
>>> (len(empty), empty.unit, str(empty.tz), empty.name)
(0, 'ns', 'UTC', 'event')
```

## Polars Date, Datetime, Time, and Duration

Construction accepts supported native Series. Date values use midnight and
Datetime retains its unit, region, and null mask. Time is meaningful only in a
clock role such as `combine(time=...)`; it is not a date by itself. A Duration
Series is an arithmetic operand, rather than constructor date data.

```{doctest} pddt-polars-native-exchange
>>> temporal = pl.Series('event', [123, None], dtype=pl.Int64).cast(pl.Datetime('ns', 'UTC'))
>>> result = Pddt(temporal)
>>> (type(result) is Pddt, result.unit, str(result.tz), result.name, result.asi8.tolist())
(True, 'ns', 'UTC', 'event', [123, -9223372036854775808])
>>> dates = pl.Series('day', [date(2024, 2, 29), None], dtype=pl.Date)
>>> (Pddt.fromdate(dates).unit, Pddt.fromdate(dates).day.tolist())
('s', [29.0, nan])
>>> fields = Pddt.fromdatetime(temporal, tz='Asia/Shanghai')
>>> (fields.unit, fields.isoformat().dropna().tolist())
('ns', ['1970-01-01T00:00:00.000000123+08:00'])
>>> clocks = pl.Series('clock', [34200000000123, None], dtype=pl.Int64).cast(pl.Time)
>>> combined = Pddt.combine(date(2024, 1, 2), clocks)
>>> (combined.unit, combined.isoformat().dropna().tolist(), combined.isna().tolist())
('ns', ['2024-01-02T09:30:00.000000123'], [False, True])
>>> durations = pl.Series([1, None], dtype=pl.Duration('ns'))
>>> (Pddt([0, 1], unit='ns') + durations).asi8.tolist()
[1, -9223372036854775808]
>>> for invalid in (clocks, pl.DataFrame({'date': temporal}), pl.LazyFrame({'date': temporal})):
...     try:
...         Pddt(invalid)
...     except TypeError:
...         continue
...     raise AssertionError('unsupported date container was guessed')
```

Polars has an independent null bitmap, so int64 minimum can be a valid date.
Pandas reserves that bit pattern for NaT. Pddt rejects a valid Polars date that
would collide with the destination sentinel instead of silently making it
missing. Keep that value in a representation capable of expressing it.

```{doctest} pddt-valid-minimum-collision
>>> valid_minimum = pl.Series([-2**63, None], dtype=pl.Int64).cast(pl.Datetime('ns'))
>>> (valid_minimum.is_null().to_list(), valid_minimum.cast(pl.Int64).to_list())
([False, True], [-9223372036854775808, None])
>>> try:
...     Pddt(valid_minimum)
... except OverflowError as error:
...     print(type(error).__name__, 'reserved NaT' in str(error))
OverflowError True
```

## Arrow and native output

Arrow can read Pddt's pandas date column with its exact timestamp type and
validity. A pandas Arrow-backed timestamp Series also supplies supported
datetime values to Pddt. A raw Arrow Array instead iterates Arrow scalar objects;
those scalars are outside Pddt's accepted date-element protocol. Wrap the actual
Arrow timestamp dtype in pandas when that is the source you have.

```{doctest} pddt-arrow-and-polars-output
>>> source = Pddt([123, None], unit='ns', tz='UTC', name='event')
>>> arrow = pa.array(source)
>>> (arrow.type == pa.timestamp('ns', tz='UTC'), arrow.cast(pa.int64()).to_pylist(), arrow.null_count)
(True, [123, None], 1)
>>> wrapped = pd.Series(arrow, dtype=pd.ArrowDtype(arrow.type), name='arrow')
>>> restored = Pddt(wrapped)
>>> (restored.unit, str(restored.tz), restored.name, restored.asi8.tolist())
('ns', 'UTC', 'arrow', [123, -9223372036854775808])
>>> try:
...     Pddt(arrow)
... except TypeError as error:
...     print(type(error).__name__, 'data[0]' in str(error))
TypeError True
>>> series = pl.from_pandas(source.to_series(index=pd.RangeIndex(len(source))))
>>> (type(series) is pl.Series, series.dtype == pl.Datetime('ns', 'UTC'), series.name, series.cast(pl.Int64).to_list())
(True, True, 'event', [123, None])
>>> Pddt(series).asi8.tolist() == source.asi8.tolist()
True
```

## Real callbacks and unsupported adapters

Plain dateutil relativedelta is not an additional Pddt operand. Convert an
applicable one to Delta explicitly, following
[Delta's adapter restrictions](delta-interop.md). A genuine Delta subclass
arithmetic override still owns its result. Input iterators are consumed once
and retain their original exception objects.

```{doctest} pddt-real-protocol-boundaries
>>> from dateutil.relativedelta import relativedelta
>>> sample = Pddt(['2024-01-31'])
>>> try:
...     sample + relativedelta(months=1)
... except TypeError as error:
...     print(type(error).__name__)
TypeError
>>> (sample + Delta.from_relativedelta(relativedelta(months=1))).day.tolist()
[29]
>>> calls = []
>>> class BusinessAdjustment(Delta):
...     def __radd__(self, other):
...         calls.append(type(other))
...         return 'application column result'
>>> sample + BusinessAdjustment(days=1)
'application column result'
>>> calls == [Pddt]
True
>>> marker = RuntimeError('input iterator stopped')
>>> def values():
...     yield '2024-01-01'
...     raise marker
>>> try:
...     Pddt(values())
... except RuntimeError as caught:
...     print(caught is marker)
True
```
