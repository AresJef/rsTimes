"""Type hints for rstimes.delta; executable behavior is supplied by Rust."""
from datetime import date, datetime, timedelta
from typing import Iterable, TypeVar, overload, SupportsIndex
import numpy as np
from dateutil.relativedelta import relativedelta
_DateT = TypeVar('_DateT', bound=date)
_DeltaT = TypeVar('_DeltaT', bound='Delta')
_Metadata = dict[str, object] | tuple[dict[str, object] | None, dict[str, object]] | None
_State = tuple[str, int, tuple[int, ...], int, _Metadata]
_FixedAmount = SupportsIndex | float | np.float16 | np.float32 | np.float64

class Delta:
    """An immutable calendar increment with relative amounts and optional field settings.

Parameters
----------
years : int or SupportsIndex, default 0
    Signed calendar years to add. Negative values reverse that direction; zero
    is a real zero increment.
quarters : int or SupportsIndex, default 0
    Signed calendar quarters to add. Negative values reverse that direction;
    zero is a real zero increment.
months : int or SupportsIndex, default 0
    Signed calendar months to add. Negative values reverse that direction; zero
    is a real zero increment.
weeks : int, float or numpy.float16/float32/float64, default 0
    Signed weeks to add. Negative values reverse that direction; zero is a real
    zero increment. Fixed-duration floats are combined and rounded once to
    microseconds.
days : int, float or numpy.float16/float32/float64, default 0
    Signed days to add. Negative values reverse that direction; zero is a real
    zero increment. Fixed-duration floats are combined and rounded once to
    microseconds.
hours : int, float or numpy.float16/float32/float64, default 0
    Signed hours to add. Negative values reverse that direction; zero is a real
    zero increment. Fixed-duration floats are combined and rounded once to
    microseconds.
minutes : int, float or numpy.float16/float32/float64, default 0
    Signed minutes to add. Negative values reverse that direction; zero is a
    real zero increment. Fixed-duration floats are combined and rounded once to
    microseconds.
seconds : int, float or numpy.float16/float32/float64, default 0
    Signed seconds to add. Negative values reverse that direction; zero is a
    real zero increment. Fixed-duration floats are combined and rounded once to
    microseconds.
milliseconds : int, float or numpy.float16/float32/float64, default 0
    Signed milliseconds to add. Negative values reverse that direction; zero is
    a real zero increment. Fixed-duration floats are combined and rounded once
    to microseconds.
microseconds : int, float or numpy.float16/float32/float64, default 0
    Signed microseconds to add. Negative values reverse that direction; zero is
    a real zero increment. Fixed-duration floats are combined and rounded once
    to microseconds.
year : int | None, default None
    Absolute year replacement. None leaves it unset; explicit integers must be
    positive. Values above 9999 are limited to that maximum.
month : int | None, default None
    Absolute month replacement. None leaves it unset; explicit integers must be
    positive. Values above 12 are limited to that maximum.
day : int | None, default None
    Absolute day replacement. None leaves it unset; explicit integers must be
    positive. Values above 31 are limited to that maximum.
weekday : int | None, default None
    Absolute weekday replacement in 0 (Monday) through 6 (Sunday). None leaves
    it unset; zero is an actual setting. Floats and out-of-range numbers are
    rejected.
hour : int | None, default None
    Absolute hour replacement in 0 through 23. None leaves it unset; zero is an
    actual setting. Floats and out-of-range numbers are rejected.
minute : int | None, default None
    Absolute minute replacement in 0 through 59. None leaves it unset; zero is
    an actual setting. Floats and out-of-range numbers are rejected.
second : int | None, default None
    Absolute second replacement in 0 through 59. None leaves it unset; zero is
    an actual setting. Floats and out-of-range numbers are rejected.
millisecond : int | None, default None
    Absolute millisecond replacement in 0 through 999. None leaves it unset;
    zero is an actual setting. Floats and out-of-range numbers are rejected.
microsecond : int | None, default None
    Absolute microsecond replacement in 0 through 999999. None leaves it unset;
    zero is an actual setting. Floats and out-of-range numbers are rejected. If
    millisecond is also set, only the final three microsecond digits are used.

Returns
-------
Delta
    A completed instance of this class.

Notes
-----
Relative amounts add or subtract time; singular fields replace date or clock fields. None leaves an absolute field unset, while an explicit clock zero sets that field to zero. Positive year/month/day selections keep their upper limiting and month-end behavior. Other absolute fields require their stated ranges. Integer-like values such as NumPy integers are accepted for absolute fields; floats are rejected.

Fixed-duration fractions are combined and rounded once to microseconds, with halfway cases rounded to an even microsecond. Relative years, quarters and months require the integer index protocol; floats are rejected. Public numeric fields reject boolean values. Fixed-duration inputs accept the listed real floating types and integer index values, not arbitrary numeric conversions. Calendar month moves need not be reversible: January 31 plus one month and then minus one month may finish on January 29.

Values compare and hash by their fields with other Delta values. Fields cannot be changed in place; calling __init__ again leaves the existing value unchanged.

Examples
--------
>>> Delta(hour=None).hour is None
True
>>> Delta(hour=0).hour
0
>>> from datetime import date
>>> date(2024, 1, 31) + Delta(months=1)
datetime.date(2024, 2, 29)"""

    def __new__(cls: type[_DeltaT], years: SupportsIndex=0, quarters: SupportsIndex=0, months: SupportsIndex=0, weeks: _FixedAmount=0, days: _FixedAmount=0, hours: _FixedAmount=0, minutes: _FixedAmount=0, seconds: _FixedAmount=0, milliseconds: _FixedAmount=0, microseconds: _FixedAmount=0, year: SupportsIndex | None=None, month: SupportsIndex | None=None, day: SupportsIndex | None=None, weekday: SupportsIndex | None=None, hour: SupportsIndex | None=None, minute: SupportsIndex | None=None, second: SupportsIndex | None=None, millisecond: SupportsIndex | None=None, microsecond: SupportsIndex | None=None) -> _DeltaT:
        """Create a Delta value; see Delta for complete parameter descriptions.

Parameters
----------
years : int or SupportsIndex, default 0
    Signed calendar years to add. Negative values reverse that direction; zero
    is a real zero increment.
quarters : int or SupportsIndex, default 0
    Signed calendar quarters to add. Negative values reverse that direction;
    zero is a real zero increment.
months : int or SupportsIndex, default 0
    Signed calendar months to add. Negative values reverse that direction; zero
    is a real zero increment.
weeks : int, float or numpy.float16/float32/float64, default 0
    Signed weeks to add. Negative values reverse that direction; zero is a real
    zero increment. Fixed-duration floats are combined and rounded once to
    microseconds.
days : int, float or numpy.float16/float32/float64, default 0
    Signed days to add. Negative values reverse that direction; zero is a real
    zero increment. Fixed-duration floats are combined and rounded once to
    microseconds.
hours : int, float or numpy.float16/float32/float64, default 0
    Signed hours to add. Negative values reverse that direction; zero is a real
    zero increment. Fixed-duration floats are combined and rounded once to
    microseconds.
minutes : int, float or numpy.float16/float32/float64, default 0
    Signed minutes to add. Negative values reverse that direction; zero is a
    real zero increment. Fixed-duration floats are combined and rounded once to
    microseconds.
seconds : int, float or numpy.float16/float32/float64, default 0
    Signed seconds to add. Negative values reverse that direction; zero is a
    real zero increment. Fixed-duration floats are combined and rounded once to
    microseconds.
milliseconds : int, float or numpy.float16/float32/float64, default 0
    Signed milliseconds to add. Negative values reverse that direction; zero is
    a real zero increment. Fixed-duration floats are combined and rounded once
    to microseconds.
microseconds : int, float or numpy.float16/float32/float64, default 0
    Signed microseconds to add. Negative values reverse that direction; zero is
    a real zero increment. Fixed-duration floats are combined and rounded once
    to microseconds.
year : int | None, default None
    Absolute year replacement. None leaves it unset; explicit integers must be
    positive. Values above 9999 are limited to that maximum.
month : int | None, default None
    Absolute month replacement. None leaves it unset; explicit integers must be
    positive. Values above 12 are limited to that maximum.
day : int | None, default None
    Absolute day replacement. None leaves it unset; explicit integers must be
    positive. Values above 31 are limited to that maximum.
weekday : int | None, default None
    Absolute weekday replacement in 0 (Monday) through 6 (Sunday). None leaves
    it unset; zero is an actual setting. Floats and out-of-range numbers are
    rejected.
hour : int | None, default None
    Absolute hour replacement in 0 through 23. None leaves it unset; zero is an
    actual setting. Floats and out-of-range numbers are rejected.
minute : int | None, default None
    Absolute minute replacement in 0 through 59. None leaves it unset; zero is
    an actual setting. Floats and out-of-range numbers are rejected.
second : int | None, default None
    Absolute second replacement in 0 through 59. None leaves it unset; zero is
    an actual setting. Floats and out-of-range numbers are rejected.
millisecond : int | None, default None
    Absolute millisecond replacement in 0 through 999. None leaves it unset;
    zero is an actual setting. Floats and out-of-range numbers are rejected.
microsecond : int | None, default None
    Absolute microsecond replacement in 0 through 999999. None leaves it unset;
    zero is an actual setting. Floats and out-of-range numbers are rejected. If
    millisecond is also set, only the final three microsecond digits are used.

Returns
-------
Delta subclass
    A new instance of the requested class.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def __init__(self, years: SupportsIndex=0, quarters: SupportsIndex=0, months: SupportsIndex=0, weeks: _FixedAmount=0, days: _FixedAmount=0, hours: _FixedAmount=0, minutes: _FixedAmount=0, seconds: _FixedAmount=0, milliseconds: _FixedAmount=0, microseconds: _FixedAmount=0, year: SupportsIndex | None=None, month: SupportsIndex | None=None, day: SupportsIndex | None=None, weekday: SupportsIndex | None=None, hour: SupportsIndex | None=None, minute: SupportsIndex | None=None, second: SupportsIndex | None=None, millisecond: SupportsIndex | None=None, microsecond: SupportsIndex | None=None) -> None:
        """Accept construction arguments without changing an already initialized value.

