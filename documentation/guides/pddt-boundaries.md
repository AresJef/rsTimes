# Column boundaries, rounding, and calendar queries

Boundary transformations keep the Pddt unit, timezone, name, and NaT rows.
`to_first_of` / `to_last_of` select a day while retaining its clock.
`to_start_of` / `to_end_of` select the first/last representable time within
the period. The matching `is_*` methods return a bool Index and False at NaT.

## Calendar and clock boundaries

```{doctest} pddt-first-last-boundaries
>>> from datetime import timedelta
>>> import numpy as np
>>> import pandas as pd
>>> from rstimes import Pddt
>>> source = Pddt(['2024-02-29T12:34:56.123456789', None], tz='UTC', name='event')
>>> days = [('Y', '2024-01-01', '2024-12-31'), ('Q', '2024-01-01', '2024-03-31'), ('M', '2024-02-01', '2024-02-29'), ('W', '2024-02-26', '2024-03-03'), ('January', '2024-01-01', '2024-01-31')]
>>> for period, first, last in days:
...     a, b = source.to_first_of(period), source.to_last_of(period)
...     assert type(a) is Pddt and type(b) is Pddt
...     assert a.isoformat().dropna().tolist() == [first + 'T12:34:56.123456789+00:00']
...     assert b.isoformat().dropna().tolist() == [last + 'T12:34:56.123456789+00:00']
...     assert a.is_first_of(period).tolist() == b.is_last_of(period).tolist() == [True, False]
...     assert a.unit == b.unit == 'ns' and a.name == b.name == 'event'
>>> source.is_end_of('M').tolist()
[False, False]
>>> periods = [
...     ('Y', '2024-01-01T00:00:00', '2024-12-31T23:59:59.999999999'),
...     ('Q', '2024-01-01T00:00:00', '2024-03-31T23:59:59.999999999'),
...     ('M', '2024-02-01T00:00:00', '2024-02-29T23:59:59.999999999'),
...     ('W', '2024-02-26T00:00:00', '2024-03-03T23:59:59.999999999'),
...     ('D', '2024-02-29T00:00:00', '2024-02-29T23:59:59.999999999'),
...     ('h', '2024-02-29T12:00:00', '2024-02-29T12:59:59.999999999'),
...     ('min', '2024-02-29T12:34:00', '2024-02-29T12:34:59.999999999'),
...     ('s', '2024-02-29T12:34:56', '2024-02-29T12:34:56.999999999'),
...     ('ms', '2024-02-29T12:34:56.123000', '2024-02-29T12:34:56.123999999'),
...     ('us', '2024-02-29T12:34:56.123456', '2024-02-29T12:34:56.123456999'),
...     ('ns', '2024-02-29T12:34:56.123456789', '2024-02-29T12:34:56.123456789'),
...     ('Monday', '2024-02-26T00:00:00', '2024-02-26T23:59:59.999999999'),
... ]
>>> for period, start, end in periods:
...     a, b = source.to_start_of(period), source.to_end_of(period)
...     assert a.isoformat().dropna().tolist() == [start + '+00:00']
...     assert b.isoformat().dropna().tolist() == [end + '+00:00']
...     assert a.is_start_of(period).tolist() == b.is_end_of(period).tolist() == [True, False]
>>> for unit, tail in (('s', ''), ('ms', '.999000'), ('us', '.999999'), ('ns', '.999999999')):
...     result = Pddt(['2024-01-01'], unit=unit).to_end_of('D')
...     assert result.unit == unit and result.isoformat().tolist() == ['2024-01-01T23:59:59' + tail]
>>> Pddt(['2018-11-04 12:00'], tz='America/Sao_Paulo').normalize().isoformat().tolist()
['2018-11-04T01:00:00-02:00']
```

## Rounding and fractional precision

