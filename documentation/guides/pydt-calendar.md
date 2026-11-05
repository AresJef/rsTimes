# Select and move scalar calendar dates

Pydt calendar conveniences return a Pydt of the appropriate subtype and retain
the source clock and timezone unless that operation explicitly changes a
clock field. Month-end fitting is part of convenience selection; strict
`replace` instead requires a complete valid date.

## Relative periods and named selections

`to_year`, `to_quarter`, `to_month`, `to_weekday`, and `to_day` move by signed
calendar periods. A zero offset is a real zero move. A quarter's `month`
parameter is its position 1–3 within that quarter. A year selector's month
can be an accepted month name; `to_date` and `to_datetime` take numeric months.

The examples start on Wednesday, January 31, 2024. The expected dates are
written explicitly from the Gregorian calendar. Each real named method is
called, and its type, date, clock, and timezone are checked.

```{doctest} pydt-calendar-selectors
>>> from datetime import datetime, timedelta, timezone
>>> import numpy as np
>>> from rstimes import Pydt, Delta
>>> source = Pydt(2024, 1, 31, 12, 34, 56, 123456, tzinfo='UTC')
>>> cases = [
...     ('to_year', (1,), {}, '2025-01-31'),
...     ('to_year', (-1,), {'month': 'February', 'day': 31}, '2023-02-28'),
...     ('to_curr_year', (), {'month': 'February', 'day': 31}, '2024-02-29'),
...     ('to_prev_year', (), {'month': 'February', 'day': 31}, '2023-02-28'),
...     ('to_next_year', (), {'month': 'February', 'day': 31}, '2025-02-28'),
...     ('to_quarter', (1,), {}, '2024-04-30'),
...     ('to_curr_quarter', (), {'month': 3, 'day': 31}, '2024-03-31'),
...     ('to_prev_quarter', (), {'month': 2, 'day': 31}, '2023-11-30'),
...     ('to_next_quarter', (), {'month': 2, 'day': 31}, '2024-05-31'),
...     ('to_month', (np.int64(1),), {}, '2024-02-29'),
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
>>> for method, args, kwargs, expected in cases:
...     result = getattr(source, method)(*args, **kwargs)
...     assert type(result) is Pydt and result.date().isoformat() == expected
...     assert (result.hour, result.minute, result.second, result.microsecond) == (12, 34, 56, 123456)
...     assert result.tzinfo is source.tzinfo
>>> source.to_month(0).isoformat()
'2024-01-31T12:34:56.123456+00:00'
```

The previous/next weekday selectors choose that day in the previous/next
calendar week. They do not mean “nearest matching weekday in that direction”.
Weekday selectors use Monday=0; ISO calendar factories use Monday=1.

## Change selected fields

For optional field arguments, `None` preserves the existing field and zero
sets a real zero clock field. Convenience date selection can fit day 31 to
February's month end. `replace` and `__replace__` use strict date validation.

```{doctest} pydt-fields-and-replace
>>> selected = source.to_datetime(year=None, month=2, day=31, hour=0, minute=None)
>>> (type(selected) is Pydt, selected.isoformat())
(True, '2024-02-29T00:34:56.123456+00:00')
>>> source.to_date(month=2, day=31).isoformat()
'2024-02-29T12:34:56.123456+00:00'
>>> source.to_time(hour=0, microsecond=0).isoformat()
'2024-01-31T00:34:56+00:00'
>>> source.replace(day=None).isoformat()
'2024-01-31T12:34:56.123456+00:00'
>>> source.__replace__(day=1).isoformat()
'2024-01-01T12:34:56.123456+00:00'
>>> try:
...     source.replace(month=2, day=31)
... except ValueError as error:
...     print(type(error).__name__)
ValueError
>>> for call in (lambda: source.to_date(day=0), lambda: source.to_date(day=-1), lambda: source.to_time(hour=25)):
...     try:
...         call()
...     except ValueError:
...         continue
...     raise AssertionError('invalid field accepted')
>>> try:
...     source.to_date(month='February')
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```

## Add or subtract named integer amounts

`add` and `sub` accept years, quarters, months, weeks, days, hours, minutes,
seconds, milliseconds, and microseconds. Each uses the integer index protocol;
fixed fractional amounts belong in Delta instead. Named Pydt `add`/`sub` do
not add a nanoseconds parameter to this microsecond scalar class.

