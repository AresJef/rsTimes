"""Type hints for Pydt's calendar conveniences and standard datetime inheritance."""
from dateutil.relativedelta import relativedelta
from typing import Literal, SupportsIndex, SupportsInt, SupportsFloat
from typing_extensions import Self, TypeVar, overload, TypedDict, Unpack
import datetime
import time
import numpy as np
from zoneinfo import ZoneInfo
from .parser import Configs
from .delta import Delta
_DateT = TypeVar('_DateT', bound=datetime.date)
_DatetimeT = TypeVar('_DatetimeT', bound=datetime.datetime)
_TimedeltaT = TypeVar('_TimedeltaT', bound=datetime.timedelta)
DatetimeLike = str | datetime.date | datetime.datetime | int | float | np.datetime64

class _ReplaceFields(TypedDict, total=False):
    """Keyword fields accepted by Pydt.__replace__.

Parameters
----------
year, month, day, hour, minute, second, microsecond, fold : int or None, optional
    New numeric fields. Omitted values and None preserve the stored field.
tzinfo : tzinfo, str or None, optional
    Omitted preserves the timezone; None removes it; a name selects ZoneInfo.

Returns
-------
_ReplaceFields
    A keyword dictionary; pass its fields to Pydt.__replace__()."""
    year: SupportsIndex | None
    month: SupportsIndex | None
    day: SupportsIndex | None
    hour: SupportsIndex | None
    minute: SupportsIndex | None
    second: SupportsIndex | None
    microsecond: SupportsIndex | None
    tzinfo: datetime.tzinfo | str | None
    fold: SupportsIndex | np.bool_ | None

class Pydt(datetime.datetime):
    """A datetime subclass with consistent calendar and timezone conveniences.

Parameters
----------
year : int, default 1
    Year field in 1 through 9999.
month : int, default 1
    Month field in 1 through 12.
day : int, default 1
    Day field in 1 through 31.
hour : int, default 0
    Hour field in 0 through 23.
minute : int, default 0
    Minute field in 0 through 59.
second : int, default 0
    Second field in 0 through 59.
microsecond : int, default 0
    Microsecond field in 0 through 999999.
tzinfo : datetime.tzinfo | str | None, default None
    Timezone name or tzinfo. None leaves a naive result unless this factory
    explicitly uses the local timezone. Named regions use ZoneInfo; missing
    local times are rejected when creating Pydt.
fold : int, default 0
    Integer 0/1 or a Python/NumPy boolean selects the earlier/later repeated time.
    Numeric None retains it in replace; missing local times are rejected for
    either fold.

Returns
-------
Pydt
    A completed instance of this class.

Notes
-----
Numeric date fields and calendar counts accept integer-index objects, not floats or booleans. Seconds factories retain their documented numeric protocols and reject boolean/text inputs. Ordinary boolean options accept only bool or numpy.bool_; fold additionally accepts the documented integer 0 or 1.

Explicit construction and replace() require a valid date and an existing regional local time. fold selects the earlier or later occurrence of a repeated time only; it cannot make a missing time valid. ZoneInfo subclasses follow the same regional checks.

Calendar conveniences prefer the original UTC offset when selecting a repeated local result and choose an existing result when a clock adjustment crosses a gap. Period starts and ends stay within the requested period; round/ceil/floor retain their rounding meanings. Naive values, UTC and standard fixed offsets need no regional-time checks.

Comparisons, hashing and subtraction between ordinary datetimes retain Python semantics.
A pandas Timestamp is compared using its real date and nanosecond precision.
Its date difference returns a standard timedelta, rounded once to the nearest
microsecond with ties to even. Both operands sharing the same tzinfo object
follow Python's wall-clock subtraction rule, ignoring fold. Values are immutable, and ordinary subclasses may keep their own extra attributes.

Examples
--------
>>> Pydt(2024, 1, 31).to_month(1).isoformat()
'2024-02-29T00:00:00'
>>> Pydt(2024, 5, 7, 12, tzinfo="Asia/Shanghai").tz_convert("UTC").hour
4"""

    def __new__(cls, year: SupportsIndex=1, month: SupportsIndex=1, day: SupportsIndex=1, hour: SupportsIndex=0, minute: SupportsIndex=0, second: SupportsIndex=0, microsecond: SupportsIndex=0, tzinfo: datetime.tzinfo | str | None=None, *, fold: SupportsIndex | np.bool_=0) -> Self:
        """Construct a complete value of this class.

Parameters
----------
year : int, default 1
    Year field in 1 through 9999.
month : int, default 1
    Month field in 1 through 12.
day : int, default 1
    Day field in 1 through 31.
hour : int, default 0
    Hour field in 0 through 23.
minute : int, default 0
    Minute field in 0 through 59.
second : int, default 0
    Second field in 0 through 59.
microsecond : int, default 0
    Microsecond field in 0 through 999999.
tzinfo : datetime.tzinfo | str | None, default None
    Timezone name or tzinfo. None leaves a naive result unless this factory
    explicitly uses the local timezone. Named regions use ZoneInfo; missing
    local times are rejected when creating Pydt.
fold : int, default 0
    Integer 0/1 or a Python/NumPy boolean selects the earlier/later repeated time.
    Numeric None retains it in replace; missing local times are rejected for
    either fold.

Returns
-------
Pydt
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

    @classmethod
    def parse(cls, dtobj: DatetimeLike, default: DatetimeLike | None=None, yearfirst: bool | np.bool_ | None=None, dayfirst: bool | np.bool_ | None=None, ignoretz: bool | np.bool_=True, isoformat: bool | np.bool_=True, strict: bool | np.bool_=False, cfg: Configs | None=None) -> Self:
        """Parse text or a supported date object into this class.

Parameters
----------
dtobj : DatetimeLike
    One supported date/time input: text, a Python date/datetime, numeric epoch
    seconds, or a NumPy datetime64 scalar. NaT and unsupported containers are
    rejected.
default : str | date | datetime | int | float | numpy.datetime64 | None, default None
    An independently complete date used to fill missing year, month and day
    only. Date/datetime subclasses, complete date text, numeric epoch seconds
    and NumPy datetime64 are supported. A datetime also supplies its stored
    fold; its clock and timezone are not defaults.
yearfirst : bool | None, default None
    Prefer a year in the first position of an ambiguous numeric date. None uses
    Configs when this parser option is optional.
dayfirst : bool | None, default None
    Prefer a day before a month in an ambiguous numeric date. None uses Configs
    when this parser option is optional.
ignoretz : bool, default True
    For text, True discards recognized timezone information without changing the
    clock. False retains the timezone. Existing datetime objects retain their
    own timezone.
isoformat : bool, default True
    Try ISO date/time forms before the general grammar. This does not restrict
    input to ISO text.
strict : bool, default False
    True rejects explicit invalid fields, conflicting repeated fields and a
    weekday inconsistent with a full written date. False clips invalid fields
    without carrying and allows later conflicting fields to win. A two-digit
    year requires False and a complete default date.
