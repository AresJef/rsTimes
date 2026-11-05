# Transform pandas calendar columns

Library date transformations return Pddt and keep its current unit, name,
timezone, order, and missing positions. A result too fine for that unit raises
ValueError; it does not silently upgrade or discard a fractional tail.
Calendar month selection fits a valid day intent to the target month end.
Strict field replacement instead requires a valid complete date.

## Every calendar selector

The following loop actually calls each named selector. Its expected calendar
dates are specified independently from the January 31, 2024 source. The original
nanosecond clock and the missing second row must survive each operation.

```{doctest} pddt-calendar-selectors
>>> from datetime import timedelta
>>> import numpy as np
>>> import pandas as pd
>>> from rstimes import Pddt, Delta
>>> source = Pddt(['2024-01-31T12:34:56.123456789', None], tz='UTC', name='event')
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
>>> for method, args, kwargs, expected in selectors:
...     result = getattr(source, method)(*args, **kwargs)
...     assert type(result) is Pddt and result.unit == 'ns' and result.name == 'event' and result.tz is source.tz
...     assert result.isna().tolist() == [False, True]
...     assert result.isoformat().dropna().tolist() == [expected + 'T12:34:56.123456789+00:00']
>>> source.to_month(0).asi8.tolist() == source.asi8.tolist()
True
```

`to_prev_weekday` and `to_next_weekday` select the weekday in the previous or
next calendar week. Ordinary weekday numbers are Monday=0 through Sunday=6.
Quarter month selections are positions 1–3 within the quarter, not month names.

## Change fields through the right namespace

Use `x.pddt.replace(...)` for strict date-field replacement. Ordinary pandas
index operations retain their own meanings. None preserves an optional date
field; a zero clock sets a real zero. Year zero and negative years are real
years at a unit with enough capacity.

Setting `microsecond` replaces the complete fractional microsecond part and
clears the old nanosecond tail. Setting only `nanosecond` retains microseconds.
When both are explicit, the nanosecond tail applies last.

```{doctest} pddt-field-replacement
>>> fitted = source.to_datetime(month=2, day=31, hour=0, minute=None)
>>> fitted.isoformat().dropna().tolist()
['2024-02-29T00:34:56.123456789+00:00']
>>> source.to_date(month=2, day=31).day.dropna().tolist()
[29.0]
>>> source.to_time(hour=0, nanosecond=0).isoformat().dropna().tolist()
['2024-01-31T00:34:56.123456+00:00']
>>> for fields, fraction in (({'microsecond': 1}, '000001000'), ({'nanosecond': 2}, '123456002'), ({'microsecond': 1, 'nanosecond': 2}, '000001002')):
...     result = source.pddt.replace(**fields)
...     assert type(result) is Pddt and result.unit == 'ns' and result.name == source.name
...     assert result.isna().tolist() == [False, True]
...     assert result.isoformat(timespec='nanoseconds').dropna().tolist() == ['2024-01-31T12:34:56.' + fraction + '+00:00']
>>> source.pddt.replace(day=None).asi8.tolist() == source.asi8.tolist()
True
>>> removed = source.pddt.replace(tzinfo=None)
>>> (removed.tz is None, removed.hour.dropna().tolist())
(True, [12.0])
>>> wide = Pddt(['0001-01-01'], unit='us')
>>> (wide.to_date(year=0).year.tolist(), wide.pddt.replace(year=-1).year.tolist())
([0], [-1])
>>> for call, exception in ((lambda: source.pddt.replace(month=2), ValueError), (lambda: source.to_date(day=32), ValueError), (lambda: source.to_time(hour=25), ValueError), (lambda: source.to_quarter(0, month='February'), TypeError), (lambda: source.to_time(nanosecond=True), TypeError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid field accepted')
>>> source.isoformat().dropna().tolist()
['2024-01-31T12:34:56.123456789+00:00']
```

## Pair row arguments by position

Supported fields, offsets, and selectors accept a scalar or a column of exactly
the receiver's length. Scalar arguments broadcast; a one-element column does
not. Multiple columns pair by position, without pandas label alignment.
Optional field None values preserve that row's old field. Relative counts and
query targets have different roles and reject missing arguments.
Pandas nullable arrays replace a supplied None with pd.NA; that is a missing
target parameter, not the explicit None sentinel. Use an object column when
you intend to retain None as the field-preservation instruction.

```{doctest} pddt-positional-fields
>>> dates = Pddt(['2024-01-31', '2025-03-31', None], unit='us', name='row')
>>> months = pd.Series([2, 4, None], index=['third', 'first', 'second'], dtype=object)
>>> changed = dates.to_date(month=months, day=[31, 30, None])
>>> (changed.year.tolist(), changed.month.tolist(), changed.day.tolist(), changed.isna().tolist())
([2024.0, 2025.0, nan], [2.0, 4.0, nan], [29.0, 30.0, nan], [False, False, True])
>>> changed.year.dtype == np.dtype('float64')
True
>>> dates.add(months=[1, -1, 0]).month.tolist()
[2.0, 2.0, nan]
>>> for call, exception in ((lambda: dates.to_date(day=[1]), ValueError), (lambda: dates.to_day([1, 2]), ValueError), (lambda: dates.add(days=[1, None, 0]), TypeError), (lambda: Pddt([None]).is_day([None]), TypeError), (lambda: dates.to_date(month=pd.array([2, 4, None], dtype='Int64')), TypeError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid row parameter accepted')
```

## Every relative component and final precision

`add` and `sub` accept integer years, quarters, months, weeks, days, hours,
minutes, seconds, milliseconds, microseconds, and nanoseconds. Month components
combine before month-end fitting; fixed components combine before the final
precision check, so exact cancellation is allowed. Use Delta for fractional
fixed durations.

```{doctest} pddt-relative-components
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
>>> for field, expected in components:
...     plus, inverse = source.add(**{field: 1}), source.sub(**{field: -1})
...     assert type(plus) is Pddt and type(inverse) is Pddt
...     assert plus.isoformat().dropna().tolist() == inverse.isoformat().dropna().tolist() == [expected + '+00:00']
...     assert plus.isna().tolist() == inverse.isna().tolist() == [False, True]
>>> source.add(years=1, months=-12).asi8.tolist() == source.asi8.tolist()
True
>>> coarse = Pddt([0, None], unit='us')
>>> coarse.add(microseconds=1, nanoseconds=-1000).asi8.tolist()
[0, -9223372036854775808]
>>> for call in (lambda: coarse.add(nanoseconds=1), lambda: coarse.sub(nanoseconds=1)):
...     try:
...         call()
...     except ValueError:
...         continue
...     raise AssertionError('fraction was silently lost')
>>> for call in (lambda: source.add(hours=1.5), lambda: source.sub(days=True), lambda: source.to_month(None)):
...     try:
...         call()
...     except TypeError:
...         continue
...     raise AssertionError('wrong numeric role accepted')
>>> before = Pddt(['2024-03-09 12:00'], tz='America/New_York')
>>> ((before + Delta(days=1)).hour.tolist(), (before + timedelta(days=1)).hour.tolist())
([12], [13])
```

Calendar moves keep local clock meaning across DST; actual timedelta arithmetic
advances elapsed time. Month-end fitting loses the original day intent, so
adding and then subtracting a month is not generally reversible.
