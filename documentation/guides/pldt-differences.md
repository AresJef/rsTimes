# Count boundaries or subtract dates

`x.pldt.diff(target, unit)` counts unit bucket crossings, self minus target.
It returns an Int64 Series with native nulls. `x.diff()` retains Polars' native
adjacent-element difference operation and returns Duration. Subtracting dates
also returns Duration, representing elapsed time at the common supported
precision. Select the operation for the question you need to answer.

## All boundary units

Numeric diff targets are seconds, independently of storage. Date targets retain
their own real unit; they are not first forced into the receiver's unit.
Calendar weeks use Monday starts. Subsecond boundaries use exact integer
coordinates, including before the epoch.

```{doctest} pldt-all-boundary-difference-units
>>> from datetime import datetime, timedelta, timezone
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt
>>> late = Pldt(['2024-02-01', None], name='event')
>>> early = '2024-01-31 23:59:59'
>>> expected = {'Y': 0, 'Q': 0, 'M': 1, 'W': 0, 'D': 1, 'h': 1, 'm': 1, 'min': 1, 's': 1, 'ms': 1000, 'us': 1000000, 'ns': 1000000000}
>>> for owner in (late.pldt, pl.Series(late).pldt):
...     for unit, count in expected.items():
...         result = owner.diff(early, unit)
...         assert type(result) is pl.Series and result.dtype == pl.Int64 and result.name == 'event'
...         assert result.to_list() == [count, None]
>>> for storage, scale in [('ms', 1000000), ('us', 1000), ('ns', 1)]:
...     source = Pldt([-86401, -1001, -1, 0, 1, 1001, 86401, None], unit=storage)
...     for unit, step in [('D', 86400000000000), ('h', 3600000000000), ('min', 60000000000), ('s', 1000000000), ('ms', 1000000), ('us', 1000), ('ns', 1)]:
...         assert source.pldt.diff(np.datetime64(0, 'ns'), unit).to_list() == [tick * scale // step for tick in [-86401, -1001, -1, 0, 1, 1001, 86401]] + [None]
>>> Pldt([2000000, None], unit='us').pldt.diff(1, 's').to_list()
[1, None]
>>> Pldt([1], unit='ns').pldt.diff(1e-9, 'ns').to_list()
[0]
```

## Inclusive counts, missingness, and int64 capacity

`absolute` is applied before the inclusive adjustment. `one` leaves the signed
count, `both` expands it one step away from zero, and `neither` removes one
step. At zero, `both` returns 1 and `neither` returns −1, including with
absolute=True. These are boundary-count rules, rather than interval slicing.
Capacity is checked after the final adjustment. A valid minimum result stays an
integer, independently of nulls.

```{doctest} pldt-inclusive-difference-and-capacity
>>> source = Pldt([-2, -1, 0, 1, 2, None], unit='ns')
>>> for absolute in (False, True):
...     for inclusive, adjustment in [('one', 0), ('both', 1), ('neither', -1)]:
...         counts = [abs(tick) if absolute else tick for tick in [-2, -1, 0, 1, 2]]
...         answer = [tick + (-adjustment if tick < 0 else adjustment) for tick in counts] + [None]
...         assert source.pldt.diff(np.datetime64(0, 'ns'), 'ns', absolute, inclusive).to_list() == answer
>>> minimum = Pldt([-2**63, None], unit='ns').pldt.diff(np.datetime64(0, 'ns'), 'ns')
>>> (minimum.to_list(), minimum.is_null().to_list())
([-9223372036854775808, None], [False, True])
>>> maximum = Pldt([2**63 - 1], unit='ns')
>>> maximum.pldt.diff(np.datetime64(-1, 'ns'), 'ns', inclusive='neither').to_list()
[9223372036854775807]
>>> for action in (lambda: maximum.pldt.diff(np.datetime64(-1, 'ns'), 'ns'), lambda: Pldt([-2**63], unit='ns').pldt.diff(0, 'ns', absolute=True)):
...     try:
...         action()
...     except OverflowError:
...         continue
...     raise AssertionError('an out-of-capacity final difference was returned')
>>> Pldt([0, None], unit='us').pldt.diff(np.datetime64('NaT', 'ns'), 'ns').to_list()
[None, None]
>>> Pldt([0], unit='ns').pldt.diff(np.datetime64(2**63 - 1, 's'), 'D').to_list() == [-((2**63 - 1) // 86400)]
True
```

## Awareness, row pairing, and errors

Aware comparisons use UTC buckets. Naive and aware nonmissing targets cannot
be mixed. Real timezone callbacks keep their original error. A scalar target
broadcasts; a collection must match the whole source length. Missing date
targets produce null differences, but invalid text and unsupported argument
types are still rejected when a source row is null.

```{doctest} pldt-difference-target-roles
>>> aware = Pldt(['1970-01-01 08:00', None], tz='Asia/Shanghai', name='event')
>>> target = datetime(1970, 1, 1, 5, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
>>> aware.pldt.diff(target, 'ns').to_list()
[0, None]
>>> dates = Pldt(['2024-01-01', '2024-01-02', None])
>>> dates.pldt.diff(iter(['2024-01-01', '2024-01-01', None]), 'D').to_list()
[0, 1, None]
>>> for action, error in [(lambda: aware.pldt.diff(0, 'D'), TypeError), (lambda: dates.pldt.diff(['2024-01-01'], 'D'), ValueError), (lambda: dates.pldt.diff(None, 'D', absolute=1), TypeError), (lambda: dates.pldt.diff(None, 'D', inclusive='bad'), ValueError), (lambda: Pldt([None]).pldt.diff('not a date', 'D'), ValueError), (lambda: Pldt([]).pldt.diff(True, 'D'), TypeError), (lambda: dates.pldt.diff(None, 'bad'), ValueError)]:
...     try:
...         action()
...     except error:
...         continue
...     raise AssertionError('invalid difference arguments were accepted')
>>> calls = []
>>> marker = RuntimeError('application timezone failed')
>>> class Target(datetime):
...     def utcoffset(self):
...         calls.append('offset')
...         raise marker
>>> try:
...     Pldt([None], tz='UTC').pldt.diff(Target(2024, 1, 1, tzinfo=timezone.utc), 'D')
... except RuntimeError as caught:
...     print(caught is marker, calls)
True ['offset']
```

## Native differences and elapsed duration

```{doctest} pldt-native-diff-versus-elapsed
>>> source = Pldt([1001, 2002, None], unit='us', name='event')
>>> adjacent = source.diff()
>>> (type(adjacent) is pl.Series, adjacent.dtype == pl.Duration('us'), adjacent.to_physical().to_list())
(True, True, [None, 1001, None])
>>> target = pl.Series('other', [1, 2, None], dtype=pl.Datetime('ns'))
>>> elapsed = source - target
>>> (type(elapsed) is pl.Series, elapsed.dtype == pl.Duration('ns'), elapsed.name, elapsed.to_physical().to_list())
(True, True, 'event', [1000999, 2001998, None])
```
