# Calendar changes with Delta

`Delta` holds relative amounts and optional absolute date or clock settings.
Plural arguments add a relative amount. Singular arguments select a field.
The original date is unchanged.

## Month ends

Moving January 31 forward one month reaches the final day of February. The
reverse move starts from that new day, so it need not return January 31.

```{doctest} delta-month-end
>>> from datetime import date, timedelta
>>> from rstimes import Delta
>>> leap_day = date(2024, 1, 31) + Delta(months=1)
>>> (type(leap_day) is date, leap_day.isoformat())
(True, '2024-02-29')
>>> (leap_day - Delta(months=1)).isoformat()
'2024-01-29'
```

## Nanoseconds and the destination

Delta combines fixed amounts in nanoseconds. A remainder of 1,001 nanoseconds
contains one microsecond and one nanosecond. Standard `timedelta` has microsecond
resolution: conversion rounds at that destination, using ties to even.

```{doctest} delta-nanoseconds
>>> span = Delta(nanoseconds=1001)
>>> (span.microseconds, span.nanoseconds)
(1, 1)
>>> result = span.to_timedelta()
>>> (type(result) is timedelta, result == timedelta(microseconds=1))
(True, True)
```

Half a nanosecond rounds to the even nanosecond when Delta is constructed.
Projection to a datetime or timedelta then applies that destination's separate
microsecond rounding. The source's microsecond coordinate matters.

```{doctest} delta-rounding-destinations
>>> from datetime import datetime
>>> (Delta(nanoseconds=0.5), Delta(nanoseconds=1.5), Delta(nanoseconds=2.5)) == (Delta(), Delta(nanoseconds=2), Delta(nanoseconds=2))
True
>>> Delta(nanoseconds=1500).to_timedelta() == timedelta(microseconds=2)
True
>>> start = datetime(2024, 1, 1, microsecond=1)
>>> (start + Delta(nanoseconds=500)).microsecond
2
>>> Delta(nanoseconds=500).to_timedelta(start) == timedelta(microseconds=1)
True
>>> (date(2024, 1, 1) - Delta(nanoseconds=1)).isoformat()
'2023-12-31'
>>> (datetime(2024, 1, 1) - Delta(nanoseconds=1)).isoformat()
'2024-01-01T00:00:00'
```

## Read the normalized fields

Relative years, quarters, and months normalize together. Weeks and all smaller
fixed units normalize into days and a nonnegative clock remainder. A year is
not converted into a fixed number of days. There are eight relative properties;
quarters, weeks, and milliseconds are constructor inputs rather than separate
normalized properties.

```{doctest} delta-relative-fields
>>> change = Delta(years=1, quarters=1, months=10, weeks=1, days=2, hours=3, minutes=4, seconds=5, milliseconds=6, microseconds=7, nanoseconds=8)
>>> relative_fields = ('years', 'months', 'days', 'hours', 'minutes', 'seconds', 'microseconds', 'nanoseconds')
>>> tuple(getattr(change, field) for field in relative_fields)
(2, 1, 9, 3, 4, 5, 6007, 8)
>>> all(type(getattr(change, field)) is int for field in relative_fields)
True
>>> negative = Delta(nanoseconds=-1)
>>> tuple(getattr(negative, field) for field in relative_fields)
(0, 0, -1, 23, 59, 59, 999999, 999)
```

Nine absolute properties record independent settings. An unset property is
`None`; clock zero and weekday zero are real settings. `millisecond` combines
with the last three digits of `microsecond` to form the stored microsecond
setting. `nanosecond` selects the tail after the six microsecond digits.

```{doctest} delta-absolute-fields
>>> settings = Delta(year=2024, month=2, day=29, weekday=3, hour=0, minute=1, second=2, millisecond=3, microsecond=456789, nanosecond=10)
>>> absolute_fields = ('year', 'month', 'day', 'weekday', 'hour', 'minute', 'second', 'microsecond', 'nanosecond')
>>> tuple(getattr(settings, field) for field in absolute_fields)
(2024, 2, 29, 3, 0, 1, 2, 3789, 10)
>>> tuple(getattr(Delta(), field) for field in absolute_fields)
(None, None, None, None, None, None, None, None, None)
>>> (bool(Delta()), bool(Delta(hour=0)), bool(Delta(nanosecond=0)))
(False, True, True)
>>> bounded = Delta(year=10000, month=13, day=32)
>>> (bounded.year, bounded.month, bounded.day)
(9999, 12, 31)
```

