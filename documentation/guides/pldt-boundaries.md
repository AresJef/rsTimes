# Boundaries and rounding on Polars dates

`to_first_of` and `to_last_of` choose a calendar day while keeping the clock.
`to_start_of` and `to_end_of` choose the first or last representable date-time
in a period. The corresponding `is_*` methods return Boolean Series with False
at nulls. Date results keep the receiver's unit, name, timezone and nulls.

## Calendar days and exact time edges

```{doctest} pldt-calendar-period-boundaries
>>> from datetime import date, timedelta
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt
>>> source = Pldt(['2024-02-29T12:34:56.123456789', None], tz='UTC', name='event')
>>> days = [('Y', '2024-01-01', '2024-12-31'), ('Q', '2024-01-01', '2024-03-31'), ('M', '2024-02-01', '2024-02-29'), ('W', '2024-02-26', '2024-03-03'), ('January', '2024-01-01', '2024-01-31')]
>>> for owner in (source, pl.Series(source).pldt):
...     for period, first, last in days:
...         a, b = owner.to_first_of(period), owner.to_last_of(period)
...         assert type(a) is Pldt and type(b) is Pldt and a.dtype == b.dtype == source.dtype
...         assert a.name == b.name == 'event'
...         assert a.isoformat().to_list() == [first + 'T12:34:56.123456789+00:00', None]
...         assert b.isoformat().to_list() == [last + 'T12:34:56.123456789+00:00', None]
...         assert a.is_first_of(period).to_list() == b.is_last_of(period).to_list() == [True, False]
...         assert pl.Series(a).pldt.is_first_of(period).to_list() == pl.Series(b).pldt.is_last_of(period).to_list() == [True, False]
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
>>> for owner in (source, pl.Series(source).pldt):
...     for period, first, last in periods:
...         a, b = owner.to_start_of(period), owner.to_end_of(period)
...         assert type(a) is Pldt and type(b) is Pldt and a.dtype == b.dtype == source.dtype
...         assert a.isoformat().to_list() == [first + '+00:00', None]
...         assert b.isoformat().to_list() == [last + '+00:00', None]
...         assert a.is_start_of(period).to_list() == b.is_end_of(period).to_list() == [True, False]
...         assert pl.Series(a).pldt.is_start_of(period).to_list() == pl.Series(b).pldt.is_end_of(period).to_list() == [True, False]
>>> for unit, tail in [('ms', '.999000'), ('us', '.999999'), ('ns', '.999999999')]:
...     last = Pldt(['2024-01-01'], unit=unit).to_end_of('D')
...     assert last.dtype == pl.Datetime(unit)
...     assert last.isoformat(timespec='ns' if unit == 'ns' else 'us').to_list() == ['2024-01-01T23:59:59' + tail]
>>> for storage in ('ms', 'us', 'ns'):
...     fine = Pldt([0, 1, -1, None], unit=storage)
...     for period in ('ms', 'us', 'ns'):
...         if {'ms': 1000000, 'us': 1000, 'ns': 1}[period] <= {'ms': 1000000, 'us': 1000, 'ns': 1}[storage]:
...             assert fine.to_start_of(period).to_physical().to_list() == fine.to_end_of(period).to_physical().to_list() == [0, 1, -1, None]
...             assert fine.is_start_of(period).to_list() == fine.is_end_of(period).to_list() == [True, True, True, False]
```

For a period finer than storage, the only representable lattice point is the
existing date. The implementation does not invent an unrepresentable final
fraction or silently change the unit.

## Fixed grids, snap, and fractional precision

Use `.pldt.round`, `.pldt.floor` and `.pldt.ceil` for date rounding. Native
Series rounding has its own numeric API. Date grids are positive fixed
frequencies such as `15min`, `500ns`, or a timedelta. Round uses ties to even.
Snap instead selects the nearest actual period start, with ties going later;
it accepts single natural periods and stored month/weekday names.