Parameters
----------
years : int or SupportsIndex, default 0
    Signed calendar years to add. Negative values reverse that direction; zero
    is a real zero increment.
quarters : int or SupportsIndex, default 0
    Signed calendar quarters to add. Negative values reverse that direction;
    zero is a real zero increment.
months : int or SupportsIndex, default 0
    Signed calendar months to add. Negative values reverse that direction; zero
    is a real zero increment.
weeks : int, float or numpy.float16/float32/float64, default 0
    Signed weeks to add. Negative values reverse that direction; zero is a real
    zero increment. Fixed-duration floats are combined and rounded once to
    microseconds.
days : int, float or numpy.float16/float32/float64, default 0
    Signed days to add. Negative values reverse that direction; zero is a real
    zero increment. Fixed-duration floats are combined and rounded once to
    microseconds.
hours : int, float or numpy.float16/float32/float64, default 0
    Signed hours to add. Negative values reverse that direction; zero is a real
    zero increment. Fixed-duration floats are combined and rounded once to
    microseconds.
minutes : int, float or numpy.float16/float32/float64, default 0
    Signed minutes to add. Negative values reverse that direction; zero is a
    real zero increment. Fixed-duration floats are combined and rounded once to
    microseconds.
seconds : int, float or numpy.float16/float32/float64, default 0
    Signed seconds to add. Negative values reverse that direction; zero is a
    real zero increment. Fixed-duration floats are combined and rounded once to
    microseconds.
