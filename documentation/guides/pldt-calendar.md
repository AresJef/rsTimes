# Transform Polars calendar columns

Date transformations on Pldt and a native Series' `.pldt` namespace return
Pldt. They retain the current unit, name, timezone and source nulls. Calendar
selection fits a legal day intent to the final month. Strict field replacement
requires a valid complete date. Use `.pldt.replace` for that date operation;
ordinary Series `replace` keeps its native value-replacement meaning.

## All calendar selectors

Every method in the table below is actually called on both entry paths. The
literal expected dates start from January 31, 2024. The clock's nanosecond
fraction and the missing second row must survive.

```{doctest} pldt-calendar-selectors
>>> from datetime import timedelta
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt, Delta
>>> source = Pldt(['2024-01-31T12:34:56.123456789', None], tz='UTC', name='event')
>>> selectors = [
...     ('to_year', (1,), {}, '2025-01-31'),
...     ('to_curr_year', (), {'month': 'February', 'day': 31}, '2024-02-29'),
...     ('to_prev_year', (), {'month': 'February', 'day': 31}, '2023-02-28'),
...     ('to_next_year', (), {'month': 'February', 'day': 31}, '2025-02-28'),
...     ('to_quarter', (1,), {}, '2024-04-30'),
...     ('to_curr_quarter', (), {'month': 3, 'day': 31}, '2024-03-31'),
...     ('to_prev_quarter', (), {'month': 2, 'day': 31}, '2023-11-30'),
...     ('to_next_quarter', (), {'month': 2, 'day': 31}, '2024-05-31'),
...     ('to_month', (1,), {}, '2024-02-29'),
...     ('to_curr_month', (), {'day': 1}, '2024-01-01'),
...     ('to_prev_month', (), {'day': 1}, '2023-12-01'),
...     ('to_next_month', (), {'day': 1}, '2024-02-01'),
...     ('to_weekday', (1,), {'weekday': 'Monday'}, '2024-02-05'),
...     ('to_curr_weekday', (), {'weekday': 0}, '2024-01-29'),
...     ('to_prev_weekday', (), {'weekday': 'Monday'}, '2024-01-22'),
...     ('to_next_weekday', (), {'weekday': 'Monday'}, '2024-02-05'),
...     ('to_monday', (), {}, '2024-01-29'),
...     ('to_tuesday', (), {}, '2024-01-30'),
...     ('to_wednesday', (), {}, '2024-01-31'),
...     ('to_thursday', (), {}, '2024-02-01'),
...     ('to_friday', (), {}, '2024-02-02'),
...     ('to_saturday', (), {}, '2024-02-03'),
...     ('to_sunday', (), {}, '2024-02-04'),
...     ('to_day', (1,), {}, '2024-02-01'),
...     ('to_yesterday', (), {}, '2024-01-30'),
...     ('to_tomorrow', (), {}, '2024-02-01'),
... ]
>>> for owner in (source, pl.Series(source).pldt):
...     for method, args, kwargs, expected in selectors:
...         result = getattr(owner, method)(*args, **kwargs)
...         assert type(result) is Pldt and result.dtype == source.dtype and result.name == 'event'
...         assert result.isoformat().to_list() == [expected + 'T12:34:56.123456789+00:00', None]
>>> source.to_month(0).to_physical().to_list() == source.to_physical().to_list()
True
```

Ordinary weekdays are Monday=0 through Sunday=6. Previous/next weekday methods
select that weekday in the previous/next calendar week. Quarter month arguments
are positions 1–3 inside a quarter, rather than names of months.

## Fitted fields and strict replacement

None retains an optional field. Zero is a real clock value. Replacing a
microsecond clears the old nanosecond tail; an explicit nanosecond tail is
applied last. Year zero and negative years are valid when the unit has enough
capacity. No operation silently changes its storage unit to make a result fit.

```{doctest} pldt-calendar-field-replacement
>>> for owner in (source, pl.Series(source).pldt):
...     assert owner.to_datetime(month=2, day=31, hour=0).isoformat().to_list() == ['2024-02-29T00:34:56.123456789+00:00', None]
...     assert owner.to_date(month=2, day=31).day.to_list() == [29, None]
...     assert owner.to_time(hour=0, nanosecond=0).isoformat().to_list() == ['2024-01-31T00:34:56.123456+00:00', None]
>>> for fields, fraction in [({'microsecond': 1}, '000001000'), ({'nanosecond': 2}, '123456002'), ({'microsecond': 1, 'nanosecond': 2}, '000001002')]:
...     for namespace in (source.pldt, pl.Series(source).pldt):
...         result = namespace.replace(**fields)
...         assert type(result) is Pldt and result.dtype == source.dtype and result.name == source.name
...         assert result.isoformat(timespec='ns').to_list() == ['2024-01-31T12:34:56.' + fraction + '+00:00', None]
>>> source.pldt.replace(day=None).to_physical().to_list() == source.to_physical().to_list()
True
>>> removed = source.pldt.replace(tzinfo=None)
>>> (removed.dtype.time_zone, removed.hour.to_list())
(None, [12, None])
>>> wide = Pldt(['0001-01-01'], unit='us')
>>> (wide.to_date(year=0).year.to_list(), wide.pldt.replace(year=-1).year.to_list())
([0], [-1])
>>> for action, error in [(lambda: source.pldt.replace(month=2), ValueError), (lambda: source.to_date(day=32), ValueError), (lambda: source.to_time(hour=25), ValueError), (lambda: source.to_quarter(0, month='February'), TypeError), (lambda: source.to_time(nanosecond=True), TypeError)]:
...     try:
...         action()
...     except error:
...         continue
...     raise AssertionError('an invalid field was accepted')
```

