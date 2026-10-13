# Delta API guide

`rstimes.Delta` represents calendar changes. Relative amounts add time; absolute
settings choose parts of the result. Values keep their fields after construction.

```python
from datetime import date, datetime, timedelta
from rstimes import Delta

end = date(2024, 1, 31) + Delta(months=1)  # 2024-02-29
span = Delta(hours=1.5).to_timedelta()    # timedelta(hours=1, minutes=30)
```

## Calendar moves and absolute settings

`hours=25` adds one day and one hour. `hour=25` sets the hour to 23.
Negative absolute settings mean unset; year/month/day zero also mean unset.
Setting an absolute clock part to zero is meaningful.

Month ends use the last available day. January 31 plus one month becomes
February 29 in a leap year. Subtracting one month then gives January 29.
These two calendar moves are not inverses.

When adding Delta values, a setting on the right wins. When subtracting, a
setting on the left remains, with the right supplying one only if the left has
none. Thus `Delta(hour=9) - Delta(hour=9)` still sets hour 9 and is truthy.

Fractional weeks through microseconds are combined and rounded once to the
nearest microsecond, with half values rounded to even. Integer parts remain
exact even above `2**53`. Fractional years, quarters, months and absolute
settings keep their existing integer conversion rule.

## Values, equality and dictionary keys

A Delta's fields cannot be overwritten. Repeated `__init__` does not change the
value. Construct another Delta to express a different change.

Delta values compare with other Delta values, including subclasses that inherit
the same behavior. Equal values have equal hashes. Other kinds are unsupported
by Delta's comparison methods; Python can also consult the other object's
comparison. Sorting Delta values is unsupported.

## Subclasses

Put Delta fields in `__new__` and additional attributes in `__init__`:

```python
class NamedDelta(Delta):
    def __new__(cls, name, **changes):
        return Delta.__new__(cls, **changes)

    def __init__(self, name, **changes):
        self.name = name

change = NamedDelta("next day", days=1)
```

Date and datetime operations try the input's class when creating a changed
result. Custom constructors and operators keep their normal role. An unchanged
date or datetime result can be the original object.

## Ordered batches

`delta.apply_many(values)` returns the same ordered results as
`[value + delta for value in values]`. Lists, tuples and generators are accepted.
Supported operands include dates, datetimes, Delta, timedelta, valid
relativedelta, NumPy date/time scalars, and mixtures of these kinds. Subclass
operators are honored. A failed item raises an error; no partial list is
returned, and an iterator's already consumed items are not restored.

```python
change = Delta(days=1)
results = change.apply_many([date(2024, 1, 31), timedelta(hours=2)])
```

## Exact time spans

`to_timedelta()` without a start accepts fixed relative units only: no relative
years/months and no absolute settings. With a date or datetime start, it returns
`(start + delta) - start`. A date start gives whole days. Same-timezone datetime
subtraction follows Python's clock-time rules, including daylight saving changes.
Calendar months are not approximated as a number of days.

```python
Delta(months=1).to_timedelta(date(2024, 1, 31))  # timedelta(days=29)
```

## Converting relativedelta

`Delta.from_relativedelta(rd)` keeps supported fields and applies Delta's usual
absolute limits. Any weekday setting and any nonzero leapdays value raise
`ValueError`; their date rules cannot be represented by Delta. The same checks
apply to arithmetic involving relativedelta. `leapdays=0` is accepted.

## Copying and saving

Use `copy.copy`, `copy.deepcopy` and `pickle` normally. Copies are separate
objects and preserve the Delta type. Subclass attributes, shared values and
cycles follow shallow/deep copying rules. Loading restores the full value
before its additional attributes. Only load pickle from trusted sources.

## Limits and local demo

Integers and checked arithmetic use the signed 64-bit range. Absolute settings
are limited as described below; relative months and clock parts are normalized.
A date result must fit Python's supported date range. This project's acceptance
covers ordinary CPython 3.13 on macOS arm64.

Run `python demo/delta.py` from the project root. Each `xxx_demo` function can be
run independently, including `datetime_demo`, `pydt_demo`, `apply_many_demo`,
`to_timedelta_demo` and `wide_integer_demo`. It compares original and Rust results,
checks approved changes and prints paired timings. Demo timings are for
exploration; the project's benchmark reports provide performance acceptance.

## Constructor reference

Calendar changes with relative amounts and absolute replacements.

Add a Delta to a date or datetime to move it, set selected parts, or both.
A Delta keeps its value after construction. Its 15 field properties are read-only.

Parameters
----------
years : int, default 0
    Years to add.
quarters : int, default 0
    Quarters to add; each quarter is three months.
months : int, default 0
    Months to add; every twelve months become one year.
weeks : int or float, default 0
    Weeks to add; each week is seven days.
days : int or float, default 0
    Days to add. This positional parameter follows weeks.
hours : int or float, default 0
    Hours to add.
minutes : int or float, default 0
    Minutes to add.
seconds : int or float, default 0
    Seconds to add.
milliseconds : int or float, default 0
    Milliseconds to add; one millisecond is 1000 microseconds.