milliseconds : int, float or numpy.float16/float32/float64, default 0
    Signed milliseconds to add. Negative values reverse that direction; zero is
    a real zero increment. Fixed-duration floats are combined and rounded once
    to microseconds.
microseconds : int, float or numpy.float16/float32/float64, default 0
    Signed microseconds to add. Negative values reverse that direction; zero is
    a real zero increment. Fixed-duration floats are combined and rounded once
    to microseconds.
year : int | None, default None
    Absolute year replacement. None leaves it unset; explicit integers must be
    positive. Values above 9999 are limited to that maximum.
month : int | None, default None
    Absolute month replacement. None leaves it unset; explicit integers must be
    positive. Values above 12 are limited to that maximum.
day : int | None, default None
    Absolute day replacement. None leaves it unset; explicit integers must be
    positive. Values above 31 are limited to that maximum.
weekday : int | None, default None
    Absolute weekday replacement in 0 (Monday) through 6 (Sunday). None leaves
    it unset; zero is an actual setting. Floats and out-of-range numbers are
    rejected.
hour : int | None, default None
    Absolute hour replacement in 0 through 23. None leaves it unset; zero is an
    actual setting. Floats and out-of-range numbers are rejected.
minute : int | None, default None
    Absolute minute replacement in 0 through 59. None leaves it unset; zero is
    an actual setting. Floats and out-of-range numbers are rejected.
