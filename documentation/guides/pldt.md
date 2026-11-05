# Native Polars dates with Pldt

Pldt is a real Polars Series subclass containing native Datetime data. It uses
`ms`, `us`, or `ns` storage and an independent null bitmap. Import Pldt to
register `.pldt` on native Polars Series and Expr. Core date calculations need
Polars and NumPy; pandas, Arrow, and dateutil are optional integrations.

Pldt construction is eager. A Series namespace also returns an eager date
result; an Expr namespace returns an ordinary Polars Expr whose rows must be
executed. See [expression workflows](expressions.md) for actual lazy collection.

## Native types, ticks, and null validity

```{doctest} pldt-native-construction
>>> from datetime import date, datetime, timedelta, timezone
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt, Configs
>>> value = Pldt([1, -1, None], unit='ns', name='event')
>>> (type(value) is Pldt, isinstance(value, pl.Series), value.dtype, value.name, value.to_physical().to_list())
(True, True, Datetime(time_unit='ns', time_zone=None), 'event', [1, -1, None])
>>> for unit in ('ms', 'us', 'ns'):
...     result = Pldt([1, -1, None], unit=unit, name='event')
...     assert type(result) is Pldt and result.dtype == pl.Datetime(unit)
...     assert result.to_physical().to_list() == [1, -1, None] and result.is_null().to_list() == [False, False, True]
>>> (Pldt([1]).dtype == pl.Datetime('ns'), Pldt([1.0]).to_physical().to_list())
(True, [1])
>>> minimum = Pldt([-2**63, None], unit='ns')
>>> (minimum.to_physical().to_list(), minimum.is_null().to_list())
([-9223372036854775808, None], [False, True])
>>> try:
...     minimum.to_numpy()
... except OverflowError as error:
...     print(type(error).__name__, 'NaT reserved tick' in str(error))
OverflowError True
>>> lossy = minimum.to_numpy(allow_nat_collision=True)
>>> (lossy.dtype, np.isnat(lossy).tolist())
(dtype('<M8[ns]'), [True, True])
```

Pandas/NumPy datetime buffers reserve int64 minimum for NaT. Pldt does not.
Allowing a collision is an explicit loss: it makes a valid minimum value
indistinguishable from missing in that destination. It does not allow ordinary
overflow or unrelated precision loss. Arrow can carry a separate validity map.

## Ordered one-dimensional input

Lists, tuples, one-dimensional NumPy arrays, supported native Series, and
single-use ordered iterables are accepted according to their actual elements.
Mappings, sets, tables, Expr, nested rows, and zero/two-dimensional arrays are
rejected. A scalar belongs in `[value]` or a named factory with `size`.

```{doctest} pldt-containers-and-shape
>>> for data in ([0, 1, None], (0, 1, None), iter([0, 1, None]), pl.Series('source', [0, 1, None])):
...     result = Pldt(data, unit='ms')
...     assert type(result) is Pldt and result.to_physical().to_list() == [0, 1, None]
>>> native = pl.Series('source', [123, None], dtype=pl.Int64).cast(pl.Datetime('ns', 'UTC'))
>>> (Pldt(native).dtype, Pldt(native).name, Pldt(native).to_physical().to_list())
(Datetime(time_unit='ns', time_zone='UTC'), 'source', [123, None])
>>> Pldt(native, name='').name
''
>>> sliced = np.array([0, 100, 1, 100, 2, 100], dtype='datetime64[us]')[::2]
>>> Pldt(sliced).to_physical().to_list()
[0, 1, 2]
>>> Pldt(sliced.astype(sliced.dtype.newbyteorder('S'))).to_physical().to_list()
[0, 1, 2]
>>> invalids = [(None, TypeError), ('2024-01-01', TypeError), (0, TypeError), ({0: 'date'}, TypeError), ({0, 1}, TypeError), (pl.DataFrame({'date': native}), TypeError), (pl.col('date'), TypeError), (np.array(0), ValueError), (np.array([[0]]), ValueError), ([[0]], TypeError)]
>>> for data, exception in invalids:
...     try:
...         Pldt(data)
...     except exception:
...         continue
...     raise AssertionError('unsupported shape was guessed')
>>> for data in ([True], pl.Series([True]), [b'2024-01-01']):
...     try:
...         Pldt(data)
...     except TypeError:
...         continue
...     raise AssertionError('unsupported date element accepted')
```