microseconds : int or float, default 0
    Microseconds to add. Combined fractions round once to the nearest microsecond;
    an exact halfway value rounds to the even microsecond.
year : int, default -1
    Year to set. Positive values above 9999 become 9999; zero or negative means unset.
month : int, default -1
    Month to set. Positive values above 12 become 12; zero or negative means unset.
day : int, default -1
    Day to set. Positive values above 31 become 31; zero or negative means unset.
weekday : int, default -1
    Day of the week to set, Monday=0 through Sunday=6. Larger values become 6;
    negative means unset. This selects a day in the same Monday-to-Sunday week.
hour : int, default -1
    Hour to set, limited to 23. Negative means unset; zero is a real setting.
minute : int, default -1
    Minute to set, limited to 59. Negative means unset.
second : int, default -1
    Second to set, limited to 59. Negative means unset.
millisecond : int, default -1
    Millisecond part to set, limited to 999. If set, it replaces the millisecond
    part of microsecond, which then supplies only its last three digits.
microsecond : int, default -1
    Microsecond to set, limited to 999999 when millisecond is unset.
    Negative means unset.

Raises
------
TypeError
    An argument name, count or numeric conversion is unsupported.
OverflowError
    An integer or a calculation is outside the signed 64-bit range.
ValueError
    A fractional duration is NaN.

Notes
-----
Relative amounts are carried into larger units. For example, 25 hours become
one day and one hour; -1 hour becomes -1 day and 23 hours. Fractional years,
quarters, months and absolute settings discard their fractional part.
Objects providing __int__ can supply integer values.

Date operations set absolute parts, add relative amounts, then adjust weekday.
A missing day at month end becomes that month's last day. These moves need not
be reversible: January 31 plus one month, then minus one month, may end on
January 29. Dates outside Python's supported range raise an error.

Delta values compare by their fields with other Delta values, including
subclasses that inherit the same behavior. Equal values have equal, stable
hashes. Calling __init__ again leaves the value unchanged. Create another Delta
to use different values. Sorting Delta values is unsupported.

Examples
--------
>>> from datetime import date
>>> date(2024, 1, 31) + Delta(months=1)
datetime.date(2024, 2, 29)
>>> (Delta(hours=1.5).hours, Delta(hours=1.5).minutes)
(1, 30)
>>> d = Delta(microseconds=-1)
>>> (d.days, d.hours, d.minutes, d.seconds, d.microseconds)
(-1, 23, 59, 59, 999999)
>>> Delta(millisecond=2, microsecond=123456).microsecond
2456

## Method reference

### from_relativedelta

Create a Delta from supported relativedelta fields.

Parameters
----------
rd : dateutil.relativedelta
    Relative amounts and absolute settings to convert.

Returns
-------
Delta
    A new Delta, including when called through a Delta subclass.

Raises
------
InvalidRelativeDelta
    rd is not a relativedelta instance.
ValueError
    weekday is set or leapdays is nonzero; Delta cannot preserve those rules.
OverflowError
    A converted value or calculation is outside the supported integer range.

Notes
-----
The usual Delta rules for absolute settings still apply. Errors from custom
normalization or numeric conversion are passed to the caller.

Examples
--------
>>> from dateutil.relativedelta import relativedelta
>>> Delta.from_relativedelta(relativedelta(months=1)).months
1

### apply_many

Add this Delta to each value and return the results in order.

Parameters
----------
values : iterable
    Values supporting value + self, including dates, datetimes, Delta,
    timedelta, supported third-party scalars, or a mixture of these.

Returns
-------
list
    One result per input, with the same values and types as
    [value + self for value in values]. An empty input returns [].

Raises
------
TypeError
    values is not iterable or an item does not support addition.
Exception
    Errors from iteration or addition propagate. No partial list is
    returned; a consumed iterator is not rewound.

Examples
--------
>>> Delta(days=1).apply_many([date(2024, 1, 1), date(2024, 1, 2)])
[datetime.date(2024, 1, 2), datetime.date(2024, 1, 3)]

### to_timedelta

Convert this Delta to an exact standard-library time span.

Parameters
----------
start : date or datetime, optional
    Starting value for calendar years, months or absolute replacements.
    With a start, the result is (start + self) - start.

Returns
-------
datetime.timedelta
    The fixed span, or the difference at the supplied starting value.

Raises
------
ValueError
    No start was supplied for years, months or an absolute replacement.
TypeError
    start is not a date or datetime.
OverflowError
    The fixed span is outside timedelta's supported range.

Notes
-----
A date start gives a whole-day difference. For datetimes in the same
time zone, Python's wall-clock subtraction rules apply across clock changes.
Months are never approximated as a fixed number of days. Errors from
applying the Delta to the starting value propagate.

Examples
--------
>>> Delta(hours=25).to_timedelta()
datetime.timedelta(days=1, seconds=3600)
>>> Delta(months=1).to_timedelta(date(2024, 1, 31))
datetime.timedelta(days=29)

### __add__

Add a Delta, timedelta, relativedelta, date/datetime or NumPy scalar.

Parameters
----------
other : object
    Increment or date operand; NumPy arrays are unsupported.