cfg : Configs | None, default None
    Optional Configs vocabulary and ordering rules for text. None uses the
    library defaults.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.

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
    def now(cls, tz: datetime.tzinfo | str | None=None) -> Self:
        """Return the current time in a named or supplied timezone.

Parameters
----------
tz : datetime.tzinfo | str | None, default None
    Timezone name or tzinfo for the current instant. None returns local clock
    fields without a timezone. Named regions use ZoneInfo.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.

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
    def utcnow(cls) -> Self:
        """Return the current time with the standard UTC timezone attached.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes."""
        ...

    @classmethod
    def today(cls) -> Self:
        """Return the current local date and time without a timezone.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes."""
        ...

    @classmethod
    def combine(cls, date: DatetimeLike | None=None, time: DatetimeLike | datetime.time | None=None, tz: datetime.tzinfo | str | None=None) -> Self:
        """Combine date and time fields; omitted fields use today and midnight.

Parameters
----------
date : DatetimeLike | None, default None
    A date/datetime, date text, numeric epoch seconds or NumPy datetime64. Only
    its date fields are used. None uses today; NaT is rejected.
time : DatetimeLike | datetime.time | None, default None
    A time, datetime or other scalar accepted by parse. Only clock fields,
    timezone and fold are used. None supplies midnight. Text is parsed with a
    fixed date for missing date fields; NaT is rejected. An explicit tz replaces
    the input timezone without converting the clock.
tz : datetime.tzinfo | str | None, default None
    Timezone name or tzinfo to attach without moving clock fields. None keeps
    the input time's timezone, or leaves the result naive when it has none.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.

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
>>> Pydt.combine(datetime.date(2024, 5, 7), datetime.datetime(2000, 1, 1, 9, 30)).isoformat()
'2024-05-07T09:30:00'"""
        ...

    @classmethod
    def fromordinal(cls, ordinal: SupportsIndex, tz: datetime.tzinfo | str | None=None) -> Self:
        """Build midnight from a Gregorian ordinal; ordinal 1 is 0001-01-01.

Parameters
----------
ordinal : number
    Integer Gregorian day number, with 1 meaning 0001-01-01. Uses the integer
    index protocol; floats, booleans, text and byte strings are rejected.
tz : datetime.tzinfo | str | None, default None
    Timezone name or tzinfo to attach without converting the clock fields.
    None produces a naive value. Named regions use ZoneInfo; nonexistent
    regional local times raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.

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
    def fromseconds(cls, seconds: SupportsFloat | SupportsIndex, tz: datetime.tzinfo | str | None=None) -> Self:
        """Build from epoch seconds, attaching tz without a clock conversion.

Parameters
----------
seconds : number
    Numeric seconds since the naive epoch 1970-01-01. Custom float-convertible
    and integer-index objects are accepted. Boolean values, str, bytes and
    bytearray are rejected.
    Floating inputs follow parse: round to seven decimal places, then discard
    the seventh digit for microseconds. tz attaches without a clock conversion.
tz : datetime.tzinfo | str | None, default None
    Timezone name or tzinfo to attach without converting the clock fields.
    None produces a naive value. Named regions use ZoneInfo; nonexistent
    regional local times raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.

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
>>> Pydt.fromseconds(0, "Asia/Shanghai").isoformat()
'1970-01-01T00:00:00+08:00'
>>> Pydt.fromseconds(-0.000001).tomicroseconds()
-1
"""
        ...

    @classmethod
    def frommicroseconds(cls, us: SupportsIndex, tz: datetime.tzinfo | str | None=None) -> Self:
        """Build from exact integer epoch microseconds, attaching an optional tz.

Parameters
----------
us : number
    Integer epoch microseconds, read with the index protocol. Floats, booleans,
    text and byte strings are rejected.
tz : datetime.tzinfo | str | None, default None
    Timezone name or tzinfo to attach without converting the clock fields.
    None produces a naive value. Named regions use ZoneInfo; nonexistent
    regional local times raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.

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
>>> Pydt.frommicroseconds(-1).isoformat()
'1969-12-31T23:59:59.999999'
>>> Pydt.frommicroseconds(1).tomicroseconds()
1
"""
        ...

    @classmethod
    def fromtimestamp(cls, ts: int | float, tz: datetime.tzinfo | str | None=None) -> Self:
        """Build from a POSIX timestamp, converting to tz or naive local time.

Parameters
----------
ts : int | float
    POSIX seconds since 1970-01-01T00:00:00Z. Numeric values are accepted;
    strings and byte strings are rejected.
tz : datetime.tzinfo | str | None, default None
    Timezone name or tzinfo for converting the Unix instant. None returns the
    system-local clock fields without a timezone.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.

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
    def utcfromtimestamp(cls, ts: int | float) -> Self:
        """Build an aware UTC value from numeric POSIX seconds.

Parameters
----------
ts : int | float
    POSIX seconds since 1970-01-01T00:00:00Z. Numeric values are accepted;
    strings and byte strings are rejected.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.

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
    def fromisoformat(cls, dtstr: str) -> Self:
        """Build from text accepted by datetime.fromisoformat.

Parameters
----------
dtstr : str
    Date/time text to parse. This argument must be a string.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.

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
    def fromisocalendar(cls, year: SupportsIndex, week: SupportsIndex, weekday: SupportsIndex, tz: datetime.tzinfo | str | None=None) -> Self:
        """Build an ISO date, limiting high weeks/days to the year's final week/day.

Parameters
----------
year : int
    Year field in 1 through 9999.
week : int
    One-based ISO week number. Values below 1 raise an error; high values select
    the ISO year's actual final week, 52 or 53.
weekday : int
    ISO weekday, Monday=1 through Sunday=7. Values below 1 raise an error;
    larger values select Sunday.
tz : datetime.tzinfo | str | None, default None
    Timezone name or tzinfo to attach without converting the clock fields.
    None produces a naive value. Named regions use ZoneInfo; nonexistent
    regional local times raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.

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
    def fromdayofyear(cls, year: SupportsIndex, doy: SupportsIndex, tz: datetime.tzinfo | str | None=None) -> Self:
        """Build from a year and positive day number, limiting high values to year end.

Parameters
----------
year : number
    Integer year in 1 through 9999, read with the index protocol. Floats, booleans,
    text and byte strings are rejected.
doy : number
    One-based integer day of the year, read with the index protocol. Values below 1 raise an error; high values select the year's final
    day. Text and byte strings are rejected.
tz : datetime.tzinfo | str | None, default None
    Timezone name or tzinfo to attach without converting the clock fields.
    None produces a naive value. Named regions use ZoneInfo; nonexistent
    regional local times raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.

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
    def fromdate(cls, date: datetime.date, tz: datetime.tzinfo | str | None=None) -> Self:
        """Copy date fields at midnight and attach an optional timezone.

Parameters
----------
date : datetime.date
    A Python date or datetime, including subclasses. Copy its calendar date at
    midnight; the source clock, timezone and fold are not copied. A genuine pandas
    Timestamp supplies its actual date. NaT raises ValueError and a date
    outside Pydt's years 1 through 9999 raises OverflowError.