## Resolution comes from the source

Bare numbers mean ticks at the explicit unit, or ns when omitted. Ordinary
date text and Python datetime use us; seven-to-nine fractional text digits
declare ns even when the tail is zero. Dates and native seconds map to ms,
because Polars has no Datetime(s). Mixed input selects the finer required unit
once. Later date operations keep that chosen unit.

```{doctest} pldt-source-resolution
>>> sources = [(['1970-01-01'], 'us'), (['1970-01-01T00:00:00.123456000'], 'ns'), ([date(1970, 1, 1)], 'ms'), ([datetime(1970, 1, 1)], 'us'), (np.array([1], dtype='datetime64[s]'), 'ms')]
>>> for data, unit in sources:
...     assert Pldt(data).dtype == pl.Datetime(unit)
>>> Pldt(np.array([1, -1, 'NaT'], dtype='datetime64[s]')).to_physical().to_list()
[1000, -1000, None]
>>> mixed = Pldt([date(1970, 1, 1), datetime(1970, 1, 1, 0, 0, 1), np.datetime64(123, 'ns'), None])
>>> (mixed.dtype, mixed.to_physical().to_list())
(Datetime(time_unit='ns', time_zone=None), [0, 1000000000, 123, None])
>>> for call, exception in ((lambda: Pldt([0], unit='s'), ValueError), (lambda: Pldt([0], unit=1), TypeError), (lambda: Pldt(['1970-01-01T00:00:00.000000123'], unit='us'), ValueError), (lambda: Pldt(['2500-01-01'], unit='ns'), OverflowError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid resolution accepted')
>>> limit = (2**63 - 1) // 1000
>>> Pldt(np.array([limit], dtype='datetime64[s]')).to_physical().to_list()
[9223372036854775000]
>>> try:
...     Pldt(np.array([limit + 1], dtype='datetime64[s]'))
... except OverflowError as error:
...     print(type(error).__name__)
OverflowError
```

## Missing data and empty metadata

Explicit missing dates retain their row positions. Exact whole-text markers
are supported; whitespace and arbitrary case variants are not automatically
normalized into null. Empty or untyped missing-only input defaults to ms.
Declared native date/numeric resolution still matters for empty or missing data.

```{doctest} pldt-missing-and-empty
>>> markers = [None, np.nan, '', 'NaT', 'NAT', 'nat', 'NaN', 'NAN', 'nan', np.datetime64('NaT', 'ns')]
>>> for strict in (False, True):
...     result = Pldt(markers, unit='ns', strict=strict)
...     assert result.dtype == pl.Datetime('ns') and result.is_null().to_list() == [True] * 10
>>> defaults = [(Pldt([]), 'ms'), (Pldt([None, np.nan]), 'ms'), (Pldt(np.array([], dtype='float64')), 'ns'), (Pldt(np.array([np.nan])), 'ns'), (Pldt(np.array([], dtype='datetime64[ns]')), 'ns'), (Pldt([np.datetime64('NaT', 'ns')]), 'ns')]
>>> assert all(result.dtype == pl.Datetime(unit) for result, unit in defaults)
>>> empty = Pldt(pl.Series('event', [], dtype=pl.Datetime('ns', 'UTC')))
>>> (len(empty), empty.dtype, empty.name)
(0, Datetime(time_unit='ns', time_zone='UTC'), 'event')
>>> for text in (' ', 'None', 'null', 'nAt', ' NaT '):
...     try:
...         Pldt([text])
...     except ValueError:
...         continue
...     raise AssertionError('bad text was coerced to null')
```

## Active unit conversion and ownership

`as_unit` defaults to `round_ok=True`, allowing an explicit move to the earlier
coarser tick. False requires exact preservation. It keeps name, timezone, and
null positions. `copy=True` isolates source data. `copy=False` permits safe
sharing and does not promise universal zero-copy or protection from arbitrary
external raw-pointer writes.

Pldt follows Polars' mutable Series shell model. A separately constructed
result owns its own shell; appending to the source does not replace that shell.