## Positional row arguments

A scalar broadcasts. A collection must have exactly the receiver length,
including null rows. A length-one collection is not a scalar. Optional field
None values retain the old field; relative counts instead require integers at
every supplied position. Source nulls do not bypass argument validation.

```{doctest} pldt-calendar-row-arguments
>>> dates = Pldt(['2024-01-31', '2025-03-31', None], name='event')
>>> months = pl.Series('month', [2, 4, None], dtype=pl.Int64)
>>> for owner in (dates, pl.Series(dates).pldt):
...     changed = owner.to_date(month=months, day=[31, 30, None])
...     assert type(changed) is Pldt and changed.dtype == dates.dtype
...     assert changed.year.to_list() == [2024, 2025, None]
...     assert changed.month.to_list() == [2, 4, None] and changed.day.to_list() == [29, 30, None]
...     assert owner.add(months=[1, -1, 0]).month.to_list() == [2, 2, None]
>>> for action, error in [(lambda: dates.to_date(day=[1]), ValueError), (lambda: dates.to_day([1, 2]), ValueError), (lambda: dates.add(days=[1, None, 0]), TypeError), (lambda: Pldt([None]).is_day([None]), TypeError)]:
...     try:
...         action()
...     except error:
...         continue
...     raise AssertionError('invalid row arguments were accepted')
```

## Every relative component

`add` and `sub` accept integer years, quarters, months, weeks, days, hours,
minutes, seconds, milliseconds, microseconds and nanoseconds. Components combine
before the final precision check, so exact cancellation is legal. A month-end
fit loses the original day intent; adding and subtracting a month need not be
reversible. Use Delta for fractional fixed durations.

```{doctest} pldt-calendar-relative-components
>>> components = [
...     ('years', '2025-01-31T12:34:56.123456789'),
...     ('quarters', '2024-04-30T12:34:56.123456789'),
...     ('months', '2024-02-29T12:34:56.123456789'),
...     ('weeks', '2024-02-07T12:34:56.123456789'),
...     ('days', '2024-02-01T12:34:56.123456789'),
...     ('hours', '2024-01-31T13:34:56.123456789'),
...     ('minutes', '2024-01-31T12:35:56.123456789'),
...     ('seconds', '2024-01-31T12:34:57.123456789'),
...     ('milliseconds', '2024-01-31T12:34:56.124456789'),
...     ('microseconds', '2024-01-31T12:34:56.123457789'),
...     ('nanoseconds', '2024-01-31T12:34:56.123456790'),
... ]
>>> for owner in (source, pl.Series(source).pldt):
...     for field, expected in components:
...         plus, inverse = owner.add(**{field: 1}), owner.sub(**{field: -1})
...         assert type(plus) is Pldt and type(inverse) is Pldt
...         assert plus.dtype == inverse.dtype == source.dtype and plus.name == inverse.name == 'event'
...         assert plus.isoformat().to_list() == inverse.isoformat().to_list() == [expected + '+00:00', None]
>>> source.add(years=1, months=-12).to_physical().to_list() == source.to_physical().to_list()
True
>>> coarse = Pldt([0, None], unit='us')
>>> coarse.add(microseconds=1, nanoseconds=-1000).to_physical().to_list()
[0, None]
>>> for action, error in [(lambda: coarse.add(nanoseconds=1), ValueError), (lambda: coarse.sub(nanoseconds=1), ValueError), (lambda: source.add(hours=1.5), TypeError), (lambda: source.sub(days=True), TypeError), (lambda: source.to_month(None), TypeError)]:
...     try:
...         action()
...     except error:
...         continue
...     raise AssertionError('relative fields lost their numeric or precision role')
>>> before = Pldt(['2024-03-09 12:00'], tz='America/New_York')
>>> ((before + Delta(days=1)).hour.to_list(), (before + timedelta(days=1)).hour.to_list())
([12], [13])
```