second : int | None, default None
    Absolute second replacement in 0 through 59. None leaves it unset; zero is
    an actual setting. Floats and out-of-range numbers are rejected.
millisecond : int | None, default None
    Absolute millisecond replacement in 0 through 999. None leaves it unset;
    zero is an actual setting. Floats and out-of-range numbers are rejected.
microsecond : int | None, default None
    Absolute microsecond replacement in 0 through 999999. None leaves it unset;
    zero is an actual setting. Floats and out-of-range numbers are rejected. If
    millisecond is also set, only the final three microsecond digits are used.

Returns
-------
None
    No return value. Calling __init__ again does not change this Delta.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    @classmethod
    def from_relativedelta(cls, rd: relativedelta) -> Delta:
        """Create a Delta from supported relativedelta fields.

Source date zero means no absolute replacement; clock zero remains an explicit setting. Relative years/months are interpreted before limiting the destination day. Unsupported or unrepresentable rules raise ValueError instead of silently changing their meaning.

Reads the source fields directly, including real subclass attributes, without calling normalized(). Fractional fixed durations use the same microsecond rounding as Delta construction. The returned Delta follows Delta's date, fold and arithmetic rules; conversion does not promise that every operation can replace the source object unchanged.

Parameters
----------
rd : relativedelta
    A dateutil.relativedelta whose supported date meaning can be represented
    exactly. A nonempty weekday or nonzero leapdays is not supported.

Returns
-------
Delta
    A Delta from supported relativedelta fields.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range.

Examples
--------
>>> from dateutil.relativedelta import relativedelta
>>> Delta.from_relativedelta(relativedelta(months=1)).months
1"""
        ...

    def to_timedelta(self, start: date | datetime | None=None) -> timedelta:
        """Convert this Delta to a standard-library time span.

Parameters
----------
start : date | datetime | None, default None
    Date/datetime anchor for calendar years, months or absolute settings. With
    an anchor the result is (start + this Delta) - start, returned as standard
    timedelta after the final microsecond rounding. Ordinary datetime anchors
    use Python subtraction rules, including wall-clock subtraction with the same
    timezone object. Standard pandas Timestamp anchors use the elapsed instant
    difference, retain nanoseconds until the final rounding and support spans
    beyond pandas Timedelta storage when standard timedelta can hold them.
    Custom arithmetic methods still control their own results.

Returns
-------
timedelta
    A standard-library timedelta representing the stated difference or fixed
    span. Genuine pandas spans retain their precision until one final rounding
    to the nearest microsecond, with ties to even. A result outside the standard
    timedelta range raises OverflowError.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range.

Examples
--------
>>> Delta(hours=25).to_timedelta()
datetime.timedelta(days=1, seconds=3600)
>>> Delta(months=1).to_timedelta(date(2024, 1, 31))
datetime.timedelta(days=29)"""
        ...

    def apply_many(self, values: Iterable[object]) -> list[object]:
        """Add this Delta to each value and return the results in order.

NumPy inputs keep the return types and exceptions of ordinary value + Delta.

Parameters
----------
values : Iterable[object]
    An iterable of operands supporting value + this Delta. Order is retained;
    errors stop the call without returning a partial result.

Returns
-------
list[object]
    One result per supplied operand, in input order; each result follows
    ordinary value + Delta semantics.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range.

Examples
--------
>>> Delta(days=1).apply_many([date(2024, 1, 1), date(2024, 1, 2)])
[datetime.date(2024, 1, 2), datetime.date(2024, 1, 3)]"""
        ...

    @property
    def years(self) -> int:
        """int: Normalized relative years; months are carried into this value.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def months(self) -> int:
        """int: Relative months after grouping years, in 0..11.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def days(self) -> int:
        """int: Relative days, including normalized weeks and clock carries.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def hours(self) -> int:
        """int: Normalized relative hours, in 0..23.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def minutes(self) -> int:
        """int: Normalized relative minutes, in 0..59.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def seconds(self) -> int:
        """int: Normalized relative seconds, in 0..59.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def microseconds(self) -> int:
        """int: Normalized relative microseconds, in 0..999999.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def year(self) -> int | None:
        """int | None: Absolute year replacement, or None when unset.