`round` uses ties to even; `ceil` cannot move earlier and `floor` cannot move
later. Positive fixed grids include multi-frequency forms such as `15min` and
`500ns`, timedeltas, and fixed pandas offsets. Calendar month/business offsets
are not fixed rounding grids. `snap` instead chooses the nearest valid period
start and chooses the later start on a tie. It accepts single periods and
stored month/weekday names, without arbitrary multi-frequency forms.

```{doctest} pddt-rounding-grids-and-snap
>>> ties = Pddt([1500, 2500, -1500, -2500, None], unit='ns', name='tie')
>>> (ties.round('us').asi8.tolist(), ties.floor('us').asi8.tolist(), ties.ceil('us').asi8.tolist())
([2000, 2000, -2000, -2000, -9223372036854775808], [1000, 2000, -2000, -3000, -9223372036854775808], [2000, 3000, -1000, -2000, -9223372036854775808])
>>> for method in ('round', 'ceil', 'floor'):
...     result = getattr(ties, method)(pd.offsets.Micro())
...     assert type(result) is Pddt and result.unit == 'ns' and result.name == 'tie'
...     assert result.isna().tolist() == [False, False, False, False, True]
>>> middle = Pddt(['2024-01-02 12:30', None])
>>> (middle.round('h').hour.dropna().tolist(), middle.snap('h').hour.dropna().tolist(), middle.round('15min').minute.dropna().tolist())
([12.0], [13.0], [30.0])
>>> for grid in ('500ns', timedelta(microseconds=1), pd.offsets.Micro()):
...     assert ties.floor(grid).unit == 'ns'
>>> source.snap('Monday').isoformat().dropna().tolist()
['2024-03-04T00:00:00+00:00']
>>> source.snap('February').isoformat().dropna().tolist()
['2024-02-01T00:00:00+00:00']
>>> for precision, expected in ((0, 0), (1, 100000000), (2, 120000000), (3, 123000000), (4, 123400000), (5, 123450000), (6, 123456000), (7, 123456700), (8, 123456780), (9, 123456789), (12, 123456789)):
...     result = Pddt([123456789, None], unit='ns').fsp(precision)
...     assert result.unit == 'ns' and result.asi8.tolist() == [expected, -9223372036854775808]
>>> for call, exception in ((lambda: source.round('ME'), ValueError), (lambda: source.floor('-1s'), ValueError), (lambda: source.ceil('0s'), ValueError), (lambda: source.snap('15min'), ValueError), (lambda: source.fsp(-1), ValueError), (lambda: source.fsp(True), TypeError), (lambda: source.fsp([3, 3]), TypeError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid rounding request accepted')
```

## Nullable queries and inherited attributes

Library integer queries return pandas Index with nullable Int64 and pd.NA at
NaT. Library boolean queries return bool Index with False at NaT. Inherited
calendar attributes such as month/day use pandas' own output forms. The year
property likewise uses int32 where possible, int64 for wider years, or float64
with NaN when dates are missing. It avoids narrowing a wide year to int32.