tz : datetime.tzinfo | str | None, default None
    Timezone name or tzinfo to attach without converting the clock fields.
    None produces a naive value. Named regions use ZoneInfo; nonexistent
    regional local times raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.

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
    def fromdatetime(cls, dt: datetime.datetime, tz: datetime.tzinfo | str | None=None) -> Self:
        """Copy a datetime, optionally replacing its timezone without conversion.

Parameters
----------
dt : datetime.datetime
    A Python datetime, including a true datetime subclass. Its stored calendar,
    timezone and fold are read. Pandas Timestamp uses its actual date,
    not a substitute year; NaT is rejected. Wide dates that cannot fit
    Pydt raise OverflowError.
tz : datetime.tzinfo | str | None, default None
    Optional timezone name or tzinfo to attach or replace without moving clock
    fields. None retains the source timezone and fold.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.

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
    def fromdatetime64(cls, dt64: np.datetime64, tz: datetime.tzinfo | str | None=None) -> Self:
        """Copy a NumPy datetime64 scalar at microsecond precision.

Parameters
----------
dt64 : np.datetime64
    One NumPy datetime64 scalar. Dtype multipliers are honored. Submicrosecond values are floored to microseconds and NaT
    raises ValueError. Collections are unsupported; tz attaches to the decoded
    clock fields without converting them.
tz : datetime.tzinfo | str | None, default None
    Timezone name or tzinfo to attach without converting the clock fields.
    None produces a naive value. Named regions use ZoneInfo; nonexistent
    regional local times raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.

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
    def strptime(cls, dtstr: str, fmt: str, *, cfg: Configs | None = None) -> Self:
        """Build a datetime by parsing text with a strptime format.
        
        Parameters
        ----------
        dtstr : str
            Date/time text to parse. This argument must be a string.
        fmt : str
            A shared strptime format, for example "%Y-%m-%d". Fractional seconds
            are read completely and truncated once to microseconds at output.
        
        cfg : Configs or None, default None
            Current month, weekday, AM/PM and explicit timezone names. None uses
            default Rust words. Unknown %Z names require Configs registration.
        
        Returns
        -------
        Pydt
            An immutable Pydt value of the same subclass.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ValueError
            An input is invalid or cannot retain the requested date/time meaning.
        OverflowError
            An integer conversion or result exceeds the supported range.
        """
        ...

    def dst(self) -> datetime.timedelta | None:
        """Return the timezone's daylight-saving adjustment, or None.
        
        Returns
        -------
        datetime.timedelta | None
            The timezone's actual duration, including a supported pandas duration.
        
        Raises
        ------
        TypeError
            The timezone returns something other than None or a timedelta.
        ValueError
            The adjustment is not strictly between -24 and +24 hours."""
        ...

    def timetuple(self) -> time.struct_time:
        """Return local calendar fields as a time.struct_time.
        
        Returns
        -------
        time.struct_time
            Local fields. tm_isdst is -1 for an unknown adjustment, 0 for zero,
            or 1 for a nonzero adjustment, including negative daylight saving.
        
        Raises
        ------
        TypeError
            The timezone returns an unsupported DST value.
        ValueError
            The daylight-saving adjustment is outside the supported range."""
        ...

    def timedict(self) -> dict[str, int]:
        """Return local calendar fields under the standard tm_* names.

Returns
-------
dict[str, int]
    Local calendar fields. tm_isdst is -1 for None, 0 for zero, and 1
    for a legal nonzero DST duration, including negative or nanosecond values."""
        ...

    def utctimedict(self) -> dict[str, int]:
        """Return UTC calendar fields under the standard tm_* names.

Returns
-------
dict[str, int]
    UTC calendar fields under the standard tm_* names."""
        ...

    def toseconds(self, utc: bool | np.bool_=False) -> float:
        """Return epoch seconds, including the microsecond fraction.

Parameters
----------
utc : bool, default False
    True subtracts the aware UTC offset before measuring epoch units. False uses
    local clock fields directly; naive values use their clock fields in either
    case. Only bool and numpy.bool_ are accepted; other values raise TypeError
    without invoking their truth-conversion methods.

Returns
-------
float
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated.

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
>>> value = Pydt(1970, 1, 1, 8, tzinfo="Asia/Shanghai")
>>> value.toseconds(), value.toseconds(utc=True)
(28800.0, 0.0)
"""
        ...

    def tomicroseconds(self, utc: bool | np.bool_=False) -> int:
        """Return exact epoch microseconds; optionally subtract an aware UTC offset.

Parameters
----------
utc : bool, default False
    True subtracts the aware UTC offset before measuring epoch units. False uses
    local clock fields directly; naive values use their clock fields in either
    case. Only bool and numpy.bool_ are accepted; other values raise TypeError
    without invoking their truth-conversion methods.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated.

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
>>> value = Pydt(1970, 1, 1, 8, tzinfo="Asia/Shanghai")
>>> value.tomicroseconds(), value.tomicroseconds(utc=True)
(28800000000, 0)
"""
        ...

    def to_curr_year(self, month: SupportsIndex | str | None=None, day: SupportsIndex | None=None) -> Self:
        """Select a date in the current year; retain the time.

Parameters
----------
month : int | str | None, default None
    Month in 1..12 or a stored month name; None retains the current month.
    Invalid numeric selections raise ValueError.
day : int | None, default None
    Day in 1..31 to select, or None to retain the original day. A valid
    requested day may be limited to the destination month end; other values
    raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_prev_year(self, month: SupportsIndex | str | None=None, day: SupportsIndex | None=None) -> Self:
        """Select a date in the previous year; retain the time.

Parameters
----------
month : int | str | None, default None
    Month in 1..12 or a stored month name; None retains the current month.
    Invalid numeric selections raise ValueError.
day : int | None, default None
    Day in 1..31 to select, or None to retain the original day. A valid
    requested day may be limited to the destination month end; other values
    raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_next_year(self, month: SupportsIndex | str | None=None, day: SupportsIndex | None=None) -> Self:
        """Select a date in the next year; retain the time.

Parameters
----------
month : int | str | None, default None
    Month in 1..12 or a stored month name; None retains the current month.
    Invalid numeric selections raise ValueError.
day : int | None, default None
    Day in 1..31 to select, or None to retain the original day. A valid
    requested day may be limited to the destination month end; other values
    raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_year(self, offset: SupportsIndex, month: SupportsIndex | str | None=None, day: SupportsIndex | None=None) -> Self:
        """Move by years, optionally selecting the destination month.

Parameters
----------
offset : number
    Signed calendar periods to move. Negative values move earlier and zero keeps
    the current period; it is a real increment, not a missing-field marker.
month : int | str | None, default None
    Month in 1..12 or a stored month name; None retains the current month.
    Invalid numeric selections raise ValueError.