```{doctest} pydt-add-sub-components
>>> components = [
...     ('years', '2025-01-31T12:34:56.123456+00:00', '2023-01-31T12:34:56.123456+00:00'),
...     ('quarters', '2024-04-30T12:34:56.123456+00:00', '2023-10-31T12:34:56.123456+00:00'),
...     ('months', '2024-02-29T12:34:56.123456+00:00', '2023-12-31T12:34:56.123456+00:00'),
...     ('weeks', '2024-02-07T12:34:56.123456+00:00', '2024-01-24T12:34:56.123456+00:00'),
...     ('days', '2024-02-01T12:34:56.123456+00:00', '2024-01-30T12:34:56.123456+00:00'),
...     ('hours', '2024-01-31T13:34:56.123456+00:00', '2024-01-31T11:34:56.123456+00:00'),
...     ('minutes', '2024-01-31T12:35:56.123456+00:00', '2024-01-31T12:33:56.123456+00:00'),
...     ('seconds', '2024-01-31T12:34:57.123456+00:00', '2024-01-31T12:34:55.123456+00:00'),
...     ('milliseconds', '2024-01-31T12:34:56.124456+00:00', '2024-01-31T12:34:56.122456+00:00'),
...     ('microseconds', '2024-01-31T12:34:56.123457+00:00', '2024-01-31T12:34:56.123455+00:00'),
... ]
>>> for field, plus, minus in components:
...     forward, backward = source.add(**{field: 1}), source.sub(**{field: 1})
...     assert type(forward) is Pydt and type(backward) is Pydt
...     assert forward.isoformat() == plus and backward.isoformat() == minus
>>> source.add(months=1, days=-1, hours=2).isoformat()
'2024-02-28T14:34:56.123456+00:00'
>>> source.add(days=-1).isoformat()
'2024-01-30T12:34:56.123456+00:00'
>>> for call in (lambda: source.add(hours=1.5), lambda: source.sub(days=True), lambda: source.to_month(None)):
...     try:
...         call()
...     except TypeError:
...         continue
...     raise AssertionError('wrong numeric role accepted')
>>> (source + Delta(hours=1.5)).isoformat()
'2024-01-31T14:04:56.123456+00:00'
```

## Read calendar fields and ask conditions

The access forms are deliberate. `weekday()` is the standard method;
`day_of_year`, `days_in_month`, `is_leap_year`, `quarter`, and `millisecond`
are properties. The remaining convenience queries below are methods.

```{doctest} pydt-calendar-queries
>>> leap_day = Pydt(2024, 2, 29, 12, 34, 56, 123456)
>>> properties = {'year': 2024, 'month': 2, 'day': 29, 'hour': 12, 'minute': 34, 'second': 56, 'microsecond': 123456, 'day_of_year': 60, 'days_in_month': 29, 'is_leap_year': True, 'quarter': 1, 'millisecond': 123}
>>> for name, expected in properties.items():
...     result = getattr(leap_day, name)
...     assert type(result) is type(expected) and result == expected
>>> methods = {'isoyear': 2024, 'isoweek': 9, 'isoweekday': 4, 'days_in_year': 366, 'days_bf_year': 738885, 'days_in_quarter': 91, 'days_bf_quarter': 0, 'day_of_quarter': 60, 'days_bf_month': 31, 'day_of_month': 29, 'weekday': 3}
>>> for name, expected in methods.items():
...     result = getattr(leap_day, name)()
...     assert type(result) is int and result == expected
>>> (tuple(leap_day.isocalendar()), leap_day.is_long_year(), Pydt(2015, 6, 1).is_long_year(), leap_day.leap_bt_year(2025))
((2024, 9, 4), False, True, 1)
>>> (leap_day.is_year(2024), leap_day.is_quarter(1), leap_day.is_month('February'), leap_day.is_weekday('Thursday'), leap_day.is_day(29))
(True, True, True, True, True)
>>> (leap_day.is_year(0), leap_day.is_quarter(5), leap_day.is_month(13), leap_day.is_weekday(8), leap_day.is_day(0))
(False, False, False, False, False)
>>> for call in (lambda: leap_day.is_month(None), lambda: leap_day.is_weekday(True), lambda: leap_day.is_day(1.0)):
...     try:
...         call()
...     except TypeError:
...         continue
...     raise AssertionError('invalid query target accepted')
>>> for call in (lambda: leap_day.is_month(''), lambda: leap_day.is_weekday('unknown weekday')):
...     try:
...         call()
...     except ValueError:
...         continue
...     raise AssertionError('unknown name accepted')
```

Legal nonmatching query integers return False, even when they would not be a
legal selected field. None and invalid types are not nonmatches. `leap_bt_year`
counts leap years in the half-open interval between the two years. Calendar
arithmetic is not generally reversible across a fitted month end.
