# Scalar datetimes with Pydt

Pydt is a real `datetime.datetime` subclass. It stores microseconds and years
1–9999, and adds calendar and timezone conveniences. Use Pddt or Pldt for a
nanosecond column or a date range outside that scalar capacity.

## Construct a complete scalar

The constructor defaults to year/month/day 1 and a zero clock. Explicit fields
must form a valid date. Numeric fields use the integer index protocol; floats,
booleans, and numeric strings do not become integer date fields. `fold` is a
separate role: integer 0/1 and real Python/NumPy booleans are accepted.

```{doctest} pydt-constructor
>>> from datetime import date, datetime, time, timedelta, timezone
>>> import numpy as np
>>> from rstimes import Pydt, Configs
>>> Pydt().isoformat()
'0001-01-01T00:00:00'
>>> value = Pydt.__new__(Pydt, np.int64(2024), 2, 29, 12, 34, 56, 123456, tzinfo='UTC', fold=np.bool_(False))
>>> (type(value) is Pydt, isinstance(value, datetime), value.isoformat(), value.fold)
(True, True, '2024-02-29T12:34:56.123456+00:00', 0)
>>> for options in ({'year': 2024.0}, {'year': True}, {'day': '1'}, {'hour': None}):
...     try:
...         Pydt(**options)
...     except TypeError:
...         continue
...     raise AssertionError(options)
>>> for args in ((0, 1, 1), (10000, 1, 1), (2024, 2, 30)):
...     try:
...         Pydt(*args)
...     except ValueError:
...         continue
...     raise AssertionError(args)
>>> Pydt(2024, 1, 1, fold=True).fold
1
```

## Separate wall-clock coordinates from Unix instants

`fromseconds` and `frommicroseconds` decode a naive epoch clock and attach the
requested zone without moving that clock. `fromtimestamp` decodes a POSIX
instant and converts it to the target zone. With no target, `fromtimestamp`
uses naive system-local clock fields. `utcfromtimestamp` returns aware UTC.

```{doctest} pydt-numeric-factories
>>> attached = Pydt.fromseconds(0, 'Asia/Shanghai')
>>> converted = Pydt.fromtimestamp(0, 'Asia/Shanghai')
>>> (type(attached) is Pydt, attached.isoformat(), converted.isoformat())
(True, '1970-01-01T00:00:00+08:00', '1970-01-01T08:00:00+08:00')
>>> Pydt.frommicroseconds(-1).isoformat()
'1969-12-31T23:59:59.999999'
>>> Pydt.utcfromtimestamp(0).isoformat()
'1970-01-01T00:00:00+00:00'
>>> Pydt.frommicroseconds(0, 'Asia/Shanghai').isoformat()
'1970-01-01T00:00:00+08:00'
```

`fromseconds` also supports its documented real float conversion protocol.
It rounds a floating value to seven decimal places and then discards the
seventh digit at the microsecond destination. `frommicroseconds` requires an
integer index and does not truncate an integral float. Boolean inputs and
text/byte input are rejected by these numeric factories.

```{doctest} pydt-seconds-protocol
>>> from decimal import Decimal
>>> calls = []
>>> class Seconds:
...     def __float__(self):
...         calls.append(1)
...         return 1.5
>>> (Pydt.fromseconds(Seconds()).isoformat(), calls)
('1970-01-01T00:00:01.500000', [1])
>>> Pydt.fromseconds(Decimal('1.5')).isoformat()
'1970-01-01T00:00:01.500000'
>>> for invalid in (1.0, True, '1'):
...     try:
...         Pydt.frommicroseconds(invalid)
...     except TypeError:
...         continue
...     raise AssertionError(invalid)
>>> for factory in (Pydt.fromseconds, Pydt.frommicroseconds, Pydt.fromtimestamp, Pydt.utcfromtimestamp):
...     try:
...         factory(True)
...     except TypeError:
...         continue
...     raise AssertionError(factory.__name__)
```

## Use calendar factories

`fromordinal` uses a Gregorian ordinal with 1=0001-01-01. ISO weeks are
one-based and use Monday=1 through Sunday=7, unlike `weekday()`'s Monday=0.
High ISO week/day numbers select the ISO year's last real week/Sunday.
`fromdayofyear` similarly limits a high positive day to that year's last day.
Values below 1 are errors. The final date must still fit Pydt.

```{doctest} pydt-calendar-factories
>>> factories = (Pydt.fromordinal(738945), Pydt.fromisocalendar(2024, 9, 4), Pydt.fromdayofyear(2024, 60))
>>> [(type(item) is Pydt, item.isoformat()) for item in factories]
[(True, '2024-02-29T00:00:00'), (True, '2024-02-29T00:00:00'), (True, '2024-02-29T00:00:00')]
>>> (Pydt.fromisocalendar(2024, 99, 99).isoformat(), Pydt.fromdayofyear(2024, 999).isoformat())
('2024-12-29T00:00:00', '2024-12-31T00:00:00')
>>> Pydt.fromisocalendar(2015, 53, 7).isoformat()
'2016-01-03T00:00:00'
>>> for call in (lambda: Pydt.fromordinal(0), lambda: Pydt.fromisocalendar(2024, 0, 1), lambda: Pydt.fromdayofyear(2024, 0)):
...     try:
...         call()
...     except ValueError:
...         continue
...     raise AssertionError('nonpositive calendar coordinate accepted')
```