day : int | None, default None
    Day in 1..31 to select, or None to retain the original day. A valid
    requested day may be limited to the destination month end; other values
    raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_curr_quarter(self, month: SupportsIndex | None=None, day: SupportsIndex | None=None) -> Self:
        """Select a date in the current quarter; retain the time.

Parameters
----------
month : int | None, default None
    Position 1, 2 or 3 within the destination quarter. None retains the original
    position; out-of-range values raise ValueError.
day : int | None, default None
    Day in 1..31 to select, or None to retain the original day. A valid
    requested day may be limited to the destination month end; other values
    raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_prev_quarter(self, month: SupportsIndex | None=None, day: SupportsIndex | None=None) -> Self:
        """Select a date in the previous quarter; retain the time.

Parameters
----------
month : int | None, default None
    Position 1, 2 or 3 within the destination quarter. None retains the original
    position; out-of-range values raise ValueError.
day : int | None, default None
    Day in 1..31 to select, or None to retain the original day. A valid
    requested day may be limited to the destination month end; other values
    raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_next_quarter(self, month: SupportsIndex | None=None, day: SupportsIndex | None=None) -> Self:
        """Select a date in the next quarter; retain the time.

Parameters
----------
month : int | None, default None
    Position 1, 2 or 3 within the destination quarter. None retains the original
    position; out-of-range values raise ValueError.
day : int | None, default None
    Day in 1..31 to select, or None to retain the original day. A valid
    requested day may be limited to the destination month end; other values
    raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_quarter(self, offset: SupportsIndex, month: SupportsIndex | None=None, day: SupportsIndex | None=None) -> Self:
        """Move by quarters, optionally selecting the destination month.

Parameters
----------
offset : number
    Signed calendar periods to move. Negative values move earlier and zero keeps
    the current period; it is a real increment, not a missing-field marker.
month : int | None, default None
    Position 1, 2 or 3 within the destination quarter. None retains the original
    position; out-of-range values raise ValueError.
day : int | None, default None
    Day in 1..31 to select, or None to retain the original day. A valid
    requested day may be limited to the destination month end; other values
    raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_curr_month(self, day: SupportsIndex | None=None) -> Self:
        """Select a day in the current month, limiting it to month end.

Parameters
----------
day : int | None, default None
    Day in 1..31 to select, or None to retain the original day. A valid
    requested day may be limited to the destination month end; other values
    raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_prev_month(self, day: SupportsIndex | None=None) -> Self:
        """Select a day in the previous month, limiting it to month end.

Parameters
----------
day : int | None, default None
    Day in 1..31 to select, or None to retain the original day. A valid
    requested day may be limited to the destination month end; other values
    raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_next_month(self, day: SupportsIndex | None=None) -> Self:
        """Select a day in the next month, limiting it to month end.

Parameters
----------
day : int | None, default None
    Day in 1..31 to select, or None to retain the original day. A valid
    requested day may be limited to the destination month end; other values
    raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_month(self, offset: SupportsIndex, day: SupportsIndex | None=None) -> Self:
        """Move by calendar months, limiting the day to the destination month.

Parameters
----------
offset : number
    Signed calendar periods to move. Negative values move earlier and zero keeps
    the current period; it is a real increment, not a missing-field marker.
day : int | None, default None
    Day in 1..31 to select, or None to retain the original day. A valid
    requested day may be limited to the destination month end; other values
    raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_monday(self) -> Self:
        """Return Monday in this week, retaining the time.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes."""
        ...

    def to_tuesday(self) -> Self:
        """Return Tuesday in this week, retaining the time.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes."""
        ...

    def to_wednesday(self) -> Self:
        """Return Wednesday in this week, retaining the time.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes."""
        ...

    def to_thursday(self) -> Self:
        """Return Thursday in this week, retaining the time.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes."""
        ...

    def to_friday(self) -> Self:
        """Return Friday in this week, retaining the time.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes."""
        ...

    def to_saturday(self) -> Self:
        """Return Saturday in this week, retaining the time.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes."""
        ...

    def to_sunday(self) -> Self:
        """Return Sunday in this week, retaining the time.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes."""
        ...

    def to_curr_weekday(self, weekday: SupportsIndex | str | None=None) -> Self:
        """Select a weekday in the current week; retain the time.

Parameters
----------
weekday : int | str | None, default None
    Weekday 0 (Monday) through 6 (Sunday), a stored weekday name, or None to
    keep the original weekday. Out-of-range integers raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_prev_weekday(self, weekday: SupportsIndex | str | None=None) -> Self:
        """Select a weekday in the previous week; retain the time.

Parameters
----------
weekday : int | str | None, default None
    Weekday 0 (Monday) through 6 (Sunday), a stored weekday name, or None to
    keep the original weekday. Out-of-range integers raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_next_weekday(self, weekday: SupportsIndex | str | None=None) -> Self:
        """Select a weekday in the next week; retain the time.

Parameters
----------
weekday : int | str | None, default None
    Weekday 0 (Monday) through 6 (Sunday), a stored weekday name, or None to
    keep the original weekday. Out-of-range integers raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_weekday(self, offset: SupportsIndex, weekday: SupportsIndex | str | None=None) -> Self:
        """Move by calendar weeks and optionally select a stored weekday.

Parameters
----------
offset : number
    Signed calendar periods to move. Negative values move earlier and zero keeps
    the current period; it is a real increment, not a missing-field marker.
weekday : int | str | None, default None
    Weekday 0 (Monday) through 6 (Sunday), a stored weekday name, or None to
    keep the original weekday. Out-of-range integers raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_yesterday(self) -> Self:
        """Return the preceding calendar day at the same time.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes."""
        ...

    def to_tomorrow(self) -> Self:
        """Return the next calendar day at the same time.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes."""
        ...

    def to_day(self, offset: SupportsIndex) -> Self:
        """Move by whole calendar days, retaining the time and timezone.

Parameters
----------
offset : number
    Signed calendar periods to move. Negative values move earlier and zero keeps
    the current period; it is a real increment, not a missing-field marker.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def normalize(self) -> Self:
        """Return the first existing local time on this date, retaining the timezone.

A missing midnight selects the first existing time within this date; it never uses the preceding date as a substitute. A wholly missing date has no valid beginning.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes."""
        ...

    def to_datetime(self, year: SupportsIndex | None=None, month: SupportsIndex | None=None, day: SupportsIndex | None=None, hour: SupportsIndex | None=None, minute: SupportsIndex | None=None, second: SupportsIndex | None=None, microsecond: SupportsIndex | None=None) -> Self:
        """Set selected date/time fields; None preserves a field and explicit numbers are checked.

A requested day in 1..31 is limited to the destination month's last day. Other explicit fields must be within their usual ranges; use replace() to require an exact valid date.

Parameters
----------
year : int | None, default None
    Year field in 1 through 9999. None retains the existing field.
month : int | None, default None
    Month number in 1..12; None retains the current month.
    Python and NumPy integers, including integer-index values, are accepted.
    Floats, booleans and month names raise TypeError.
    Invalid numeric selections raise ValueError.
