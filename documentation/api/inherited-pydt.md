# Scalar fields and datetime protocols

Pydt is a datetime subclass. The entries below are inherited datetime/object
features or native adapters for those features. They are available on the
actual Pydt object. Library calendar and timezone extensions have their own
[API reference](reference/rstimes/pydt/index.rst).

## Stored fields and bounds

These are read-only attributes; they take no call arguments. Date values use
the Gregorian calendar. The final stored precision is one microsecond.

| Entry | Type and meaning |
|---|---|
| <span id="rstimes.Pydt.year"></span>`year` | int, 1–9999. |
| <span id="rstimes.Pydt.month"></span>`month` | int, 1–12. |
| <span id="rstimes.Pydt.day"></span>`day` | int, 1 through the selected month's length. |
| <span id="rstimes.Pydt.hour"></span>`hour` | int, 0–23. |
| <span id="rstimes.Pydt.minute"></span>`minute` | int, 0–59. |
| <span id="rstimes.Pydt.second"></span>`second` | int, 0–59. |
| <span id="rstimes.Pydt.microsecond"></span>`microsecond` | int, 0–999999. |
| <span id="rstimes.Pydt.fold"></span>`fold` | int, 0 or 1; selects a repeated local occurrence. |
| <span id="rstimes.Pydt.tzinfo"></span>`tzinfo` | Stored tzinfo object or None; reading it does not convert the clock. |
| <span id="rstimes.Pydt.min"></span>`min` | Builtin datetime, 0001-01-01 at midnight. |
| <span id="rstimes.Pydt.max"></span>`max` | Builtin datetime, 9999-12-31 at 23:59:59.999999. |
| <span id="rstimes.Pydt.resolution"></span>`resolution` | Builtin timedelta of one microsecond. |

The [calendar guide](../guides/pydt-calendar.md) verifies each stored calendar
and clock field. [Timezone examples](../guides/pydt-timezones.md) verify fold,
stored zones, gaps, and real offsets.

## Output methods

| Entry | Parameters and result | Boundary or related method |
|---|---|---|
| <span id="rstimes.Pydt.date"></span>`date()` | No arguments; builtin date with Y/M/D. | Drops clock and timezone. |
| <span id="rstimes.Pydt.time"></span>`time()` | No arguments; builtin time. | Keeps fold, drops timezone. |
| <span id="rstimes.Pydt.timetz"></span>`timetz()` | No arguments; builtin time with stored timezone and fold. | A regional offset may require a date. |
| <span id="rstimes.Pydt.toordinal"></span>`toordinal()` | No arguments; int Gregorian day, 1=0001-01-01. | Ignores the clock and timezone. |
| <span id="rstimes.Pydt.isocalendar"></span>`isocalendar()` | No arguments; ISO year/week/weekday named tuple. | Weekday is Monday=1 through Sunday=7. |
| <span id="rstimes.Pydt.isoformat"></span>`isoformat(sep='T', timespec='auto')` | Text with requested clock precision and effective offset. | Omitted digits are truncated; invalid timespec raises ValueError. |
| <span id="rstimes.Pydt.ctime"></span>`ctime()` | No arguments; system-style weekday/month text. | Contains no offset or fractional seconds. |
| <span id="rstimes.Pydt.timestamp"></span>`timestamp()` | No arguments; float POSIX seconds. | Naive values use the system local timezone; see explicit-zone examples. |
| <span id="rstimes.Pydt.utctimetuple"></span>`utctimetuple()` | No arguments; time.struct_time in UTC for aware dates. | Naive clock stays unchanged; tm_isdst=0. |
| <span id="rstimes.Pydt.utcoffset"></span>`utcoffset()` | No arguments; actual timezone timedelta or None. | Invalid timezone callback results raise their standard errors. |
| <span id="rstimes.Pydt.tzname"></span>`tzname()` | No arguments; timezone name or None. | Uses the actual stored timezone callback. |

See [scalar output](../guides/pydt-output.md) for types, precision, local/UTC
containers, and each output call on Pydt.

## Comparisons and object protocols

| Entry | Parameters and result | Responsibility |
|---|---|---|
| <span id="rstimes.Pydt.__eq__"></span>`__eq__(other)` | bool or NotImplemented. | Ordinary datetime equality; actual Timestamp nanoseconds are retained. |
| <span id="rstimes.Pydt.__ne__"></span>`__ne__(other)` | bool or NotImplemented. | Ordinary inequality; naive versus aware compares unequal. |
| <span id="rstimes.Pydt.__lt__"></span>`__lt__(other)` | bool or NotImplemented. | Earlier than; naive/aware ordering raises TypeError. |
| <span id="rstimes.Pydt.__le__"></span>`__le__(other)` | bool or NotImplemented. | Earlier than or equal; same input responsibilities. |
| <span id="rstimes.Pydt.__gt__"></span>`__gt__(other)` | bool or NotImplemented. | Later than; same input responsibilities. |
| <span id="rstimes.Pydt.__ge__"></span>`__ge__(other)` | bool or NotImplemented. | Later than or equal; same input responsibilities. |
| <span id="rstimes.Pydt.__hash__"></span>`__hash__()` | int. | Compatible with equal ordinary datetimes; metadata is outside the date value. |
| <span id="rstimes.Pydt.__rsub__"></span>`__rsub__(other)` | timedelta for an ordinary datetime left operand, or NotImplemented. | Standard reflected datetime subtraction; the left operand can own a more specific implementation. |
| <span id="rstimes.Pydt.__str__"></span>`__str__()` | str. | ISO-like output with a space separator. |
| <span id="rstimes.Pydt.__init__"></span>`__init__(*args, **kwargs)` | None. | Inherited initializer does not change the immutable fields created by __new__. |
| <span id="rstimes.Pydt.__getstate__"></span>`__getstate__()` | None, dictionary, or a dictionary/slots pair. | Object metadata for copy/pickle; date fields use a separate reconstruction recipe. |

Direct methods returning NotImplemented allow Python's reflected negotiation.
The operator raises TypeError when both sides decline. Full executable
comparison, copy, state, and error examples are in
[scalar protocols](../guides/pydt-protocols.md) and
[scalar interoperability](../guides/pydt-interop.md).

```{doctest} pydt-inherited-entry-forms
>>> from datetime import datetime, timedelta, timezone
>>> from rstimes import Pydt
>>> value = Pydt(2024, 2, 29, 12, 34, 56, 123456, tzinfo='UTC', fold=1)
>>> (value.year, value.month, value.day, value.hour, value.minute, value.second, value.microsecond, value.fold)
(2024, 2, 29, 12, 34, 56, 123456, 1)
>>> (value.tzinfo is timezone.utc, value.tzname(), value.utcoffset())
(True, 'UTC', datetime.timedelta(0))
>>> (value.time().fold, value.timetz().fold, value.__str__())
(1, 1, '2024-02-29 12:34:56.123456+00:00')
>>> value.__getstate__() is None
True
>>> value.__rsub__(object()) is NotImplemented
True
>>> value.__init__() is None
True
>>> value.__hash__() == hash(datetime(2024, 2, 29, 12, 34, 56, 123456, tzinfo=timezone.utc))
True
```

The [standard datetime reference](https://docs.python.org/3/library/datetime.html#datetime-objects)
documents the inherited signatures in full. The scalar guides show the actual
Pydt return types and its separate regional-time and precision rules.