## Copy date or datetime fields

`fromdate` copies only the calendar date at midnight: source clock, timezone,
and fold do not contribute. `fromdatetime` retains the real date, clock, zone,
and fold; an explicit non-None `tz` replaces the zone while keeping the clock.
Its `tz=None` retains the source timezone. Use an explicit timezone-removal
operation when that is your task.

`fromdatetime64` reads one NumPy datetime64 scalar, including a dtype multiplier.
It floors finer input to microseconds, rejects NaT, and attaches an optional
zone without converting the decoded clock.

```{doctest} pydt-source-factories
>>> source = datetime(2024, 5, 7, 9, 30, tzinfo=timezone(timedelta(hours=8)), fold=1)
>>> (Pydt.fromdate(source).isoformat(), Pydt.fromdate(source, 'UTC').isoformat())
('2024-05-07T00:00:00', '2024-05-07T00:00:00+00:00')
>>> copied = Pydt.fromdatetime(source)
>>> (type(copied) is Pydt, copied.isoformat(), copied.fold, copied.tzinfo is source.tzinfo)
(True, '2024-05-07T09:30:00+08:00', 1, True)
>>> Pydt.fromdatetime(source, 'UTC').isoformat()
'2024-05-07T09:30:00+00:00'
>>> (Pydt.fromdatetime64(np.datetime64(-1, 'ns')).isoformat(), Pydt.fromdatetime64(np.datetime64(1, '10D')).isoformat())
('1969-12-31T23:59:59.999999', '1970-01-11T00:00:00')
>>> try:
...     Pydt.fromdatetime64(np.datetime64('NaT'))
... except ValueError as error:
...     print(type(error).__name__)
ValueError
```

## Combine a date and a clock

The date argument contributes only Y/M/D. The time argument contributes its
clock, timezone, and fold. An explicit zone attaches to those fields without
converting the clock. With `date=None` the factory uses today; with `time=None`
it uses midnight.

```{doctest} pydt-combine
>>> clock = time(9, 30, tzinfo=timezone(timedelta(hours=8)))
>>> combined = Pydt.combine(date(2024, 5, 7), clock)
>>> (type(combined) is Pydt, combined.isoformat())
(True, '2024-05-07T09:30:00+08:00')
>>> Pydt.combine(date(2024, 5, 7), clock, tz='UTC').isoformat()
'2024-05-07T09:30:00+00:00'
>>> Pydt.combine(date(2024, 5, 7), None).isoformat()
'2024-05-07T00:00:00'
>>> before = date.today()
>>> today_midnight = Pydt.combine()
>>> after = date.today()
>>> (today_midnight.date() in (before, after), today_midnight.time() == time())
(True, True)
```

## Parse ordinary, ISO, or formatted text

`Pydt.parse` uses the shared [parser rules](parsing.md) and returns Pydt.
`fromisoformat` is the dedicated ISO entry. `strptime` uses an explicit shared
format and effective Configs; a missing year in that format defaults to 1900.
Fractional seconds may be read more finely, then truncated once at the
microsecond output.

```{doctest} pydt-text-factories
>>> config = Configs()
>>> config.add_month('harvest', 10)
True
>>> parsed = Pydt.parse('7 harvest 2024', cfg=config)
>>> formatted = Pydt.strptime('7 harvest 2024', '%d %b %Y', cfg=config)
>>> (type(parsed) is Pydt, parsed.isoformat(), formatted.isoformat())
(True, '2024-10-07T00:00:00', '2024-10-07T00:00:00')
>>> Pydt.fromisoformat('2024-05-07T09:30:00.123456789+00:00').isoformat()
'2024-05-07T09:30:00.123456+00:00'
>>> Pydt.strptime('2024-05-07 09:30:00.123456789', '%Y-%m-%d %H:%M:%S.%f').microsecond
123456
>>> Pydt.strptime('12:30.5', '%H:%M.%f').isoformat()
'1900-01-01T12:30:00.500000'
```

## Read the current time

`now(tz=None)` and `today()` return complete naive local date and clock fields;
today does not normalize to midnight. `utcnow()` returns aware UTC. An explicit
zone in `now` converts the current instant to that zone. These examples check
types and clock-read bounds, not a fixed display time.