```{doctest} pldt-unit-and-source-ownership
>>> fine = Pldt([-1500, 1500, None], unit='ns', name='event')
>>> coarse = fine.as_unit('us')
>>> native_coarse = pl.Series(fine).pldt.as_unit('us')
>>> (type(native_coarse) is Pldt, native_coarse.dtype == pl.Datetime('us'), native_coarse.to_physical().to_list())
(True, True, [-2, 1, None])
>>> (type(coarse) is Pldt, coarse.dtype, coarse.name, coarse.to_physical().to_list())
(True, Datetime(time_unit='us', time_zone=None), 'event', [-2, 1, None])
>>> try:
...     fine.as_unit('us', round_ok=False)
... except ValueError as error:
...     print(type(error).__name__)
ValueError
>>> original = np.array([1, 2], dtype='datetime64[ns]')
>>> isolated = Pldt(original, copy=True)
>>> original[0] = np.datetime64(999, 'ns')
>>> isolated.to_physical().to_list()
[1, 2]
>>> native = pl.Series('event', [1, 2], dtype=pl.Datetime('ns'))
>>> captured = Pldt(native, copy=False)
>>> appended = native.append(pl.Series('event', [3], dtype=pl.Datetime('ns')))
>>> (appended is native, captured.to_physical().to_list(), native.to_physical().to_list())
(True, [1, 2], [1, 2, 3])
>>> for call, exception in ((lambda: Pldt([], copy=1), TypeError), (lambda: fine.as_unit('us', round_ok=1), TypeError), (lambda: Pldt([0], name=1), TypeError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid option accepted')
```

## Shared parsing with column-specific defaults

`Pldt.parse` matches the constructor contract. Explicit ordering options win
over Configs, and recognized source zones are retained rather than silently
discarded. Complete defaults supply only missing text Y/M/D fields, not clocks,
zones, nanoseconds, or fold. `strict` is separate from column DST strategies.

```{doctest} pldt-parser-options
>>> config = Configs(dayfirst=True)
>>> config.add_month('harvest', 10)
True
>>> parsed = Pldt.parse(['01/02/2024', '7 harvest 2024', None], cfg=config)
>>> (type(parsed) is Pldt, parsed.month.to_list(), parsed.is_null().to_list())
(True, [2, 10, None], [False, False, True])
>>> Pldt(['01/02/2024'], cfg=config, dayfirst=False).month.to_list()
[1]
>>> Pldt(['February 29'], default=datetime(2024, 1, 1, 12, tzinfo=timezone.utc)).isoformat().to_list()
['2024-02-29T00:00:00']
>>> (len(Pldt([], default=object())), Pldt([0], default=object()).to_physical().to_list())
(0, [0])
>>> Pldt(['2024-02-31']).day.to_list()
[29]
>>> try:
...     Pldt(['2024-02-31'], strict=True)
... except ValueError as error:
...     print(type(error).__name__)
ParseError
>>> for option in ('strict', 'isoformat', 'yearfirst', 'dayfirst'):
...     try:
...         Pldt([], **{option: 1})
...     except TypeError:
...         continue
...     raise AssertionError(option)
```

The registered accessor also parses a real native String column. Explicit units
make the intended storage visible; parser configuration still owns token and
date-order rules. Unit conversion on prepared dates keeps instants and timezone.

```{doctest} pldt-native-series-parser-and-units
>>> native_text = pl.Series('event', ['01/02/2024', None])
>>> parsed = native_text.pldt.parse(unit='ns', cfg=config)
>>> (type(parsed) is Pldt, parsed.name, parsed.dtype == pl.Datetime('ns'), parsed.month.to_list())
(True, 'event', True, [2, None])
>>> units = [('ms', 1000), ('us', 1000000), ('ns', 1000000000)]
>>> for unit, scale in units:
...     original = Pldt([scale, -scale, None], unit=unit, tz='UTC', name='event')
...     for target, target_scale in units:
...         for owner in (original, pl.Series(original).pldt):
...             result = owner.as_unit(target, round_ok=False)
...             assert type(result) is Pldt and result.dtype == pl.Datetime(target, 'UTC') and result.name == 'event'
...             assert result.to_physical().to_list() == [target_scale, -target_scale, None]
```