day : int | None, default None
    Day in 1..31 to select, or None to retain the original day. A valid
    requested day may be limited to the destination month end; other values
    raise ValueError.
hour : int | None, default None
    Hour field in 0 through 23. None retains the existing field.
minute : int | None, default None
    Minute field in 0 through 59. None retains the existing field.
second : int | None, default None
    Second field in 0 through 59. None retains the existing field.
microsecond : int | None, default None
    Microsecond field in 0 through 999999. None retains the existing field.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Examples
--------
>>> from rstimes import Pydt
>>> value = Pydt(2024, 1, 31, 12)
>>> result = value.to_datetime(month=2, hour=0)
>>> (result.month, result.day, result.hour)
(2, 29, 0)

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_date(self, year: SupportsIndex | None=None, month: SupportsIndex | None=None, day: SupportsIndex | None=None) -> Self:
        """Set date fields and limit the final day to the destination month.

None retains a date field. A requested day in 1..31 is limited to the destination month's last day.

Parameters
----------
year : int | None, default None
    Year field in 1 through 9999. None retains the existing field.
month : int | None, default None
    Month number in 1..12; None retains the current month.
    Python and NumPy integers, including integer-index values, are accepted.
    Floats, booleans and month names raise TypeError.
    Invalid numeric selections raise ValueError.
day : int | None, default None
    Day in 1..31 to select, or None to retain the original day. A valid
    requested day may be limited to the destination month end; other values
    raise ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Examples
--------
>>> from rstimes import Pydt
>>> value = Pydt(2024, 1, 31, 12)
>>> result = value.to_date(month=2)
>>> (result.month, result.day)
(2, 29)

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_time(self, hour: SupportsIndex | None=None, minute: SupportsIndex | None=None, second: SupportsIndex | None=None, microsecond: SupportsIndex | None=None) -> Self:
        """Set clock fields; None preserves a field and zero sets it to zero.

Explicit clock fields require the integer index protocol; floats, negative values and values above the normal maximum are rejected.

Parameters
----------
hour : int | None, default None
    Hour field in 0 through 23. None retains the existing field.
minute : int | None, default None
    Minute field in 0 through 59. None retains the existing field.
second : int | None, default None
    Second field in 0 through 59. None retains the existing field.
microsecond : int | None, default None
    Microsecond field in 0 through 999999. None retains the existing field.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

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
>>> value = Pydt(2024, 1, 2, 12)
>>> (value.to_time(hour=None).hour, value.to_time(hour=0).hour)
(12, 0)"""
        ...

    def to_first_of(self, unit: str | Literal['Y', 'Q', 'M', 'W']) -> Self:
        """Return the first of a calendar period or named month.

Parameters
----------
unit : str | Literal['Y', 'Q', 'M', 'W']
    Calendar period or stored month name; start/end operations also accept
    stored weekday names and clock units. Unknown or empty names raise
    ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_last_of(self, unit: str | Literal['Y', 'Q', 'M', 'W']) -> Self:
        """Return the last of a calendar period or named month.

Parameters
----------
unit : str | Literal['Y', 'Q', 'M', 'W']
    Calendar period or stored month name; start/end operations also accept
    stored weekday names and clock units. Unknown or empty names raise
    ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def to_start_of(self, unit: str | Literal['Y', 'Q', 'M', 'W', 'D', 'h', 'm', 's', 'ms', 'us']) -> Self:
        """Return the start of a calendar period or named month/weekday.

For 'us' and its 'ns' alias, return this same object, retaining fold
and the represented instant.

Parameters
----------
unit : str | Literal['Y', 'Q', 'M', 'W', 'D', 'h', 'm', 's', 'ms', 'us']
    Calendar period or stored month name; start/end operations also accept
    stored weekday names and clock units. Unknown or empty names raise
    ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

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
>>> value = Pydt(2024, 5, 7, 9, 30, fold=1)
>>> value.to_start_of("us") is value
True"""
        ...

    def to_end_of(self, unit: str | Literal['Y', 'Q', 'M', 'W', 'D', 'h', 'm', 's', 'ms', 'us']) -> Self:
        """Return the end of a calendar period or named month/weekday.

For 'us' and its 'ns' alias, return this same object, retaining fold
and the represented instant.

Parameters
----------
unit : str | Literal['Y', 'Q', 'M', 'W', 'D', 'h', 'm', 's', 'ms', 'us']
    Calendar period or stored month name; start/end operations also accept
    stored weekday names and clock units. Unknown or empty names raise
    ValueError.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def is_first_of(self, unit: str | Literal['Y', 'Q', 'M', 'W']) -> bool:
        """Test whether this date is the period's first calendar day, ignoring the clock.

Parameters
----------
unit : str | Literal['Y', 'Q', 'M', 'W']
    Calendar period or stored month name; start/end operations also accept
    stored weekday names and clock units. Unknown or empty names raise
    ValueError.

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

    def is_last_of(self, unit: str | Literal['Y', 'Q', 'M', 'W']) -> bool:
        """Test whether this date is the period's last calendar day, ignoring the clock.

Parameters
----------
unit : str | Literal['Y', 'Q', 'M', 'W']
    Calendar period or stored month name; start/end operations also accept
    stored weekday names and clock units. Unknown or empty names raise
    ValueError.

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

    def is_start_of(self, unit: str | Literal['Y', 'Q', 'M', 'W', 'D', 'h', 'm', 's', 'ms', 'us']) -> bool:
        """Test whether this value is the period's first existing local time.

Always True for the native microsecond unit 'us' and its 'ns' alias.

Parameters
----------
unit : str | Literal['Y', 'Q', 'M', 'W', 'D', 'h', 'm', 's', 'ms', 'us']
    Calendar period or stored month name; start/end operations also accept
    stored weekday names and clock units. Unknown or empty names raise
    ValueError.

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

    def is_end_of(self, unit: str | Literal['Y', 'Q', 'M', 'W', 'D', 'h', 'm', 's', 'ms', 'us']) -> bool:
        """Test whether this value is the period's last existing local time.

Always True for the native microsecond unit 'us' and its 'ns' alias.

Parameters
----------
unit : str | Literal['Y', 'Q', 'M', 'W', 'D', 'h', 'm', 's', 'ms', 'us']
    Calendar period or stored month name; start/end operations also accept
    stored weekday names and clock units. Unknown or empty names raise
    ValueError.

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

    def round(self, freq: Literal['D', 'h', 'm', 'min', 's', 'ms', 'us', 'ns']) -> Self:
        """Round local clock fields to D, h, m, s, ms or us.

Round local clock fields with ties to even. The result remains frequency-aligned; regional adjustments select an existing boundary.

Parameters
----------
freq : Literal['D', 'h', 'm', 'min', 's', 'ms', 'us', 'ns']
    Single rounding unit: D, h, m/min, s, ms, us or the existing ns alias for
    us. Multi-frequency forms such as 15min are not supported.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def ceil(self, freq: Literal['D', 'h', 'm', 'min', 's', 'ms', 'us', 'ns']) -> Self:
        """Ceil local clock fields to D, h, m, s, ms or us.