```{doctest} pydt-current-time
>>> before = datetime.now(timezone.utc)
>>> current_utc, explicit_utc = Pydt.utcnow(), Pydt.now('UTC')
>>> after = datetime.now(timezone.utc)
>>> all(type(item) is Pydt and item.utcoffset() == timedelta(0) and before <= item <= after for item in (current_utc, explicit_utc))
True
>>> before = datetime.now()
>>> local_now, local_today = Pydt.now(), Pydt.today()
>>> after = datetime.now()
>>> all(type(item) is Pydt and item.tzinfo is None and before <= item <= after for item in (local_now, local_today))
True
```

## Keep parser defaults and input roles explicit

The Pydt parsing wrapper retains the shared parser's ordering, strictness, and
timezone options. A datetime input keeps its own timezone; `ignoretz` controls
text. A complete default supplies missing date fields and fold, but does not
supply a default clock or timezone.

```{doctest} pydt-parser-option-branches
>>> (Pydt.parse('01/02/2024', dayfirst=True).isoformat(), Pydt.parse('01/02/2024', dayfirst=False).isoformat())
('2024-02-01T00:00:00', '2024-01-02T00:00:00')
>>> (Pydt.parse('2024-01-02T08:00:00+08:00').isoformat(), Pydt.parse('2024-01-02T08:00:00+08:00', ignoretz=False).isoformat())
('2024-01-02T08:00:00', '2024-01-02T08:00:00+08:00')
>>> Pydt.parse('February 29', default=datetime(2024, 1, 1, 12, tzinfo=timezone.utc, fold=1)).isoformat()
'2024-02-29T00:00:00'
>>> Pydt.parse('2024-02-31').isoformat()
'2024-02-29T00:00:00'
>>> try:
...     Pydt.parse('2024-02-31', strict=True)
... except ValueError as error:
...     print(type(error).__name__)
ParseError
>>> Pydt.parse('2024-02-29', isoformat=False).isoformat()
'2024-02-29T00:00:00'
>>> Pydt.parse(np.datetime64(-1, 'ns')).isoformat()
'1969-12-31T23:59:59.999999'
>>> Pydt.parse(0).isoformat()
'1970-01-01T00:00:00'
>>> for option in ('yearfirst', 'dayfirst', 'ignoretz', 'isoformat', 'strict'):
...     try:
...         Pydt.parse('2024-01-02', **{option: 1})
...     except TypeError:
...         continue
...     raise AssertionError(option)
>>> for call in (lambda: Pydt.fromdate('2024-01-02'), lambda: Pydt.fromdatetime(date(2024, 1, 2)), lambda: Pydt.fromdatetime64(0)):
...     try:
...         call()
...     except TypeError:
...         continue
...     raise AssertionError('factory source role was bypassed')
>>> Pydt.combine('2024-01-02T18:00:00+02:00', '09:30:00+08:00').isoformat()
'2024-01-02T09:30:00+08:00'
```

## Preserve subclasses through factories

The date factories produce the requested Pydt subtype. Calendar-coordinate
factories accept real integer-index values and attach a requested timezone to
midnight; they do not reinterpret that calendar date as a UTC instant.

```{doctest} pydt-factory-subtypes-and-index
>>> class BusinessDate(Pydt):
...     pass
>>> factories = [lambda: BusinessDate.parse('2024-02-29'), lambda: BusinessDate.fromdate(date(2024, 2, 29)), lambda: BusinessDate.fromdatetime(datetime(2024, 2, 29)), lambda: BusinessDate.fromdatetime64(np.datetime64('2024-02-29')), lambda: BusinessDate.fromisoformat('2024-02-29'), lambda: BusinessDate.strptime('2024-02-29', '%Y-%m-%d'), lambda: BusinessDate.combine(date(2024, 2, 29)), lambda: BusinessDate.fromordinal(np.int64(738945)), lambda: BusinessDate.fromisocalendar(2024, 9, 4), lambda: BusinessDate.fromdayofyear(2024, 60)]
>>> for factory in factories:
...     result = factory()
...     assert type(result) is BusinessDate and result.isoformat() == '2024-02-29T00:00:00'
>>> for factory, arguments in ((Pydt.fromordinal, (738945,)), (Pydt.fromisocalendar, (2024, 9, 4)), (Pydt.fromdayofyear, (2024, 60))):
...     result = factory(*arguments, tz='Asia/Shanghai')
...     assert result.isoformat() == '2024-02-29T00:00:00+08:00'
...     for invalid in (True, 1.0, None):
...         try:
...             factory(invalid, *arguments[1:])
...         except TypeError:
...             continue
...         raise AssertionError((factory.__name__, invalid))
>>> for factory in (BusinessDate.fromseconds, BusinessDate.frommicroseconds, BusinessDate.fromtimestamp):
...     assert type(factory(0, 'UTC')) is BusinessDate and factory(0, 'UTC').isoformat() == '1970-01-01T00:00:00+00:00'
>>> assert type(BusinessDate.utcfromtimestamp(0)) is BusinessDate
```

The [Pydt API reference](../api/reference/rstimes/pydt/index.rst) lists every
signature. Calendar selection, strict replacement, timezone transitions,
rounding, queries, and output are described in the following scalar guides.