Returns
-------
Delta | date | datetime | NotImplemented
    A base Delta for increment operands,
        the input date subtype for Python dates, or a naive builtin datetime for
        NumPy datetime64. Unsupported operands return NotImplemented.

Raises
------
OverflowError
    Numeric conversion or calendar arithmetic overflows.
ValueError
    Invalid dates or a failing custom date constructor.
Exception
    Third-party conversion and other Python callback errors propagate.

Notes
-----
Date operations apply absolute fields, relative increments, then weekday;
datetime timezone and fold are preserved. Arrays are not supported.

### __sub__

Subtract Delta, timedelta, relativedelta or NumPy timedelta64 from this Delta.

Parameters
----------
other : object
    Increment to subtract; dates are unsupported here.

Returns
-------
Delta | NotImplemented
    A base Delta or NotImplemented for unsupported types,
        including dates and NumPy datetime64 in this direction.

Raises
------
OverflowError
    Numeric conversion, subtraction or normalization overflows.
Exception
    Third-party conversion and Python callback errors propagate.

### __radd__

Apply reflected addition using the same date and duration rules as __add__.

Parameters
----------
other : object
    Left-hand date, duration or relativedelta operand.

A direct reflected call with another Delta returns NotImplemented. Conversion,
calendar and custom-constructor errors follow __add__.

### __rsub__

Subtract this Delta from a date/datetime, timedelta or supported NumPy scalar.

Parameters
----------
other : object
    Left-hand date, duration or relativedelta operand.

relativedelta is also supported; direct reflected Delta calls return
NotImplemented. Return types and calendar errors follow reflected dispatch,
with OverflowError for unrepresentable negation or subtraction.

### __neg__

Negate relative components and retain absolute replacements in a new Delta.

Raises
------
OverflowError
    A relative component cannot be negated or normalized.

### __abs__

Return a new Delta with the frozen grouped-sign absolute-value behavior.

Year/month and day/time groups use their leading normalized component's sign;
absolute replacement fields are retained.

Raises
------
OverflowError
    Required negation or normalization cannot be represented.

### __eq__

Compare the values of two Delta objects.

Returns
-------
bool or NotImplemented
    Whether all relative and absolute fields match. Other object types
    return NotImplemented and follow Python's reflected comparison rules.

Notes
-----
Delta subclasses that inherit this comparison use the same value rules.
Equal Delta values have equal hashes and can share dictionary keys.

### __ne__

Compare two Delta values for inequality.

Returns
-------
bool or NotImplemented
    The opposite of field equality for Delta objects. Other types return
    NotImplemented without converting the operand.

### __bool__

Return whether a relative field is nonzero or an absolute field is set.

Explicit absolute zero is set and therefore makes a Delta truthy.

### __hash__

Return a stable hash based on the Delta value.

Returns
-------
int
    Equal Delta values have equal hashes.

Notes
-----
Additional subclass attributes do not change the Delta value or its hash.

### __copy__

Return a separate object with the same Delta value and type.

Returns
-------
Delta
    A shallow copy. Additional attribute values remain shared.

### __deepcopy__

Return a distinct deep copy, preserving subtype and tracking cycles.

Parameters
----------
memo : dict
    Python deepcopy's object-identity table, reused for recursion.

Raises
------
Exception
    Allocation, subclass and recursive deepcopy errors propagate.

### __getstate__

Return the saved fields and additional attributes used by this package.

Returns
-------
tuple
    State used by the package's save/restore support.

Notes
-----
Use pickle or copy for ordinary saving and copying.

### __setstate__

Restore saved extra attributes while keeping this Delta value.

Parameters
----------
state : tuple, dict or None
    State returned by this package, or the extra attributes used by pickle.

Returns
-------
None

Raises
------
TypeError
    The state has unsupported containers or value types.
ValueError
    The state is invalid or tries to change the Delta's fields.
OverflowError
    A saved integer is too large.

Notes
-----
The object's value and hash cannot be replaced. Only load pickle data from
trusted sources. Errors from subclass attribute handling are passed through.

## Fields

| Field | Meaning |
| --- | --- |
| `years` | int: Normalized relative years; months are carried into this value. |
| `months` | int: Relative months after grouping years, in 0..11. |
| `days` | int: Relative days, including normalized weeks and clock carries. |
| `hours` | int: Normalized relative hours, in 0..23. |
| `minutes` | int: Normalized relative minutes, in 0..59. |
| `seconds` | int: Normalized relative seconds, in 0..59. |
| `microseconds` | int: Normalized relative microseconds, in 0..999999. |
| `year` | int | None: Absolute year replacement, or None when unset. |
| `month` | int | None: Absolute month replacement (1..12), or None when unset. |
| `day` | int | None: Absolute day replacement (1..31), or None when unset. |
| `weekday` | int | None: Absolute weekday replacement (Monday=0 to Sunday=6), or None. |
| `hour` | int | None: Absolute hour replacement (0..23), or None when unset. |
| `minute` | int | None: Absolute minute replacement (0..59), or None when unset. |
| `second` | int | None: Absolute second replacement (0..59), or None when unset. |
| `microsecond` | int | None: Absolute microsecond replacement (0..999999), or None. |