Choose an existing frequency-aligned result no earlier than the input instant.

Parameters
----------
freq : Literal['D', 'h', 'm', 'min', 's', 'ms', 'us', 'ns']
    Single rounding unit: D, h, m/min, s, ms, us or the existing ns alias for
    us. Multi-frequency forms such as 15min are not supported.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def floor(self, freq: Literal['D', 'h', 'm', 'min', 's', 'ms', 'us', 'ns']) -> Self:
        """Floor local clock fields to D, h, m, s, ms or us.

Choose an existing frequency-aligned result no later than the input instant.

Parameters
----------
freq : Literal['D', 'h', 'm', 'min', 's', 'ms', 'us', 'ns']
    Single rounding unit: D, h, m/min, s, ms, us or the existing ns alias for
    us. Multi-frequency forms such as 15min are not supported.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def snap(self, unit: str='s') -> Self:
        """Return the nearest existing calendar-period start; equal distances select the later one.

Units are Y, Q, M, W, D, h, m/min, s, ms and us (ns is an existing alias for the unchanged microsecond value), plus the stored weekday/month names. Weeks start on Monday; a month name repeats annually. Aware distances use actual instants. A partially missing period starts at its first existing local time; wholly missing periods are skipped when finding adjacent starts. Repeated clock boundaries are compared as distinct real instants. Calendar periods use their first existing start. No multi-frequency syntax is accepted.

Parameters
----------
unit : str, default 's'
    Single calendar unit or stored month/weekday name listed below. The default
    s selects whole seconds.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

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
>>> Pydt(2024, 1, 2, 12, 30).snap("h").hour
13
>>> Pydt(2024, 1, 2).snap("January").month
1"""
        ...

    def fsp(self, precision: SupportsIndex) -> Self:
        """Keep precision decimal places in the fractional second, without rounding.

Parameters
----------
precision : number
    Decimal places to retain in fractional seconds. Negative precision is
    invalid; Pydt keeps its value unchanged at 6 or more places, while Pddt has
    nanosecond precision.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def isoyear(self) -> int:
        """Return the ISO week-numbering year.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def isoweek(self) -> int:
        """Return the ISO week number, from 1 through 53.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def isoweekday(self) -> int:
        """Return the ISO weekday, Monday=1 through Sunday=7.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def is_year(self, year: SupportsIndex) -> bool:
        """Return whether the year equals year.

Parameters
----------
year : int
    Integer year to compare with the stored value; a nonmatching integer returns
    False.

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

    @property
    def is_leap_year(self) -> bool:
        """Return whether this Gregorian year is a leap year.

Returns
-------
bool
    Whether the stated condition holds. A legitimate nonmatch returns False;
    invalid inputs raise the documented error."""
        ...

    def is_long_year(self) -> bool:
        """Return whether the ISO year has 53 weeks.

Returns
-------
bool
    Whether the stated condition holds. A legitimate nonmatch returns False;
    invalid inputs raise the documented error."""
        ...

    def leap_bt_year(self, year: SupportsIndex) -> int:
        """Count leap years in the half-open interval between the two years.

Parameters
----------
year : number
    Year field in 1 through 9999.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def days_in_year(self) -> int:
        """Return the number of days in this year.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def days_bf_year(self) -> int:
        """Return the number of days before this year, starting at year 1.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def day_of_year(self) -> int:
        """Return the day number within this year, starting at 1.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def quarter(self) -> int:
        """Calendar quarter, 1 through 4.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def is_quarter(self, quarter: SupportsIndex) -> bool:
        """Return whether this value belongs to the requested quarter.

Parameters
----------
quarter : int
    Quarter number to compare with the stored calendar quarter, 1 through 4.

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

    def days_in_quarter(self) -> int:
        """Return the number of days in this quarter.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def days_bf_quarter(self) -> int:
        """Return the number of days in the year before this quarter.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def day_of_quarter(self) -> int:
        """Return the day number within this quarter, starting at 1.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def is_month(self, month: SupportsIndex | str) -> bool:
        """Test a month number or a name in the library's default vocabulary.

Parameters
----------
month : int | str
    Integer month to compare with the stored value; a nonmatching integer
    returns False. A stored name is also accepted; unknown or empty names raise
    ValueError.

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

    @property
    def days_in_month(self) -> int:
        """Return the number of days in this month.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def days_bf_month(self) -> int:
        """Return the number of days in the year before this month.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def day_of_month(self) -> int:
        """Return the day number within this month.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def month_name(self, locale: str | None=None) -> str:
        """Return the full month name in the requested language.

Parameters
----------
locale : str | None, default None
    CLDR locale identifier, for example 'en_US' or 'zh_CN'. None uses English.
    An unknown identifier raises ValueError; other input types raise TypeError.

Returns
-------
str
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def is_weekday(self, weekday: SupportsIndex | str) -> bool:
        """Test a weekday number (Monday=0) or a default weekday name.

Parameters
----------
weekday : int | str
    Integer weekday to compare with the stored value; a nonmatching integer
    returns False. A stored name is also accepted; unknown or empty names raise
    ValueError.

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

    def weekday_name(self, locale: str | None=None) -> str:
        """Return the full weekday name in the requested language.

Parameters
----------
locale : str | None, default None
    CLDR locale identifier, for example 'en_US' or 'zh_CN'. None uses English.
    An unknown identifier raises ValueError; other input types raise TypeError.

Returns
-------
str
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def is_day(self, day: SupportsIndex) -> bool:
        """Return whether the day of month equals day.

Parameters
----------
day : int
    Integer day to compare with the stored value; a nonmatching integer returns
    False.

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

    @property
    def millisecond(self) -> int:
        """Millisecond part of the current second, from 0 through 999.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    @property
    def tz_available(self) -> set[str]:
        """Set of timezone keys available to the system's ZoneInfo database.

Returns
-------
set[str]
    Set of timezone keys available to the system's ZoneInfo database."""
        ...

    @property
    def tz(self) -> datetime.tzinfo | None:
        """Timezone attached to this value; an alias of tzinfo.

Returns
-------
datetime.tzinfo | None
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def is_local(self) -> bool:
        """Return whether this value uses the cached process-local timezone.

Returns
-------
bool
    Whether the stated condition holds. A legitimate nonmatch returns False;
    invalid inputs raise the documented error."""
        ...

    def is_utc(self) -> bool:
        """Return whether this value uses datetime.timezone.utc.

Returns
-------
bool
    Whether the stated condition holds. A legitimate nonmatch returns False;
    invalid inputs raise the documented error."""
        ...

    def is_dst(self) -> bool:
        """Return whether the daylight-saving adjustment is nonzero.
        
        Returns
        -------
        bool
            False for None or a zero duration. Any legal nonzero adjustment,
            including negative daylight saving or a nanosecond, returns True.
        
        Raises
        ------
        TypeError
            The timezone returns something other than None or a timedelta.
        ValueError
            The adjustment is not strictly between -24 and +24 hours.
        
        Examples
        --------
        >>> Pydt(2024, 7, 1, tzinfo="America/New_York").is_dst()
        True"""
        ...

    def utcoffset_seconds(self) -> int | None:
        """Return the UTC offset in whole seconds, or None for a naive value.