Returns
-------
int | None
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def month(self) -> int | None:
        """int | None: Absolute month replacement (1..12), or None when unset.

Returns
-------
int | None
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def day(self) -> int | None:
        """int | None: Absolute day replacement (1..31), or None when unset.

Returns
-------
int | None
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def weekday(self) -> int | None:
        """int | None: Absolute weekday replacement (Monday=0 to Sunday=6), or None.

Returns
-------
int | None
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def hour(self) -> int | None:
        """int | None: Absolute hour replacement (0..23), or None when unset.

Returns
-------
int | None
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def minute(self) -> int | None:
        """int | None: Absolute minute replacement (0..59), or None when unset.

Returns
-------
int | None
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def second(self) -> int | None:
        """int | None: Absolute second replacement (0..59), or None when unset.

Returns
-------
int | None
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def microsecond(self) -> int | None:
        """int | None: Absolute microsecond replacement (0..999999), or None.

Returns
-------
int | None
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @overload
    def __add__(self, o: _DateT, /) -> _DateT:
        """Add a Delta, timedelta, relativedelta, date/datetime or NumPy scalar.

Parameters
----------
o : date subclass
    The right-hand operand for this operation. Its accepted types and the result
    type are given by this overload.

Returns
-------
date subclass
    Add a Delta, timedelta, relativedelta, date/datetime or NumPy scalar.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    @overload
    def __add__(self, o: timedelta | Delta | relativedelta | np.timedelta64, /) -> Delta:
        """Add a Delta, timedelta, relativedelta, date/datetime or NumPy scalar.

Parameters
----------
o : timedelta | Delta | relativedelta | np.timedelta64
    The right-hand operand for this operation. Its accepted types and the result
    type are given by this overload.

Returns
-------
Delta
    Add a Delta, timedelta, relativedelta, date/datetime or NumPy scalar.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    @overload
    def __add__(self, o: np.datetime64, /) -> datetime:
        """Add a Delta, timedelta, relativedelta, date/datetime or NumPy scalar.