Absolute year, month, and day must be positive, with the upper limits shown
above. Weekday is Monday=0 through Sunday=6. Other clock fields use their
ordinary ranges; an absolute nanosecond must be 0 through 999. These absolute
settings do not extend the destination's supported years.

## Combine changes or apply them in sequence

Adding two Deltas adds relative amounts and takes each explicitly set absolute
field from the right. Subtracting keeps the left's absolute field, taking the
right's only when the left has none. Subtraction reverses relative amounts and
leaves absolute settings intact.

```{doctest} delta-merge
>>> (Delta(months=2, hour=9) + Delta(months=1, hour=0)) == Delta(months=3, hour=0)
True
>>> (Delta(months=2, hour=9) - Delta(months=1, hour=0)) == Delta(months=1, hour=9)
True
>>> (-Delta(days=1, month=2)).days, (-Delta(days=1, month=2)).month
(-1, 2)
>>> absolute_span = abs(Delta(days=-2, hours=3))
>>> (type(absolute_span) is Delta, absolute_span.days, absolute_span.hours)
(True, 1, 21)
>>> combined = Delta(nanosecond=2) + Delta(microsecond=1)
>>> (combined.microsecond, combined.nanosecond)
(1, 2)
```

Merging is a field operation. Applying the two Deltas successively can have a
different result. In particular, applying an absolute microsecond without an
absolute nanosecond clears the source's nanosecond tail. The
[nanosecond interoperability guide](delta-interop.md) demonstrates this on a
nanosecond timestamp.

## Get a standard time span

Without a start, `to_timedelta()` accepts only fixed relative amounts. Supply a
date or datetime start for calendar years, months, or absolute settings. The
anchored result follows `(start + delta) - start`; a date start therefore
returns whole days. A standard datetime sharing one timezone object uses
Python's wall-clock subtraction semantics. A pandas Timestamp start keeps
nanoseconds through the elapsed difference before the final conversion.

```{doctest} delta-anchored-span
>>> leap_span = Delta(months=1).to_timedelta(date(2024, 1, 31))
>>> (type(leap_span) is timedelta, leap_span.days)
(True, 29)
>>> try:
...     Delta(months=1).to_timedelta()
... except ValueError as error:
...     print(type(error).__name__)
ValueError
>>> (Delta(days=1) + timedelta(hours=2)) == Delta(days=1, hours=2)
True
>>> (timedelta(hours=2) + Delta(days=1)) == Delta(days=1, hours=2)
True
>>> (Delta(days=1) - timedelta(hours=2)) == Delta(hours=22)
True
>>> (timedelta(hours=2) - Delta(days=1)) == Delta(days=-1, hours=2)
True
```

## Validate inputs by their role

Relative years, quarters, months, and absolute settings accept integers and
the integer index protocol. Fixed amounts from weeks through nanoseconds also
accept Python floats and NumPy float16/32/64. Booleans, numeric strings,
Decimal, Fraction, complex values, and arbitrary `float()` adapters do not
become numeric date fields. `None` is reserved for unset absolute settings.
NaN raises `ValueError`; infinities and values exceeding the checked range
raise `OverflowError`.

```{doctest} delta-input-errors
>>> from decimal import Decimal
>>> from fractions import Fraction
>>> import numpy as np
>>> class Count:
...     def __index__(self):
...         return 2
>>> Delta(months=Count()).months
2
>>> rejected = ({'years': 1.0}, {'days': True}, {'hours': np.bool_(False)}, {'nanoseconds': None}, {'nanosecond': True}, {'seconds': Decimal('1')}, {'seconds': Fraction(1, 2)}, {'hour': 1.0})
>>> for arguments in rejected:
...     try:
...         Delta(**arguments)
...     except TypeError:
...         continue
...     raise AssertionError(arguments)
>>> for value in (-1, 1000):
...     try:
...         Delta(nanosecond=value)
...     except ValueError:
...         continue
...     raise AssertionError(value)
>>> for field in ('year', 'month', 'day'):
...     try:
...         Delta(**{field: 0})
...     except ValueError:
...         continue
...     raise AssertionError(field)
>>> for value, error_type in ((float('nan'), ValueError), (float('inf'), OverflowError), (2**63, OverflowError)):
...     try:
...         Delta(days=value)
...     except error_type:
...         continue
...     raise AssertionError(value)
>>> (Delta(seconds=np.float32(0.5)).microseconds, Delta(nanoseconds=np.int64(7)).nanoseconds)
(500000, 7)
```

See [copying and protocols](delta-protocols.md) for immutability, equality,
ordered batches, subclass state, and persistence. Full parameter signatures
are in the [Delta reference](../api/reference/rstimes/delta/index.rst).