Returns
-------
int | None
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def astimezone(self, tz: datetime.tzinfo | str | None=None) -> Self:
        """Express the same instant in tz; None selects the system local timezone.

Parameters
----------
tz : datetime.tzinfo | str | None, default None
    Target timezone name or tzinfo. None selects the process-local timezone; the
    represented instant is preserved.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def tz_localize(self, tz: datetime.tzinfo | str | None) -> Self:
        """Attach a timezone to naive clock fields, or remove it with tz=None.

Attaching a regional timezone rejects a missing local time. fold selects repeated times only; it never repairs a missing time.

Parameters
----------
tz : datetime.tzinfo | str | None
    Timezone name or tzinfo to attach to naive local fields. None removes the
    timezone while retaining the clock.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def tz_convert(self, tz: datetime.tzinfo | str | None) -> Self:
        """Convert an aware value to tz, preserving its instant.

Parameters
----------
tz : datetime.tzinfo | str | None
    Target timezone name or tzinfo. None converts to UTC and then removes the
    timezone; input must be aware.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def tz_switch(self, targ_tz: datetime.tzinfo | str | None, base_tz: datetime.tzinfo | str | None=None, naive: bool | np.bool_=False) -> Self:
        """Convert timezones, supplying base_tz when this value is naive.

Parameters
----------
targ_tz : datetime.tzinfo | str | None
    Target timezone name or tzinfo. None removes the timezone while preserving
    clock fields.
base_tz : datetime.tzinfo | str | None, default None
    Timezone used to interpret a timezone-naive input before conversion. It is
    required when the input has no usable timezone and a target conversion is
    requested.
naive : bool, default False
    True removes the target timezone after conversion. False returns a timezone-
    aware result when a target timezone is given.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def add(self, years: SupportsIndex=0, quarters: SupportsIndex=0, months: SupportsIndex=0, weeks: SupportsIndex=0, days: SupportsIndex=0, hours: SupportsIndex=0, minutes: SupportsIndex=0, seconds: SupportsIndex=0, milliseconds: SupportsIndex=0, microseconds: SupportsIndex=0) -> Self:
        """Add calendar and clock amounts using local wall time.

Parameters
----------
years : number, default 0
    Signed calendar years to add. Negative values reverse that direction; zero
    is a real zero increment.
quarters : number, default 0
    Signed calendar quarters to add. Negative values reverse that direction;
    zero is a real zero increment.
months : number, default 0
    Signed calendar months to add. Negative values reverse that direction; zero
    is a real zero increment.
weeks : number, default 0
    Signed weeks to add. Negative values reverse that direction; zero is a real
    zero increment.
days : number, default 0
    Signed days to add. Negative values reverse that direction; zero is a real
    zero increment.
hours : number, default 0
    Signed hours to add. Negative values reverse that direction; zero is a real
    zero increment.
minutes : number, default 0
    Signed minutes to add. Negative values reverse that direction; zero is a
    real zero increment.
seconds : number, default 0
    Signed seconds to add. Negative values reverse that direction; zero is a
    real zero increment.
milliseconds : number, default 0
    Signed milliseconds to add. Negative values reverse that direction; zero is
    a real zero increment.
microseconds : number, default 0
    Signed microseconds to add. Negative values reverse that direction; zero is
    a real zero increment.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range.

Notes
-----
Relative arguments use the integer index protocol. Floats, booleans, text and
        values providing only __int__ are rejected. Zero is a real increment;
        None is not accepted. Use Delta for fractional fixed durations."""
        ...

    def sub(self, years: SupportsIndex=0, quarters: SupportsIndex=0, months: SupportsIndex=0, weeks: SupportsIndex=0, days: SupportsIndex=0, hours: SupportsIndex=0, minutes: SupportsIndex=0, seconds: SupportsIndex=0, milliseconds: SupportsIndex=0, microseconds: SupportsIndex=0) -> Self:
        """Subtract calendar and clock amounts using the same rules as add().

Parameters
----------
years : number, default 0
    Signed calendar years to subtract. Negative values reverse that direction;
    zero is a real zero increment.
quarters : number, default 0
    Signed calendar quarters to subtract. Negative values reverse that
    direction; zero is a real zero increment.
months : number, default 0
    Signed calendar months to subtract. Negative values reverse that direction;
    zero is a real zero increment.
weeks : number, default 0
    Signed weeks to subtract. Negative values reverse that direction; zero is a
    real zero increment.
days : number, default 0
    Signed days to subtract. Negative values reverse that direction; zero is a
    real zero increment.
hours : number, default 0
    Signed hours to subtract. Negative values reverse that direction; zero is a
    real zero increment.
minutes : number, default 0
    Signed minutes to subtract. Negative values reverse that direction; zero is
    a real zero increment.
seconds : number, default 0
    Signed seconds to subtract. Negative values reverse that direction; zero is
    a real zero increment.
milliseconds : number, default 0
    Signed milliseconds to subtract. Negative values reverse that direction;
    zero is a real zero increment.
microseconds : number, default 0
    Signed microseconds to subtract. Negative values reverse that direction;
    zero is a real zero increment.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range.

Notes
-----
Relative arguments use the integer index protocol. Floats, booleans, text and
        values providing only __int__ are rejected. Zero is a real increment;
        None is not accepted. Use Delta for fractional fixed durations."""
        ...

    def diff(self, dtobj: DatetimeLike, unit: Literal['Y', 'Q', 'M', 'W', 'D', 'h', 'm', 'min', 's', 'ms', 'us'], absolute: bool | np.bool_=False, inclusive: Literal['one', 'both', 'neither']='one') -> int:
        """Count unit boundaries between this value and a supported date input.

Parameters
----------
dtobj : str | date | datetime | int | float | numpy.datetime64
    One supported date/time input: text, a Python date/datetime, numeric epoch
    seconds, or a NumPy datetime64 scalar. NaT and unsupported containers are
    rejected.
unit : Literal['Y', 'Q', 'M', 'W', 'D', 'h', 'm', 'min', 's', 'ms', 'us']
    Calendar or clock boundary unit: Y, Q, M, W, D, h, m/min, s, ms or us.
absolute : bool, default False
    True returns the magnitude of the difference; False retains its sign.
inclusive : Literal['one', 'both', 'neither'], default 'one'
    Boundary-count convention: one counts one endpoint, both adds one to the
    magnitude, and neither subtracts one. Equal boundaries with absolute=True
    and neither may yield -1.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def __add__(self, other: datetime.timedelta | Delta | relativedelta | np.timedelta64) -> Self:
        """Apply a relative calendar or clock increment, returning this datetime type.

Parameters
----------
other : timedelta | Delta | relativedelta | numpy.timedelta64
    Right-hand date/time value or relative increment. Text dates follow parse().