Parameters
----------
o : np.datetime64
    The right-hand operand for this operation. Its accepted types and the result
    type are given by this overload.

Returns
-------
datetime
    Add a Delta, timedelta, relativedelta, date/datetime or NumPy scalar.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    @overload
    def __radd__(self, o: _DateT, /) -> _DateT:
        """Apply reflected addition using the same date and duration rules as __add__.

NumPy may convert a scalar on the left before reflected dispatch. Thus an
expression such as value + delta may pass a different type than a direct
delta.__radd__(value) call.

Parameters
----------
o : date subclass
    The right-hand operand for this operation. Its accepted types and the result
    type are given by this overload.

Returns
-------
date subclass
    Apply reflected addition using the same date and duration rules as __add__.

NumPy may convert a scalar on the left before reflected dispatch. Thus an
expression such as value + delta may pass a different type than a direct
delta.__radd__(value) call.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    @overload
    def __radd__(self, o: timedelta | relativedelta | np.timedelta64, /) -> Delta:
        """Apply reflected addition using the same date and duration rules as __add__.

NumPy may convert a scalar on the left before reflected dispatch. Thus an
expression such as value + delta may pass a different type than a direct
delta.__radd__(value) call.

Parameters
----------
o : timedelta | relativedelta | np.timedelta64
    The right-hand operand for this operation. Its accepted types and the result
    type are given by this overload.

Returns
-------
Delta
    Apply reflected addition using the same date and duration rules as __add__.

NumPy may convert a scalar on the left before reflected dispatch. Thus an
expression such as value + delta may pass a different type than a direct
delta.__radd__(value) call.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    @overload
    def __radd__(self, o: np.datetime64, /) -> datetime:
        """Apply reflected addition using the same date and duration rules as __add__.

NumPy may convert a scalar on the left before reflected dispatch. Thus an
expression such as value + delta may pass a different type than a direct
delta.__radd__(value) call.

Parameters
----------
o : np.datetime64
    The right-hand operand for this operation. Its accepted types and the result
    type are given by this overload.

Returns
-------
datetime
    Apply reflected addition using the same date and duration rules as __add__.

NumPy may convert a scalar on the left before reflected dispatch. Thus an
expression such as value + delta may pass a different type than a direct
delta.__radd__(value) call.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def __sub__(self, o: timedelta | Delta | relativedelta | np.timedelta64, /) -> Delta:
        """Subtract Delta, timedelta, relativedelta or NumPy timedelta64 from this Delta.

Parameters
----------
o : timedelta | Delta | relativedelta | np.timedelta64
    The right-hand operand for this operation. Its accepted types and the result
    type are given by this overload.

Returns
-------
Delta
    Subtract Delta, timedelta, relativedelta or NumPy timedelta64 from this Delta.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    @overload
    def __rsub__(self, o: _DateT, /) -> _DateT:
        """Subtract this Delta from a date/datetime, timedelta or supported NumPy scalar.

Parameters
----------
o : date subclass
    The right-hand operand for this operation. Its accepted types and the result
    type are given by this overload.

Returns
-------
date subclass
    Subtract this Delta from a date/datetime, timedelta or supported NumPy scalar.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    @overload
    def __rsub__(self, o: timedelta | relativedelta | np.timedelta64, /) -> Delta:
        """Subtract this Delta from a date/datetime, timedelta or supported NumPy scalar.

Parameters
----------
o : timedelta | relativedelta | np.timedelta64
    The right-hand operand for this operation. Its accepted types and the result
    type are given by this overload.

Returns
-------
Delta
    Subtract this Delta from a date/datetime, timedelta or supported NumPy scalar.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    @overload
    def __rsub__(self, o: np.datetime64, /) -> datetime:
        """Subtract this Delta from a date/datetime, timedelta or supported NumPy scalar.

Parameters
----------
o : np.datetime64
    The right-hand operand for this operation. Its accepted types and the result
    type are given by this overload.

Returns
-------
datetime
    Subtract this Delta from a date/datetime, timedelta or supported NumPy scalar.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def __neg__(self) -> Delta:
        """Negate relative components and retain absolute replacements in a new Delta.

