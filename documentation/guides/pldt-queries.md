# Query native date columns

Pldt and native Series `.pldt` queries return ordinary Series, keeping the
receiver name and row order. Integer queries use Int64 with native nulls.
Boolean date predicates use Boolean with False at source nulls. Metadata about
the entire timezone has a scalar role.

## Integer properties and calendar methods

Weekday is Monday=0; ISO weekday is Monday=1. `nanosecond` is the additional
0–999 tail after microseconds. It is not the whole fraction since the second.
The complete leap-day example calls every integer field/query on both eager
entry paths.

```{doctest} pldt-integer-calendar-queries
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt
>>> source = Pldt(['2024-02-29T12:34:56.123456789', None], unit='ns', name='event')
>>> properties = {'year': 2024, 'month': 2, 'day': 29, 'hour': 12, 'minute': 34, 'second': 56, 'millisecond': 123, 'microsecond': 123456, 'nanosecond': 789, 'weekday': 3, 'quarter': 1, 'day_of_year': 60, 'days_in_month': 29}
>>> methods = {'isoyear': 2024, 'isoweek': 9, 'isoweekday': 4, 'days_in_year': 366, 'days_bf_year': 738885, 'days_in_quarter': 91, 'days_bf_quarter': 0, 'day_of_quarter': 60, 'days_bf_month': 31, 'day_of_month': 29}
>>> for owner in (source, pl.Series(source).pldt):
...     for name, expected in {**properties, **methods}.items():
...         value = getattr(owner, name)
...         result = value() if name in methods else value
...         assert type(result) is pl.Series and result.dtype == pl.Int64 and result.name == 'event'
...         assert result.to_list() == [expected, None]
>>> for unit, ticks_per_day in [('ms', 86400000), ('us', 86400000000), ('ns', 86400000000000)]:
...     broad = Pldt([-2**63, -1, None], unit=unit)
...     assert broad.weekday.to_list() == [(-2**63 // ticks_per_day + 3) % 7, 2, None]
...     assert broad.nanosecond.to_list() == [(-2**63) % 1000 if unit == 'ns' else 0, 999 if unit == 'ns' else 0, None]
...     assert broad.year.null_count() == 1
```

## Matching and leap-year counts

Targets can be integers or, for month/weekday matching, stored English names.
A valid but out-of-range integer simply does not match. Invalid names and
unsupported types are errors. Scalar targets broadcast; row targets must match
the full source length. Their missing values are errors even at a null date.
`leap_bt_year` counts leap years in the lower-inclusive, upper-exclusive range,
independently of direction, and returns a nonnegative count.

```{doctest} pldt-boolean-and-leap-queries
>>> for owner in (source, pl.Series(source).pldt):
...     for method, target in [('is_year', 2024), ('is_quarter', 1), ('is_month', 'February'), ('is_weekday', 'Thursday'), ('is_day', 29)]:
...         result = getattr(owner, method)(target)
...         assert type(result) is pl.Series and result.dtype == pl.Boolean and result.name == 'event'
...         assert result.to_list() == [True, False]
...     assert owner.is_leap_year.to_list() == [True, False]
...     assert owner.is_long_year().to_list() == [False, False]
...     assert owner.is_month(13).to_list() == owner.is_day(0).to_list() == [False, False]
>>> dates = Pldt(['2020-01-01', '2024-01-01', '2024-01-01', None], name='event')
>>> (dates.leap_bt_year([2024, 2020, 2024, 0]).to_list(), dates.is_long_year().to_list())
([1, 1, 0, None], [True, False, False, False])
>>> pl.Series(dates).pldt.leap_bt_year([2024, 2020, 2024, 0]).to_list()
[1, 1, 0, None]
>>> dates.is_month(pl.Series(['January', 'January', 'February', 'January'])).to_list()
[True, True, False, False]
>>> for action, error in [(lambda: dates.is_year([2024]), ValueError), (lambda: dates.is_month([1, 1, 1, None]), TypeError), (lambda: Pldt([None]).is_day(None), TypeError), (lambda: Pldt([]).is_quarter(True), TypeError), (lambda: source.is_weekday('unknown'), ValueError), (lambda: source.is_month(''), ValueError)]:
...     try:
...         action()
...     except error:
...         continue
...     raise AssertionError('an invalid query target was accepted')
```

## ISO Struct output

`isocalendar` returns one native Struct Series with UInt32 year/week/day
children. A source null is an outer Struct null. A negative ISO year cannot be
represented by UInt32 and raises OverflowError, although `isoyear()` can return
that signed year as Int64.

```{doctest} pldt-iso-struct-query
>>> for owner in (source, pl.Series(source).pldt):
...     result = owner.isocalendar()
...     assert type(result) is pl.Series and result.dtype == pl.Struct({'year': pl.UInt32, 'week': pl.UInt32, 'day': pl.UInt32})
...     assert result.to_list() == [{'year': 2024, 'week': 9, 'day': 4}, None]
...     assert result.is_null().to_list() == [False, True]
>>> Pldt(['0000-01-04'], unit='us').isocalendar().struct.field('year').to_list()
[0]
>>> signed = Pldt(['0000-01-01'], unit='us')
>>> (signed.year.to_list(), signed.isoyear().to_list())
([0], [-1])
>>> try:
...     signed.isocalendar()
... except OverflowError as error:
...     print(type(error).__name__)
OverflowError
```

## Timezone metadata and now predicates

`tzinfo` is None, normalized `timezone.utc`, or ZoneInfo. `tz_available` is a
set of available zone keys. `is_utc()` and `is_local()` describe the whole column
and return bool, whereas `is_dst()` and `utcoffset_seconds()` return row Series.
The latter returns null for naive dates, which have no known offset.

`is_past` and `is_future` compare strictly with a current instant; equality
matches neither. Eager calls read a reference when needed. Expressions capture
their reference at creation, as explained in the expression guide. Naive dates
require a valid local-zone interpretation.

```{doctest} pldt-timezone-and-now-queries
>>> from datetime import timedelta, timezone
>>> for owner in (Pldt([0, None], tz='UTC'), pl.Series('event', [0, None], dtype=pl.Datetime('ns', 'UTC')).pldt):
...     assert owner.tzinfo is timezone.utc and owner.is_utc() is True
...     assert type(owner.is_local()) is bool
...     assert type(owner.tz_available) is set and 'America/New_York' in owner.tz_available
...     assert owner.is_dst().dtype == pl.Boolean and owner.is_dst().to_list() == [False, False]
...     assert owner.utcoffset_seconds().dtype == pl.Int64 and owner.utcoffset_seconds().to_list() == [0, None]
>>> seasonal = Pldt(['2024-01-01', '2024-07-01', None], tz='America/New_York')
>>> (seasonal.is_dst().to_list(), seasonal.utcoffset_seconds().to_list())
([False, True, False], [-18000, -14400, None])
>>> Pldt(['2024-01-01', None]).utcoffset_seconds().to_list()
[None, None]
>>> now = Pldt.utcnow(1)
>>> for column, expected in [(now - timedelta(days=1), [True]), (now + timedelta(days=1), [False])]:
...     for owner in (column, pl.Series(column).pldt):
...         result = owner.is_past()
...         assert type(result) is pl.Series and result.dtype == pl.Boolean and result.to_list() == expected
...         assert owner.is_future().to_list() == [not expected[0]]
>>> (Pldt([None]).is_past().to_list(), Pldt([None]).is_future().to_list(), Pldt([]).is_past().to_list())
([False], [False], [])
```