```{doctest} pddt-calendar-query-forms
>>> leap = Pddt(['2024-02-29', None], name='event')
>>> queries = {'isoyear': 2024, 'isoweek': 9, 'isoweekday': 4, 'days_in_year': 366, 'days_bf_year': 738885, 'days_in_quarter': 91, 'days_bf_quarter': 0, 'day_of_quarter': 60, 'days_bf_month': 31, 'day_of_month': 29}
>>> for name, expected in queries.items():
...     result = getattr(leap, name)()
...     assert type(result) is pd.Index and str(result.dtype) == 'Int64'
...     assert result.tolist() == [expected, pd.NA] and result.name == name
>>> (leap.millisecond.tolist(), str(leap.millisecond.dtype), leap.leap_bt_year(2025).tolist())
([0, <NA>], 'Int64', [1, <NA>])
>>> for method, argument in (('is_year', 2024), ('is_quarter', 1), ('is_month', 'February'), ('is_weekday', 'Thursday'), ('is_day', 29)):
...     result = getattr(leap, method)(argument)
...     assert type(result) is pd.Index and result.dtype == np.dtype('bool')
...     assert result.tolist() == [True, False]
>>> (leap.is_long_year().tolist(), Pddt(['2015-06-01', None]).is_long_year().tolist())
([False, False], [True, False])
>>> (leap.is_month(13).tolist(), leap.is_weekday(8).tolist(), leap.is_day(0).tolist())
([False, False], [False, False], [False, False])
>>> iso = leap.isocalendar()
>>> (type(iso) is pd.DataFrame, iso.columns.tolist(), [str(dtype) for dtype in iso.dtypes], iso['year'].tolist(), iso['week'].tolist(), iso['day'].tolist())
(True, ['year', 'week', 'day'], ['UInt32', 'UInt32', 'UInt32'], [2024, <NA>], [9, <NA>], [4, <NA>])
>>> iso.index.equals(leap)
True
>>> signed = Pddt(['0000-01-01'], unit='us')
>>> signed.isoyear().tolist()
[-1]
>>> try:
...     signed.isocalendar()
... except OverflowError as error:
...     print(type(error).__name__)
OverflowError
>>> for call, exception in ((lambda: leap.is_month(''), ValueError), (lambda: leap.is_weekday('unknown'), ValueError), (lambda: leap.is_day([29]), ValueError), (lambda: leap.is_year([2024, None]), TypeError), (lambda: leap.is_quarter(True), TypeError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid query argument accepted')
```

## Boundary differences and now predicates

`diff` counts unit bucket crossings, self minus target. Numeric targets are
seconds, independently of the receiver's storage unit. A target can be scalar
or exactly equal length; missing date targets propagate a missing difference.
Aware targets use UTC coordinates, and naive/aware mixing is an error.
Inclusive modes adjust the boundary count, rather than duration endpoints.

```{doctest} pddt-boundary-differences
>>> late = Pddt(['2024-02-01', None])
>>> early = '2024-01-31 23:59:59'
>>> units = {'Y': 0, 'Q': 0, 'M': 1, 'W': 0, 'D': 1, 'h': 1, 'm': 1, 'min': 1, 's': 1, 'ms': 1000, 'us': 1000000, 'ns': 1000000000}
>>> for unit, expected in units.items():
...     result = late.diff(early, unit)
...     assert type(result) is pd.Index and str(result.dtype) == 'Int64'
...     assert result.tolist() == [expected, pd.NA] and result.name == 'diff'
>>> (late.diff(early, 'D', inclusive='both').tolist(), late.diff(early, 'D', inclusive='neither').tolist())
([2, <NA>], [0, <NA>])
>>> late.diff('2024-02-01', 'D', absolute=True, inclusive='neither').tolist()
[-1, <NA>]
>>> Pddt([np.datetime64(2, 's')]).diff([1], 's').tolist()
[1]
>>> Pddt([0, 1000000000], unit='ns').diff([None, 0], 's').tolist()
[<NA>, 1]
>>> minimum = Pddt([-2**63 + 1], unit='s').diff(1, 's')
>>> (minimum.tolist(), minimum.isna().tolist())
([-9223372036854775808], [False])
>>> Pddt([0], unit='s', tz='UTC').diff(Pddt([0], unit='ns', tz='Asia/Shanghai'), 'ns').tolist()
[0]
>>> for call, exception in ((lambda: late.diff(['2024-01-01'], 'D'), ValueError), (lambda: late.diff(early, 'D', absolute=1), TypeError), (lambda: late.diff(early, 'D', inclusive='unknown'), ValueError), (lambda: late.diff('2024-01-01T00:00Z', 'D'), TypeError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid diff request accepted')
>>> for now in (Pddt.now(1), Pddt.utcnow(1)):
...     past, future = now - timedelta(days=1), now + timedelta(days=1)
...     assert past.is_past().tolist() == [True] and past.is_future().tolist() == [False]
...     assert future.is_future().tolist() == [True] and future.is_past().tolist() == [False]
>>> (Pddt([None]).is_past().tolist(), Pddt([None]).is_future().tolist())
([False], [False])
```