```{doctest} pldt-rounding-snap-fraction
>>> ties = Pldt([1500, 2500, -1500, -2500, None], unit='ns', name='event')
>>> (ties.pldt.round('us').to_physical().to_list(), ties.pldt.floor('us').to_physical().to_list(), ties.pldt.ceil('us').to_physical().to_list())
([2000, 2000, -2000, -2000, None], [1000, 2000, -2000, -3000, None], [2000, 3000, -1000, -2000, None])
>>> for grid in ('500ns', timedelta(microseconds=1)):
...     for method in ('round', 'ceil', 'floor'):
...         result = getattr(pl.Series(ties).pldt, method)(grid)
...         assert type(result) is Pldt and result.dtype == ties.dtype and result.name == 'event'
...         assert result.is_null().to_list() == [False, False, False, False, True]
>>> middle = Pldt(['2024-01-02 12:30', None])
>>> (middle.pldt.round('h').hour.to_list(), middle.snap('h').hour.to_list(), middle.pldt.round('15min').minute.to_list())
([12, None], [13, None], [30, None])
>>> (source.snap('Monday').isoformat().to_list(), source.snap('February').isoformat().to_list())
(['2024-03-04T00:00:00+00:00', None], ['2024-02-01T00:00:00+00:00', None])
>>> native = pl.Series(source).pldt
>>> (native.snap('Monday').isoformat().to_list(), native.snap('February').isoformat().to_list())
(['2024-03-04T00:00:00+00:00', None], ['2024-02-01T00:00:00+00:00', None])
>>> for precision, expected in [(0, 0), (1, 100000000), (2, 120000000), (3, 123000000), (4, 123400000), (5, 123450000), (6, 123456000), (7, 123456700), (8, 123456780), (9, 123456789), (12, 123456789)]:
...     x = Pldt([123456789, None], unit='ns')
...     for owner in (x, pl.Series(x).pldt):
...         result = owner.fsp(precision)
...         assert type(result) is Pldt and result.dtype == x.dtype
...         assert result.to_physical().to_list() == [expected, None]
>>> for action, error in [(lambda: source.pldt.round('ME'), ValueError), (lambda: source.pldt.floor('-1s'), ValueError), (lambda: source.pldt.ceil('0s'), ValueError), (lambda: source.snap('15min'), ValueError), (lambda: source.fsp(-1), ValueError), (lambda: source.fsp(True), TypeError)]:
...     try:
...         action()
...     except error:
...         continue
...     raise AssertionError('invalid rounding or precision was accepted')
```

## Real timezone edges and preparation errors

A missing midnight starts at the first existing time within that day. During a
repeat, an hour edge retains the relevant occurrence. Queries can return False
for an out-of-capacity edge without constructing that edge. A transformation
that actually needs the edge raises OverflowError.

Boundaries require a prepared Datetime column. Grid operations can promote a
native Date without guessing a String column's date syntax.

```{doctest} pldt-timezone-period-edges
>>> sao = Pldt(['2018-11-04 12:00', None], tz='America/Sao_Paulo')
>>> for owner in (sao, pl.Series(sao).pldt):
...     assert owner.normalize().isoformat().to_list() == ['2018-11-04T01:00:00-02:00', None]
>>> repeated = Pldt(['2024-11-03 01:30', None], unit='us', tz='America/New_York', ambiguous=False)
>>> (repeated.to_start_of('h').tz_convert('UTC').isoformat().to_list(), repeated.to_end_of('h').tz_convert('UTC').isoformat().to_list())
(['2024-11-03T06:00:00+00:00', None], ['2024-11-03T06:59:59.999999+00:00', None])
>>> first = Pldt(['2024-11-03 01:30'], tz='America/New_York', ambiguous=True)
>>> (first.snap('h').tz_convert('UTC').hour.to_list(), first.pldt.round('h').tz_convert('UTC').hour.to_list())
([6], [7])
>>> limits = Pldt([-2**63, 2**63 - 1, None], unit='ns')
>>> (limits.is_start_of('Y').to_list(), limits.is_end_of('Y').to_list())
([False, False, False], [False, False, False])
>>> try:
...     limits.to_start_of('Y')
... except OverflowError as error:
...     print(type(error).__name__)
OverflowError
>>> native_date = pl.Series('day', [date(2024, 1, 2), None], dtype=pl.Date)
>>> (native_date.pldt.snap('D').dtype == pl.Datetime('ms'), native_date.pldt.fsp(3).dtype == pl.Datetime('ms'))
(True, True)
>>> for action, error in [(lambda: native_date.pldt.normalize(), TypeError), (lambda: source.to_first_of('D'), ValueError), (lambda: source.to_start_of('15min'), ValueError), (lambda: Pldt([]).is_start_of(None), TypeError), (lambda: Pldt([None]).is_last_of('unknown'), ValueError)]:
...     try:
...         action()
...     except error:
...         continue
...     raise AssertionError('an invalid period or receiver dtype was accepted')
```