Returns
-------
Delta
    Negate relative components and retain absolute replacements in a new Delta."""
        ...

    def __abs__(self) -> Delta:
        """Return a new Delta with the grouped-sign absolute-value behavior.

Returns
-------
Delta
    A new Delta with the grouped-sign absolute-value behavior."""
        ...

    def __eq__(self, o: object, /) -> bool:
        """Compare the values of two Delta objects.

Parameters
----------
o : object
    The right-hand operand for this operation. Its accepted types and the result
    type are given by this overload.

Returns
-------
bool
    Whether the stated condition holds. A legitimate nonmatch returns False;
    invalid inputs raise the documented error.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def __ne__(self, o: object, /) -> bool:
        """Compare two Delta values for inequality.

A subclass that defines __eq__ and inherits this method uses the opposite of
its equality result. Its own __ne__, when defined, takes precedence. A direct
call preserves NotImplemented and exceptions from the equality method.

Parameters
----------
o : object
    The right-hand operand for this operation. Its accepted types and the result
    type are given by this overload.

Returns
-------
bool
    Whether the stated condition holds. A legitimate nonmatch returns False;
    invalid inputs raise the documented error.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def __bool__(self) -> bool:
        """Return whether a relative field is nonzero or an absolute field is set.

Returns
-------
bool
    Whether the stated condition holds. A legitimate nonmatch returns False;
    invalid inputs raise the documented error."""
        ...

    def __repr__(self) -> str:
        """Return the runtime class name and set fields in the display order.

Returns
-------
str
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def __hash__(self) -> int:
        """Return a stable hash based on the Delta value.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def __getstate__(self) -> _State:
        """Return the saved fields and additional attributes used by this package.

Returns
-------
_State
    The saved fields and additional attributes used by this package."""
        ...

    def __setstate__(self, state: object) -> None:
        """Restore saved extra attributes while keeping this Delta value.

Parameters
----------
state : object
    A supported versioned state produced by this package. Invalid field values
    or malformed state are rejected; restoring metadata does not mutate an
    existing date/delta value. Slot entries are retained before setters run;
    later changes to the supplied mapping do not extend this restoration.

Returns
-------
None
    No return value.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def __reduce__(self) -> tuple[object, ...]:
        """Return the reconstruction recipe used by pickle.

Returns
-------
tuple[object, ...]
    Reconstruction data consumed by pickle; use pickle rather than editing this
    state."""
        ...

    def __reduce_ex__(self, protocol: SupportsIndex, /) -> tuple[object, ...]:
        """Return the recipe used by pickle to save this Delta.

Parameters
----------
protocol : int
    Pickle protocol requested by the caller. Reconstruction uses this package's
    validated state format.

Returns
-------
tuple[object, ...]
    Reconstruction data consumed by pickle; use pickle rather than editing this
    state."""
        ...

    def __copy__(self: _DeltaT) -> _DeltaT:
        """Return a separate object with the same Delta value and type.

Returns
-------
Delta subclass
    A separate Delta object of the same subclass, retaining the saved metadata."""
        ...

    def __deepcopy__(self: _DeltaT, memo: dict[int, object]) -> _DeltaT:
        """Return a distinct deep copy, preserving subtype and tracking cycles.

Slot values are retained before setters run. A setter may change its own
metadata or raise an exception without invalidating the remaining slot entries.

Parameters
----------
memo : dict[int, object]
    The deepcopy memo mapping used to preserve shared references and handle
    cycles.

Returns
-------
Delta subclass
    A separate Delta object of the same subclass, retaining the saved metadata."""
        ...