Returns
-------
Pydt
    An immutable result of the same Pydt subclass.

Raises
------
TypeError
    The operand type is unsupported, or aware and naive datetimes are mixed.
ValueError
    A date or timezone rule is invalid.
OverflowError
    The result is outside years 1 through 9999."""
        ...

    def __radd__(self, other: _TimedeltaT | Delta | relativedelta | np.timedelta64) -> Self:
        """Apply reflected addition to a supported time-span operand.

Parameters
----------
other : timedelta | Delta | relativedelta | numpy.timedelta64
    The right-hand operand for this operation. Its accepted types and the result
    type are given by this overload.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    # Deliberate operand extension; keep precise duration/result overloads.
    @overload  # type: ignore[override]
    def __sub__(self, other: datetime.datetime | datetime.date | str | np.datetime64) -> datetime.timedelta:
        """Return the datetime difference as a standard timedelta.

Parameters
----------
other : datetime | date | str | numpy.datetime64
    Right-hand date/time value or relative increment. Text dates follow parse().

Returns
-------
timedelta
    A signed duration. Ordinary datetime operands follow Python subtraction
    rules. Pandas Timestamp operands retain nanoseconds until one final
    nearest-microsecond rounding, with ties to even.

Raises
------
TypeError
    The operand type is unsupported, or aware and naive datetimes are mixed.
ValueError
    A date or timezone rule is invalid.
OverflowError
    The date difference is outside the supported timedelta range.

Examples
--------
>>> from pandas import Timestamp
>>> Pydt(2024, 1, 1) - Timestamp("2024-01-01 00:00:00.000000877") == datetime.timedelta(microseconds=-1)
True"""
        ...

    @overload
    def __sub__(self, other: datetime.timedelta | Delta | relativedelta | np.timedelta64) -> Self:
        """Subtract a relative calendar or clock increment, returning this datetime type.

Parameters
----------
other : timedelta | Delta | relativedelta | numpy.timedelta64
    Right-hand date/time value or relative increment. Text dates follow parse().

Returns
-------
Pydt
    An immutable result of the same Pydt subclass.

Raises
------
TypeError
    The operand type is unsupported, or aware and naive datetimes are mixed.
ValueError
    A date or timezone rule is invalid.
OverflowError
    The result is outside years 1 through 9999."""
        ...

    def is_past(self) -> bool:
        """Return whether this value is before the current instant.

Values with a UTC offset are compared as real instants, including repeated
local times during a clock change. Values with no effective UTC offset
use the local naive clock. A value equal to now returns False.

Returns
-------
bool
    True if this value is strictly before now; otherwise False."""
        ...

    def is_future(self) -> bool:
        """Return whether this value is after the current instant.

Values with a UTC offset are compared as real instants, including repeated
local times during a clock change. Values with no effective UTC offset
use the local naive clock. A value equal to now returns False.

Returns
-------
bool
    True if this value is strictly after now; otherwise False."""
        ...

    def __repr__(self) -> str:
        """Return a readable representation of this value.

Returns
-------
str
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def __format__(self, fmt: str) -> str:
        """Format this datetime using a string specification; an empty string uses the usual representation.

Parameters
----------
fmt : str
    A standard datetime strptime format, or a datetime formatting specification
    for __format__. This must be a string.

Returns
-------
str
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def __reduce__(self) -> str | tuple:
        """Return the versioned pickle representation.

Returns
-------
str | tuple
    Reconstruction data consumed by pickle; use pickle rather than editing this
    state."""
        ...

    def __reduce_ex__(self, protocol: SupportsIndex, /) -> str | tuple:
        """Save date fields separately from independent instance metadata.

Parameters
----------
protocol : int
    Pickle protocol requested by the caller. Reconstruction uses this package's
    validated state format.

Returns
-------
str | tuple
    Reconstruction data consumed by pickle; use pickle rather than editing this
    state."""
        ...

    def __setstate__(self, state: dict[str, object] | tuple[dict[str, object] | None, dict[str, object] | None] | None) -> None:
        """Restore extra instance attributes without changing the date value.

Parameters
----------
state : dict, tuple of two dicts or None
    Additional attributes, or a (dictionary, slots) pair. Either entry may be
    None. Dictionaries must have string keys. The entries are fixed before any
    user attribute setter runs. Use pickle for normal saving and loading.

Returns
-------
None
    Existing dictionary attributes are updated and saved slot values restored;
    the immutable date, timezone and fold are unchanged.

Raises
------
TypeError
    The default state format or an attribute name is invalid.
"""
        ...

    def weekday(self) -> int:
        """Return the day of the week, Monday=0 through Sunday=6.

Returns
-------
int
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

    def replace(self, year: SupportsIndex | None=..., month: SupportsIndex | None=..., day: SupportsIndex | None=..., hour: SupportsIndex | None=..., minute: SupportsIndex | None=..., second: SupportsIndex | None=..., microsecond: SupportsIndex | None=..., tzinfo: datetime.tzinfo | str | None=..., *, fold: SupportsIndex | np.bool_ | None=...) -> Self:
        """Return a new value with selected fields, or self if nothing changes.

Omitted or None numeric fields preserve their stored values. Omitted tzinfo preserves the timezone; tzinfo=None removes it, and a name resolves through ZoneInfo. An invalid date or missing regional time raises ValueError. An unchanged value returns self.

Parameters
----------
year : int | None, optional
    Year field in 1 through 9999. None retains the existing field.
month : int | None, optional
    Month field in 1 through 12. None retains the existing field.
day : int | None, optional
    Day field in 1 through 31. None retains the existing field.
hour : int | None, optional
    Hour field in 0 through 23. None retains the existing field.
minute : int | None, optional
    Minute field in 0 through 59. None retains the existing field.
second : int | None, optional
    Second field in 0 through 59. None retains the existing field.
microsecond : int | None, optional
    Microsecond field in 0 through 999999. None retains the existing field.
tzinfo : datetime.tzinfo | str | None, optional
    Timezone name, tzinfo or None. Omitting it keeps the timezone; None removes
    it. Replacing a timezone keeps the clock fields instead of converting an
    instant.
fold : int | None, optional
    0 selects the earlier and 1 the later occurrence of a repeated local time.
    Numeric None retains it in replace; missing local times are rejected for
    either fold.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

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
>>> value = Pydt(2024, 1, 2, 12)
>>> value.replace(hour=None) is value
True
>>> value.replace(tzinfo="UTC").tzinfo is datetime.timezone.utc
True"""
        ...

    def __replace__(self, **changes: Unpack[_ReplaceFields]) -> Self:
        """Return a strict replacement, retaining numeric fields passed as None.

Parameters
----------
changes : keyword arguments
    Replacement fields year, month, day, hour, minute, second, microsecond, fold
    or tzinfo. Numeric None keeps a field; tzinfo=None removes the timezone.

Returns
-------
Pydt
    An immutable Pydt value of the same subclass.
    A convenience operation may return the original value when nothing changes.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...
