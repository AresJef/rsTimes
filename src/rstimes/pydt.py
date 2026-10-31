"""Datetime with calendar adjustments backed by Rust."""
from datetime import datetime, date as _date, time as _time, timedelta, timezone, tzinfo as _tzinfo
from zoneinfo import ZoneInfo, available_timezones
from operator import index as _index
from numpy import bool_ as _numpy_bool
from ._native import (_pydt_register, _pydt_shift, _pydt_from_us, _pydt_compare_now,
                      _pydt_to_us, _pydt_to_seconds, _pydt_lookup, _pydt_calendar, _pydt_move,
                      _pydt_adjust, _pydt_boundary, _pydt_is_boundary, _pydt_round, _pydt_snap, _pydt_fsp,
                      _pydt_from_ordinal, _pydt_from_doy, _pydt_from_iso, _pydt_leaps,
                      _pydt_copy_datetime, _pydt_copy_date, _pydt_from_instant, _pydt_from_calendar, _pydt_combine, _pydt_calendar_date, _pydt_repr_fields, _pydt_carrier, _pydt_replace, _pydt_replace_general, _pydt_stored_timezone, _pydt_millisecond,
                      _pydt_normalize, _pydt_add, _pydt_diff, _pydt_matches, _pydt_offset_seconds, _pydt_convert, _pydt_flag, _pydt_is_local, _pydt_is_utc, _pydt_name_matches, _pydt_iso, _pydt_from_numpy, _pydt_timedict, _pydt_from_seconds, _pydt_strptime, _pydt_from_numpy_zoned, _pydt_dst, _pydt_is_dst, _pydt_timetuple)
from ._native import parse as _parse, _pydt_strftime
from ._native import _PydtBase, _pydt_binary, _pydt_clock, _pydt_copy_fold, _pydt_reduce
from ._native import _bool_option, _pydt_create
from ._native import _pydt_day_of_year, _pydt_days_in_month, _pydt_is_leap_year
from .errors import _raise_argument_context, _own_error, _external_error, _location_error, _preview, _critical

from ._formatting import prepare_format as _prepare_format
from ._localization import (local_timezone as _local_timezone,
                            resolve_timezone as _timezone, _localized_name)

__all__ = ["Pydt"]
_BOOL_TYPES = (bool, _numpy_bool)


def _restore_pydt(cls, version, fields, tz, fold):
    """Restore a complete date value before separate metadata is installed."""
    try:
        if not issubclass(type(cls), type) or not issubclass(cls, Pydt):
            raise _own_error(TypeError("must be a Pydt class"), "cls", cls)
        if type(version) is not int:
            raise _own_error(TypeError("must be an exact int"), "state.version", version)
        if version != 1:
            raise _own_error(ValueError("unsupported version; only version 1 is supported"), "state.version", version)
        if type(fields) is not tuple or len(fields) != 7:
            raise _own_error(TypeError("must be a tuple of seven integer date/time fields"), "state.fields", fields)
        for name, number in zip(("year", "month", "day", "hour", "minute", "second", "microsecond"), fields):
            if type(number) is not int:
                raise _own_error(TypeError("must be an exact int"), "state.fields." + name, number)
        if type(fold) is not int:
            raise _own_error(TypeError("must be an exact int"), "state.fold", fold)
        if fold not in (0, 1):
            raise _own_error(ValueError("must be 0 or 1"), "state.fold", fold)
        try:
            value = datetime.__new__(cls, *fields, tzinfo=tz, fold=fold)
        except Exception as error:
            raise _external_error(error)
        return _pydt_normalize(value) if tz is not None and type(tz) is not timezone and issubclass(type(tz), ZoneInfo) else value
    except Exception as error:
        _raise_argument_context(error, "Pydt restore", "state", None)


_DATE_DESCRIPTORS = tuple(getattr(datetime, name) for name in
                          ("year", "month", "day", "hour", "minute", "second", "microsecond"))
_UNSET = object()


def _boolean(value, entry, parameter):
    """Prepare a real boolean scalar without generic truth conversion."""
    return _bool_option(value, entry, parameter)


def _datetime_value(value):
    """Make a builtin carrier without public subclass field or constructor hooks."""
    return _pydt_carrier(value)


_TM_KEYS = ("tm_year", "tm_mon", "tm_mday", "tm_hour", "tm_min", "tm_sec",
            "tm_wday", "tm_yday", "tm_isdst")


class Pydt(_PydtBase):
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
    4
    """

    def __new__(cls, year=1, month=1, day=1, hour=0, minute=0, second=0,
                microsecond=0, tzinfo=None, *, fold=0):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            zone = None if tzinfo is None else _timezone(tzinfo, "tzinfo")
            try:
                value = _pydt_create(cls, year, month, day, hour, minute, second,
                                     microsecond, zone, fold)
            except Exception as error:
                raise _external_error(error)
            return _pydt_normalize(value) if zone is not None and type(zone) is not timezone and issubclass(type(zone), ZoneInfo) else value
        except Exception as error:
            _raise_argument_context(error, "Pydt", "arguments", None)

    def to_month(self, offset, day=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_shift(self, offset, 0, None, day)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_month", "arguments", None)

    @classmethod
    def parse(cls, dtobj, default=None, yearfirst=None, dayfirst=None,
              ignoretz=True, isoformat=True, strict=False, cfg=None):
        """Parse text or a supported date object into this class.

        Parameters
        ----------
        dtobj : DatetimeLike
            One supported date/time input: text, a Python date/datetime, numeric epoch
            seconds, or a NumPy datetime64 scalar. NaT and unsupported containers are
            rejected.
        default : object | None, default None
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _parse(dtobj, default, yearfirst, dayfirst, ignoretz, isoformat,
                          strict, cfg, cls)
        except Exception as error:
            _raise_argument_context(error, "Pydt.parse", "dtobj", dtobj)

    @classmethod
    def now(cls, tz=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            if cls is Pydt:
                if tz is None or type(tz) is timezone or type(tz) is ZoneInfo:
                    return _pydt_from_instant(datetime.now(tz))
                zone = _timezone(tz)
                if zone is None or type(zone) is timezone or type(zone) is ZoneInfo:
                    return _pydt_from_instant(datetime.now(zone))
                return _pydt_convert(datetime.now(timezone.utc), zone, output_class=cls)
            zone = _timezone(tz)
            if zone is None or type(zone) is timezone or type(zone) is ZoneInfo:
                try:
                    return cls.fromdatetime(datetime.now(zone))
                except Exception as error:
                    raise _external_error(error)
            return _pydt_convert(datetime.now(timezone.utc), zone, output_class=cls)
        except Exception as error:
            _raise_argument_context(error, "Pydt.now", "arguments", None)

    @classmethod
    def today(cls):
        """Return the current local date and time without a timezone.

        Returns
        -------
        Pydt
            An immutable Pydt value of the same subclass.
        """
        try:
            return cls.now()
        except Exception as error:
            _raise_argument_context(error, "Pydt.today", "arguments", None)

    @classmethod
    def utcnow(cls):
        """Return the current time with the standard UTC timezone attached.

        Returns
        -------
        Pydt
            An immutable Pydt value of the same subclass.
        """
        try:
            if cls is Pydt:
                return _pydt_from_instant(datetime.now(timezone.utc))
            try:
                return cls.fromdatetime(datetime.now(timezone.utc))
            except Exception as error:
                raise _external_error(error)
        except Exception as error:
            _raise_argument_context(error, "Pydt.utcnow", "arguments", None)

    @classmethod
    def combine(cls, date=None, time=None, tz=None):
        """Combine date and time fields; omitted fields use today and midnight.

        Parameters
        ----------
        date : datetime.date | str | None, default None
            Date fields to copy or combine. A missing combine date uses today; accepted
            text is parsed with the library rules.
        time : datetime.time | datetime.datetime | str | None, default None
            Clock fields to combine. None supplies midnight; an input time retains its
            stored fold and timezone unless tz replaces the timezone. A datetime supplies
            only its clock, timezone and fold; pandas NaT raises ValueError.
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
        """
        try:
            if date is None:
                date = _date.today()
            elif type(date) is not _date and not issubclass(type(date), _date):
                date = _parse(date)
            if time is None:
                if cls is Pydt:
                    return _pydt_copy_date(cls, date, _timezone(tz))
                time = _time()
            elif type(time) is datetime or issubclass(type(time), datetime):
                if cls is Pydt:
                    if tz is not None:
                        return _pydt_combine(cls, date, time, _timezone(tz))
                    result = _pydt_combine(cls, date, time)
                    if result is not None:
                        return result
                    source = _pydt_stored_timezone(time)
                    zone = _timezone(source)
                    return _pydt_combine(cls, date, time, zone, zone is not source)
                if tz is None:
                    source = _pydt_stored_timezone(time)
                    zone = _timezone(source)
                    if zone is not source and _pydt_calendar_date(date) == _pydt_calendar_date(time):
                        selected_fold = _pydt_copy_fold(time, zone)
                        time = _pydt_clock(time)
                        time = _time.replace(time, tzinfo=zone, fold=selected_fold)
                    else:
                        time = _pydt_clock(time)
                else:
                    time = _pydt_clock(time)
            elif not issubclass(type(time), _time):
                time = _parse(time, default=datetime(1970, 1, 1), ignoretz=False).timetz()
            if cls is Pydt:
                if tz is None:
                    result = _pydt_combine(cls, date, time)
                    if result is not None:
                        return result
                    zone = _timezone(_time.tzinfo.__get__(time))
                else:
                    zone = _timezone(tz)
                return _pydt_combine(cls, date, time, zone)
            zone = _timezone(tz if tz is not None else _time.tzinfo.__get__(time))
            year = _date.year.__get__(date)
            if year in (1, 1970, 1972):
                year, month, day = _pydt_calendar_date(date)
            else:
                month, day = _date.month.__get__(date), _date.day.__get__(date)
            try:
                return cls(year, month, day, _time.hour.__get__(time),
                           _time.minute.__get__(time), _time.second.__get__(time),
                           _time.microsecond.__get__(time), zone,
                           fold=_time.fold.__get__(time))
            except Exception as error:
                raise _external_error(error)
        except Exception as error:
            _raise_argument_context(error, "Pydt.combine", "arguments", None)

    @classmethod
    def fromordinal(cls, ordinal, tz=None):
        """Build midnight from a Gregorian ordinal; ordinal 1 is 0001-01-01.

        Parameters
        ----------
        ordinal : number
            Gregorian day number, with 1 meaning 0001-01-01. Uses the integer index protocol. Float values, booleans, text and
            byte strings are rejected before checking the supported date range.
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
        """
        try:
            return _pydt_from_ordinal(cls, ordinal, _timezone(tz))
        except Exception as error:
            _raise_argument_context(error, "Pydt.fromordinal", "arguments", None)

    @classmethod
    def fromseconds(cls, seconds, tz=None):
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
        try:
            kind = type(seconds)
            if kind is int or kind is float:
                numeric = seconds
            else:
                if isinstance(seconds, _BOOL_TYPES) or issubclass(kind, (str, bytes, bytearray)):
                    raise _own_error(TypeError("must be numeric"), "seconds", seconds)
                try:
                    numeric = seconds if issubclass(kind, (int, float)) else float(seconds)
                except Exception as error:
                    raise _external_error(error)
            if cls is Pydt:
                return _pydt_from_seconds(cls, numeric, tz)
            value = _parse(numeric, dtclass=cls)
            return value if tz is None else value.replace(tzinfo=_timezone(tz))
        except Exception as error:
            _raise_argument_context(error, "Pydt.fromseconds", "arguments", None)

    @classmethod
    def frommicroseconds(cls, us, tz=None):
        """Build from exact integer epoch microseconds, attaching an optional tz.

        Parameters
        ----------
        us : number
            Integer epoch microseconds, read through the integer index protocol.
            Floats, booleans, strings and byte strings are rejected.
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
        try:
            return _pydt_from_us(cls, us, _timezone(tz))
        except Exception as error:
            _raise_argument_context(error, "Pydt.frommicroseconds", "arguments", None)

    @classmethod
    def fromtimestamp(cls, ts, tz=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            if isinstance(ts, _BOOL_TYPES):
                raise _own_error(TypeError("must be numeric; boolean values are not accepted"), "ts", ts)
            if cls is Pydt:
                factory = datetime.fromtimestamp
                zone = _timezone(tz)
                if zone is None or type(zone) is timezone or type(zone) is ZoneInfo:
                    return _pydt_from_instant(factory(ts, zone))
                return _pydt_convert(factory(ts, timezone.utc), zone, output_class=cls)
            zone = _timezone(tz)
            if zone is None or type(zone) is timezone or type(zone) is ZoneInfo:
                try:
                    return cls.fromdatetime(datetime.fromtimestamp(ts, zone))
                except Exception as error:
                    raise _external_error(error)
            return _pydt_convert(datetime.fromtimestamp(ts, timezone.utc), zone, output_class=cls)
        except Exception as error:
            _raise_argument_context(error, "Pydt.fromtimestamp", "arguments", None)

    @classmethod
    def utcfromtimestamp(cls, ts):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            if isinstance(ts, _BOOL_TYPES):
                raise _own_error(TypeError("must be numeric; boolean values are not accepted"), "ts", ts)
            if cls is Pydt:
                return _pydt_from_instant(datetime.fromtimestamp(ts, timezone.utc))
            try:
                return cls.fromdatetime(datetime.fromtimestamp(ts, timezone.utc))
            except Exception as error:
                raise _external_error(error)
        except Exception as error:
            _raise_argument_context(error, "Pydt.utcfromtimestamp", "arguments", None)

    @classmethod
    def fromisoformat(cls, dtstr):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            if cls is Pydt:
                return _pydt_from_instant(datetime.fromisoformat(dtstr))
            try:
                return cls.fromdatetime(datetime.fromisoformat(dtstr))
            except Exception as error:
                raise _external_error(error)
        except Exception as error:
            _raise_argument_context(error, "Pydt.fromisoformat", "arguments", None)

    @classmethod
    def fromisocalendar(cls, year, week, weekday, tz=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_from_iso(cls, year, week, weekday, _timezone(tz))
        except Exception as error:
            _raise_argument_context(error, "Pydt.fromisocalendar", "arguments", None)

    @classmethod
    def fromdayofyear(cls, year, doy, tz=None):
        """Build from a year and positive day number, limiting high values to year end.

        Parameters
        ----------
        year : number
            Integer year in 1 through 9999, read with the index protocol.
            Floats, booleans, text and byte strings are rejected.
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_from_doy(cls, year, doy, _timezone(tz))
        except Exception as error:
            _raise_argument_context(error, "Pydt.fromdayofyear", "arguments", None)

    @classmethod
    def fromdate(cls, date, tz=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            if not issubclass(type(date), _date):
                raise _own_error(TypeError("must be datetime.date"), "date", date)
            return _pydt_copy_date(cls, date, _timezone(tz))
        except Exception as error:
            _raise_argument_context(error, "Pydt.fromdate", "arguments", None)

    @classmethod
    def fromdatetime(cls, dt, tz=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            if not issubclass(type(dt), datetime):
                raise _own_error(TypeError("must be datetime.datetime"), "dt", dt)
            if tz is None and type(dt) is cls:
                return dt
            return _pydt_copy_datetime(cls, dt, None if tz is None else _timezone(tz))
        except Exception as error:
            _raise_argument_context(error, "Pydt.fromdatetime", "arguments", None)

    def replace(self, year=None, month=None, day=None, hour=None,
                minute=None, second=None, microsecond=None,
                tzinfo=_UNSET, *, fold=None):
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
        True
        """
        try:
            supplied = (year, month, day, hour, minute, second, microsecond)
            if type(self) is Pydt:
                return _pydt_replace(self, supplied, tzinfo, fold, _UNSET)
            return _pydt_replace_general(self, supplied, tzinfo, fold, _UNSET, _timezone)
        except Exception as error:
            _raise_argument_context(error, "Pydt.replace", "arguments", None)

    def __replace__(self, **changes):
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
            An integer conversion or result exceeds the supported range.
        """
        return self.replace(**changes)

    @classmethod
    def fromdatetime64(cls, dt64, tz=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            if tz is None:
                return _pydt_from_numpy(cls, dt64)
            if cls is Pydt:
                return _pydt_from_numpy_zoned(cls, dt64, tz)
            return _pydt_from_numpy(cls, dt64).replace(tzinfo=_timezone(tz))
        except Exception as error:
            _raise_argument_context(error, "Pydt.fromdatetime64", "arguments", None)

    @classmethod
    def strptime(cls, dtstr, fmt, *, cfg=None):
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
        try:
            return _pydt_strptime(cls, dtstr, _prepare_format(fmt), cfg)
        except Exception as error:
            _raise_argument_context(error, "Pydt.strptime", "arguments", None)

    def dst(self):
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
            The adjustment is not strictly between -24 and +24 hours.
        """
        try:
            return _pydt_dst(self)
        except Exception as error:
            _raise_argument_context(error, "Pydt.dst", "arguments", None)

    def timetuple(self):
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
            The daylight-saving adjustment is outside the supported range.
        """
        try:
            return _pydt_timetuple(self)
        except Exception as error:
            _raise_argument_context(error, "Pydt.timetuple", "arguments", None)

    def timedict(self):
        """Return local calendar fields under the standard tm_* names.

        Returns
        -------
        dict[str, int]
            Local calendar fields. tm_isdst is -1 for None, 0 for zero, and 1
            for a legal nonzero DST duration, including negative or nanosecond values.
        """
        try:
            return _pydt_timedict(self, False)
        except Exception as error:
            _raise_argument_context(error, "Pydt.timedict", "arguments", None)

    def utctimedict(self):
        """Return UTC calendar fields under the standard tm_* names.

        Returns
        -------
        dict[str, int]
            UTC calendar fields under the standard tm_* names.
        """
        try:
            return _pydt_timedict(self, True)
        except Exception as error:
            _raise_argument_context(error, "Pydt.utctimedict", "arguments", None)

    def tomicroseconds(self, utc=False):
        """Return exact epoch microseconds; optionally subtract an aware UTC offset.

        Parameters
        ----------
        utc : bool, default False
            True subtracts the aware UTC offset before measuring epoch units. False uses
            local clock fields directly; naive values use their clock fields in either
            case. Only Python bool or numpy.bool_ is accepted. Other values, including
            integers and arbitrary truth-value objects, raise TypeError without
            calling their __bool__ method.

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
        try:
            return _pydt_to_us(self, utc)
        except Exception as error:
            _raise_argument_context(error, "Pydt.tomicroseconds", "arguments", None)

    def toseconds(self, utc=False):
        """Return epoch seconds, including the microsecond fraction.

        Parameters
        ----------
        utc : bool, default False
            True subtracts the aware UTC offset before measuring epoch units. False uses
            local clock fields directly; naive values use their clock fields in either
            case. Only Python bool or numpy.bool_ is accepted. Other values, including
            integers and arbitrary truth-value objects, raise TypeError without
            calling their __bool__ method.

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
        try:
            return _pydt_to_seconds(self, utc)
        except Exception as error:
            _raise_argument_context(error, "Pydt.toseconds", "arguments", None)

    def isoyear(self):
        """Return the ISO week-numbering year.

        Returns
        -------
        int
            The value described above, in the stated type and units; None represents an
            absent optional field or offset where indicated.
        """
        try:
            return _pydt_iso(self, True)
        except Exception as error:
            _raise_argument_context(error, "Pydt.isoyear", "arguments", None)

    def isoweek(self):
        """Return the ISO week number, from 1 through 53.

        Returns
        -------
        int
            The value described above, in the stated type and units; None represents an
            absent optional field or offset where indicated.
        """
        try:
            return _pydt_iso(self, False)
        except Exception as error:
            _raise_argument_context(error, "Pydt.isoweek", "arguments", None)

    isoweekday = datetime.isoweekday

    def is_year(self, year):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_matches(self, 0, year)
        except Exception as error:
            _raise_argument_context(error, "Pydt.is_year", "arguments", None)

    def leap_bt_year(self, year):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_leaps(self, year)
        except Exception as error:
            _raise_argument_context(error, "Pydt.leap_bt_year", "arguments", None)

    @property
    def quarter(self):
        """Calendar quarter, 1 through 4.

        Returns
        -------
        int
            The value described above, in the stated type and units; None represents an
            absent optional field or offset where indicated.
        """
        try:
            return _pydt_calendar(self, 0)
        except Exception as error:
            _raise_argument_context(error, "Pydt.quarter", "arguments", None)

    def is_quarter(self, quarter):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_matches(self, 1, quarter)
        except Exception as error:
            _raise_argument_context(error, "Pydt.is_quarter", "arguments", None)

    def is_month(self, month):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_name_matches(self, month, False)
        except Exception as error:
            _raise_argument_context(error, "Pydt.is_month", "month", month)

    def is_weekday(self, weekday):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_name_matches(self, weekday, True)
        except Exception as error:
            _raise_argument_context(error, "Pydt.is_weekday", "weekday", weekday)

    def is_day(self, day):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_matches(self, 2, day)
        except Exception as error:
            _raise_argument_context(error, "Pydt.is_day", "arguments", None)

    def month_name(self, locale=None):
        """Return the full month name, in the requested language.

        Parameters
        ----------
        locale : str | None, default None
            CLDR locale identifier, such as 'en_US' or 'zh_CN'. None uses English.

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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _localized_name(self, locale, False)
        except Exception as error:
            _raise_argument_context(error, "Pydt.month_name", "locale", locale)

    def weekday_name(self, locale=None):
        """Return the full weekday name, in the requested language.

        Parameters
        ----------
        locale : str | None, default None
            CLDR locale identifier, such as 'en_US' or 'zh_CN'. None uses English.

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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _localized_name(self, locale, True)
        except Exception as error:
            _raise_argument_context(error, "Pydt.weekday_name", "locale", locale)

    @property
    def millisecond(self):
        """Millisecond part of the current second, from 0 through 999.

        Returns
        -------
        int
            The value described above, in the stated type and units; None represents an
            absent optional field or offset where indicated.
        """
        try:
            return _pydt_millisecond(self)
        except Exception as error:
            _raise_argument_context(error, "Pydt.millisecond", "arguments", None)

    is_leap_year = property(
        _pydt_is_leap_year,
        doc="""Return whether this Gregorian year is a leap year.

        Returns
        -------
        bool
            Whether the stated condition holds. A legitimate nonmatch returns False;
            invalid inputs raise the documented error.
        """,
    )

    def is_long_year(self):
        """Return whether the ISO year has 53 weeks.

        Returns
        -------
        bool
            Whether the stated condition holds. A legitimate nonmatch returns False;
            invalid inputs raise the documented error.
        """
        try:
            return _pydt_flag(self, 3)
        except Exception as error:
            _raise_argument_context(error, "Pydt.is_long_year", "arguments", None)

    def days_in_year(self):
        """Return the number of days in this year.

        Returns
        -------
        int
            The value described above, in the stated type and units; None represents an
            absent optional field or offset where indicated.
        """
        try:
            return _pydt_calendar(self, 1)
        except Exception as error:
            _raise_argument_context(error, "Pydt.days_in_year", "arguments", None)

    def days_bf_year(self):
        """Return the number of days before this year, starting at year 1.

        Returns
        -------
        int
            The value described above, in the stated type and units; None represents an
            absent optional field or offset where indicated.
        """
        try:
            return _pydt_calendar(self, 2)
        except Exception as error:
            _raise_argument_context(error, "Pydt.days_bf_year", "arguments", None)

    day_of_year = property(
        _pydt_day_of_year,
        doc="""Return the day number within this year, starting at 1.

        Returns
        -------
        int
            The value described above, in the stated type and units; None represents an
            absent optional field or offset where indicated.
        """,
    )

    def days_in_quarter(self):
        """Return the number of days in this quarter.

        Returns
        -------
        int
            The value described above, in the stated type and units; None represents an
            absent optional field or offset where indicated.
        """
        try:
            return _pydt_calendar(self, 4)
        except Exception as error:
            _raise_argument_context(error, "Pydt.days_in_quarter", "arguments", None)

    def days_bf_quarter(self):
        """Return the number of days in the year before this quarter.

        Returns
        -------
        int
            The value described above, in the stated type and units; None represents an
            absent optional field or offset where indicated.
        """
        try:
            return _pydt_calendar(self, 5)
        except Exception as error:
            _raise_argument_context(error, "Pydt.days_bf_quarter", "arguments", None)

    def day_of_quarter(self):
        """Return the day number within this quarter, starting at 1.

        Returns
        -------
        int
            The value described above, in the stated type and units; None represents an
            absent optional field or offset where indicated.
        """
        try:
            return _pydt_calendar(self, 6)
        except Exception as error:
            _raise_argument_context(error, "Pydt.day_of_quarter", "arguments", None)

    days_in_month = property(
        _pydt_days_in_month,
        doc="""Return the number of days in this month.

        Returns
        -------
        int
            The value described above, in the stated type and units; None represents an
            absent optional field or offset where indicated.
        """,
    )

    def days_bf_month(self):
        """Return the number of days in the year before this month.

        Returns
        -------
        int
            The value described above, in the stated type and units; None represents an
            absent optional field or offset where indicated.
        """
        try:
            return _pydt_calendar(self, 8)
        except Exception as error:
            _raise_argument_context(error, "Pydt.days_bf_month", "arguments", None)

    def day_of_month(self):
        """Return the day number within this month.

        Returns
        -------
        int
            The value described above, in the stated type and units; None represents an
            absent optional field or offset where indicated.
        """
        try:
            return _pydt_calendar(self, 9)
        except Exception as error:
            _raise_argument_context(error, "Pydt.day_of_month", "arguments", None)


    weekday = datetime.weekday


    def to_year(self, offset, month=None, day=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_move(self, 0, offset, month, day)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_year", "arguments", None)

    def to_curr_year(self, month=None, day=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_move(self, 0, 0, month, day)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_curr_year", "arguments", None)

    def to_prev_year(self, month=None, day=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_move(self, 0, -1, month, day)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_prev_year", "arguments", None)

    def to_next_year(self, month=None, day=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_move(self, 0, 1, month, day)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_next_year", "arguments", None)

    def to_quarter(self, offset, month=None, day=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_move(self, 1, offset, month, day)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_quarter", "arguments", None)

    def to_curr_quarter(self, month=None, day=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_move(self, 1, 0, month, day)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_curr_quarter", "arguments", None)

    def to_prev_quarter(self, month=None, day=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_move(self, 1, -1, month, day)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_prev_quarter", "arguments", None)

    def to_next_quarter(self, month=None, day=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_move(self, 1, 1, month, day)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_next_quarter", "arguments", None)

    def to_weekday(self, offset, weekday=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_move(self, 3, offset, weekday)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_weekday", "arguments", None)

    def to_curr_weekday(self, weekday=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_move(self, 3, 0, weekday)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_curr_weekday", "arguments", None)

    def to_prev_weekday(self, weekday=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_move(self, 3, -1, weekday)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_prev_weekday", "arguments", None)

    def to_next_weekday(self, weekday=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_move(self, 3, 1, weekday)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_next_weekday", "arguments", None)

    def to_curr_month(self, day=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_shift(self, 0, 0, None, day)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_curr_month", "arguments", None)

    def to_prev_month(self, day=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_shift(self, -1, 0, None, day)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_prev_month", "arguments", None)

    def to_next_month(self, day=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_shift(self, 1, 0, None, day)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_next_month", "arguments", None)

    def to_monday(self):
        """Return Monday in this week, retaining the time.

        Returns
        -------
        Pydt
            An immutable Pydt value of the same subclass.
            A convenience operation may return the original value when nothing changes.
        """
        try:
            return _pydt_move(self, 3, 0, 0)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_monday", "arguments", None)

    def to_tuesday(self):
        """Return Tuesday in this week, retaining the time.

        Returns
        -------
        Pydt
            An immutable Pydt value of the same subclass.
            A convenience operation may return the original value when nothing changes.
        """
        try:
            return _pydt_move(self, 3, 0, 1)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_tuesday", "arguments", None)

    def to_wednesday(self):
        """Return Wednesday in this week, retaining the time.

        Returns
        -------
        Pydt
            An immutable Pydt value of the same subclass.
            A convenience operation may return the original value when nothing changes.
        """
        try:
            return _pydt_move(self, 3, 0, 2)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_wednesday", "arguments", None)

    def to_thursday(self):
        """Return Thursday in this week, retaining the time.

        Returns
        -------
        Pydt
            An immutable Pydt value of the same subclass.
            A convenience operation may return the original value when nothing changes.
        """
        try:
            return _pydt_move(self, 3, 0, 3)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_thursday", "arguments", None)

    def to_friday(self):
        """Return Friday in this week, retaining the time.

        Returns
        -------
        Pydt
            An immutable Pydt value of the same subclass.
            A convenience operation may return the original value when nothing changes.
        """
        try:
            return _pydt_move(self, 3, 0, 4)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_friday", "arguments", None)

    def to_saturday(self):
        """Return Saturday in this week, retaining the time.

        Returns
        -------
        Pydt
            An immutable Pydt value of the same subclass.
            A convenience operation may return the original value when nothing changes.
        """
        try:
            return _pydt_move(self, 3, 0, 5)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_saturday", "arguments", None)

    def to_sunday(self):
        """Return Sunday in this week, retaining the time.

        Returns
        -------
        Pydt
            An immutable Pydt value of the same subclass.
            A convenience operation may return the original value when nothing changes.
        """
        try:
            return _pydt_move(self, 3, 0, 6)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_sunday", "arguments", None)

    def to_day(self, offset):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_shift(self, 0, offset)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_day", "arguments", None)

    def to_yesterday(self):
        """Return the preceding calendar day at the same time.

        Returns
        -------
        Pydt
            An immutable Pydt value of the same subclass.
            A convenience operation may return the original value when nothing changes.
        """
        try:
            return _pydt_shift(self, 0, -1)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_yesterday", "arguments", None)

    def to_tomorrow(self):
        """Return the next calendar day at the same time.

        Returns
        -------
        Pydt
            An immutable Pydt value of the same subclass.
            A convenience operation may return the original value when nothing changes.
        """
        try:
            return _pydt_shift(self, 0, 1)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_tomorrow", "arguments", None)

    def normalize(self):
        """Return the first existing local time on this date, retaining the timezone.

        A missing midnight selects the first existing time within this date; it never uses the preceding date as a substitute. A wholly missing date has no valid beginning.

        Returns
        -------
        Pydt
            An immutable Pydt value of the same subclass.
            A convenience operation may return the original value when nothing changes.
        """
        try:
            return _pydt_boundary(self, "D", False, True)
        except Exception as error:
            _raise_argument_context(error, "Pydt.normalize", "arguments", None)

    def to_datetime(self, year=None, month=None, day=None, hour=None, minute=None,
                    second=None, microsecond=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_adjust(self, year, month, day, hour, minute, second, microsecond)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_datetime", "arguments", None)

    def to_date(self, year=None, month=None, day=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_adjust(self, year, month, day)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_date", "arguments", None)

    def to_time(self, hour=None, minute=None, second=None, microsecond=None):
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
        (12, 0)
        """
        try:
            return _pydt_adjust(self, None, None, None, hour, minute, second, microsecond)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_time", "arguments", None)

    def to_first_of(self, unit):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_boundary(self, unit, False, False)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_first_of", "arguments", None)

    def is_first_of(self, unit):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_is_boundary(self, unit, False, False)
        except Exception as error:
            _raise_argument_context(error, "Pydt.is_first_of", "arguments", None)

    def to_last_of(self, unit):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_boundary(self, unit, True, False)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_last_of", "arguments", None)

    def is_last_of(self, unit):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_is_boundary(self, unit, True, False)
        except Exception as error:
            _raise_argument_context(error, "Pydt.is_last_of", "arguments", None)

    def to_start_of(self, unit):
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
        """
        try:
            return _pydt_boundary(self, unit, False, True)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_start_of", "arguments", None)

    def is_start_of(self, unit):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_is_boundary(self, unit, False, True)
        except Exception as error:
            _raise_argument_context(error, "Pydt.is_start_of", "arguments", None)

    def to_end_of(self, unit):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_boundary(self, unit, True, True)
        except Exception as error:
            _raise_argument_context(error, "Pydt.to_end_of", "arguments", None)

    def is_end_of(self, unit):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_is_boundary(self, unit, True, True)
        except Exception as error:
            _raise_argument_context(error, "Pydt.is_end_of", "arguments", None)

    def round(self, freq):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_round(self, freq, 0)
        except Exception as error:
            _raise_argument_context(error, "Pydt.round", "arguments", None)

    def ceil(self, freq):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_round(self, freq, 1)
        except Exception as error:
            _raise_argument_context(error, "Pydt.ceil", "arguments", None)

    def floor(self, freq):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_round(self, freq, 2)
        except Exception as error:
            _raise_argument_context(error, "Pydt.floor", "arguments", None)

    def snap(self, unit="s"):
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
        1
        """
        try:
            return _pydt_snap(self, unit)
        except Exception as error:
            _raise_argument_context(error, "Pydt.snap", "unit", unit)

    def fsp(self, precision):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            return _pydt_fsp(self, precision)
        except Exception as error:
            _raise_argument_context(error, "Pydt.fsp", "arguments", None)

    @property
    def tz_available(self):
        """Set of timezone keys available to the system's ZoneInfo database.

        Returns
        -------
        set[str]
            Set of timezone keys available to the system's ZoneInfo database.
        """
        try:
            return available_timezones()
        except Exception as error:
            _raise_argument_context(error, "Pydt.tz_available", "arguments", None)

    @property
    def tz(self):
        """Timezone attached to this value; an alias of tzinfo.

        Returns
        -------
        datetime.tzinfo | None
            The value described above, in the stated type and units; None represents an
            absent optional field or offset where indicated.
        """
        try:
            return _pydt_stored_timezone(self)
        except Exception as error:
            _raise_argument_context(error, "Pydt.tz", "arguments", None)

    def is_local(self):
        """Return whether this value uses the cached process-local timezone.

        Returns
        -------
        bool
            Whether the stated condition holds. A legitimate nonmatch returns False;
            invalid inputs raise the documented error.
        """
        try:
            return _pydt_is_local(self, _local_timezone)
        except Exception as error:
            _raise_argument_context(error, "Pydt.is_local", "arguments", None)

    def is_utc(self):
        """Return whether this value uses datetime.timezone.utc.

        Returns
        -------
        bool
            Whether the stated condition holds. A legitimate nonmatch returns False;
            invalid inputs raise the documented error.
        """
        try:
            return _pydt_is_utc(self)
        except Exception as error:
            _raise_argument_context(error, "Pydt.is_utc", "arguments", None)

    def is_dst(self):
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
        True
        """
        try:
            return _pydt_is_dst(self)
        except Exception as error:
            _raise_argument_context(error, "Pydt.is_dst", "arguments", None)

    def utcoffset_seconds(self):
        """Return the UTC offset in whole seconds, or None for a naive value.

        Returns
        -------
        int | None
            The value described above, in the stated type and units; None represents an
            absent optional field or offset where indicated.
        """
        try:
            return _pydt_offset_seconds(self)
        except Exception as error:
            _raise_argument_context(error, "Pydt.utcoffset_seconds", "arguments", None)

    def astimezone(self, tz=None):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            target = _local_timezone() if tz is None else _timezone(tz)
            result = _pydt_convert(self, target, astimezone=True)
            if result is not None:
                return result
            # A stored zone with offset=None is just as naive as no zone.
            # Resolve strict local wall time once, then use the same native core.
            local = Pydt.fromdatetime.__func__(type(self), self, _local_timezone())
            result = _pydt_convert(local, target, astimezone=True)
            if result is None:
                raise _own_error(ValueError("local timezone has no usable UTC offset"))
            return result
        except Exception as error:
            _raise_argument_context(error, "Pydt.astimezone", "arguments", None)

    def tz_localize(self, tz):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            if tz is None:
                return self if _pydt_stored_timezone(self) is None else datetime.replace(self, tzinfo=None)
            zone = _timezone(tz)
            try:
                offset = datetime.utcoffset(self)
            except Exception as error:
                raise _external_error(error)
            if offset is not None:
                raise _own_error(ValueError("value is already timezone-aware; use tz_convert()"))
            return _pydt_normalize(datetime.replace(self, tzinfo=zone))
        except Exception as error:
            _raise_argument_context(error, "Pydt.tz_localize", "arguments", None)

    def tz_convert(self, tz):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            try:
                offset = datetime.utcoffset(self)
            except Exception as error:
                raise _external_error(error)
            if offset is None:
                raise _own_error(ValueError("value is timezone-naive; use tz_localize() first"))
            zone = _timezone(tz)
            target = timezone.utc if zone is None else zone
            result = _pydt_convert(self, target, offset, zone is None)
            if result is not None:
                return result
            result = Pydt.astimezone(self, target)
            return datetime.replace(result, tzinfo=None) if zone is None else result
        except Exception as error:
            _raise_argument_context(error, "Pydt.tz_convert", "arguments", None)

    def tz_switch(self, targ_tz, base_tz=None, naive=False):
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            if type(naive) is not bool:
                naive = _boolean(naive, "Pydt.tz_switch", "naive")
            if targ_tz is None:
                return self if _pydt_stored_timezone(self) is None else datetime.replace(self, tzinfo=None)
            target = _timezone(targ_tz, "targ_tz")
            value = self
            try:
                offset = datetime.utcoffset(self)
            except Exception as error:
                raise _external_error(error)
            if offset is None:
                base = _timezone(base_tz, "base_tz")
                if base is None:
                    raise _own_error(ValueError("a naive value requires base_tz before timezone conversion"))
                value = self.tz_localize(base)
                result = Pydt.astimezone(value, target)
            else:
                result = _pydt_convert(value, target, offset)
                if result is None:
                    result = Pydt.astimezone(value, target)
            return datetime.replace(result, tzinfo=None) if naive else result
        except Exception as error:
            _raise_argument_context(error, "Pydt.tz_switch", "arguments", None)

    def add(self, years=0, quarters=0, months=0, weeks=0, days=0, hours=0,
            minutes=0, seconds=0, milliseconds=0, microseconds=0):
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
        None is not accepted. Use Delta for fractional fixed durations.
        """
        try:
            return _pydt_add(self, False, years, quarters, months, weeks, days, hours,
                             minutes, seconds, milliseconds, microseconds)
        except Exception as error:
            _raise_argument_context(error, "Pydt.add", "arguments", None)

    def sub(self, years=0, quarters=0, months=0, weeks=0, days=0, hours=0,
            minutes=0, seconds=0, milliseconds=0, microseconds=0):
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
        None is not accepted. Use Delta for fractional fixed durations.
        """
        try:
            return _pydt_add(self, True, years, quarters, months, weeks, days, hours,
                             minutes, seconds, milliseconds, microseconds)
        except Exception as error:
            _raise_argument_context(error, "Pydt.sub", "arguments", None)

    def diff(self, dtobj, unit, absolute=False, inclusive="one"):
        """Count unit boundaries between this value and a supported date input.

        Parameters
        ----------
        dtobj : object
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
            An integer conversion or result exceeds the supported range.
        """
        try:
            try:
                value = dtobj if type(dtobj) is datetime else _parse(dtobj, ignoretz=False)
            except Exception as error:
                _raise_argument_context(error, "Pydt.diff", "dtobj", dtobj)
            return _pydt_diff(self, value, unit, absolute if type(absolute) is bool else _boolean(absolute, "Pydt.diff", "absolute"), inclusive)
        except Exception as error:
            _raise_argument_context(error, "Pydt.diff", "arguments", None)

    def __add__(self, other):
        """Add a supported elapsed duration or calendar adjustment.

        Parameters
        ----------
        other : timedelta, Delta, or relativedelta
            Elapsed duration or calendar adjustment. Existing Python datetime
            arithmetic and genuine external operator overrides are preserved.

        Returns
        -------
        Pydt or NotImplemented
            The resulting date, retaining this date class, or NotImplemented
            when Python must negotiate an unsupported operand.

        Examples
        --------
        >>> (Pydt(2024, 1, 1) + timedelta(days=1)).day
        2
        """
        try:
            return _pydt_binary(self, other, False)
        except Exception as error:
            _raise_argument_context(error, "Pydt.__add__", "arguments", None)

    def __radd__(self, other):
        """Add a supported duration on the left, retaining this date class.

        Parameters
        ----------
        other : timedelta, Delta, or relativedelta
            Duration or calendar adjustment to apply.

        Returns
        -------
        Pydt
            The adjusted date, with this instance's class.
        """
        try:
            return _pydt_binary(self, other, False)
        except Exception as error:
            _raise_argument_context(error, "Pydt.__radd__", "arguments", None)

    def __sub__(self, other):
        """Subtract a date, elapsed duration, or calendar adjustment.

        Parameters
        ----------
        other : datetime, timedelta, Delta, or relativedelta
            A date produces a standard timedelta using the existing datetime
            subtraction rules. A duration or calendar adjustment produces a
            date. Genuine external arithmetic and original exceptions remain.

        Returns
        -------
        timedelta, Pydt, or NotImplemented
            The date difference, adjusted date with this class, or the normal
            Python negotiation marker for an unsupported operand.

        Examples
        --------
        >>> (Pydt(2024, 1, 2) - Pydt(2024, 1, 1)).days
        1
        """
        try:
            return _pydt_binary(self, other, True)
        except Exception as error:
            _raise_argument_context(error, "Pydt.__sub__", "arguments", None)

    def is_past(self) -> bool:
        """Return whether this value is before the current instant.

        Values with a UTC offset are compared as real instants, including repeated
        local times during a clock change. Values with no effective UTC offset
        use the local naive clock. A value equal to now returns False.

        Returns
        -------
        bool
            True if this value is strictly before now; otherwise False.
        """
        try:
            return _pydt_compare_now(self, datetime.now, False)
        except Exception as error:
            _raise_argument_context(error, "Pydt.is_past", "arguments", None)

    def is_future(self) -> bool:
        """Return whether this value is after the current instant.

        Values with a UTC offset are compared as real instants, including repeated
        local times during a clock change. Values with no effective UTC offset
        use the local naive clock. A value equal to now returns False.

        Returns
        -------
        bool
            True if this value is strictly after now; otherwise False.
        """
        try:
            return _pydt_compare_now(self, datetime.now, True)
        except Exception as error:
            _raise_argument_context(error, "Pydt.is_future", "arguments", None)

    def __repr__(self):
        """Return this class name and its date, clock, timezone and fold fields.

        Returns
        -------
        str
            A diagnostic representation; timezone representation uses the
            timezone object's own protocol and preserves its exceptions.
        """
        try:
            values = _pydt_repr_fields(self)
            zone = _pydt_stored_timezone(self)
            if zone is not None:
                try:
                    values += f", tzinfo={zone!r}"
                except Exception as error:
                    raise _external_error(error)
            if datetime.fold.__get__(self):
                values += ", fold=1"
            return f"{type(self).__name__}({values})"
        except Exception as error:
            _raise_argument_context(error, "Pydt.__repr__", "arguments", None)

    def strftime(self, format: str) -> str:
        """Format with system directives and exact ``%f``/``%.0f``–``%.9f``.

        ``%f`` uses six digits. Explicit dot precision truncates or pads the
        stored microsecond value; ``%.0f`` emits nothing. Other system rules
        and real subclass ``__format__``/``strftime`` dispatch stay intact.

        Parameters
        ----------
        format : str
            System format, including an empty string. ``%.1f`` through
            ``%.9f`` emit a decimal dot and that many fraction digits.

        Returns
        -------
        str
            Formatted text. Pydt has microsecond precision, so digits beyond
            six are zero padding; this does not invent measured nanoseconds.

        Raises
        ------
        TypeError
            The format is not text.
        ValueError
            An explicit fractional format is invalid, or the platform rejects
            another system directive. Actual external exceptions propagate.

        Examples
        --------
        >>> Pydt(2024, 1, 1, microsecond=123456).strftime("%f|%.3f|%.9f|%.0f")
        '123456|.123|.123456000|'
        """
        try:
            return _pydt_strftime(self, format)
        except Exception as error:
            _raise_argument_context(error, "Pydt.strftime", "format", format)

    def __format__(self, fmt):
        """Format this date with an empty or strftime-style specification.

        Parameters
        ----------
        fmt : str
            Empty selects isoformat with a space separator; otherwise the
            specification is passed to this instance's strftime method.

        Returns
        -------
        str
            The formatted date and time.

        Raises
        ------
        TypeError
            The specification is not a real string or string subclass.
        """
        try:
            if not issubclass(type(fmt), str):
                raise _own_error(TypeError("must be str"), "fmt", fmt)
            try:
                return self.isoformat(" ") if fmt == "" else self.strftime(fmt)
            except Exception as error:
                raise _external_error(error)
        except Exception as error:
            _raise_argument_context(error, "Pydt.__format__", "fmt", fmt)

    def __reduce_ex__(self, protocol):
        """Save date fields separately from independent instance metadata.

        Loading restores a new immutable value. Only load pickle data that you
        trust. Old Cython Pydt pickle formats are not supported.
        """
        try:
            try:
                _index(protocol)
            except Exception as error:
                raise _external_error(error)
            return _pydt_reduce(self, _restore_pydt, True)
        except Exception as error:
            _raise_argument_context(error, "Pydt.__reduce_ex__", "protocol", protocol)

    def __reduce__(self):
        """Return the versioned pickle representation."""
        try:
            return _pydt_reduce(self, _restore_pydt, False)
        except Exception as error:
            _raise_argument_context(error, "Pydt.__reduce__", "arguments", None)

    def __setstate__(self, state: dict[str, object] | tuple[dict[str, object] | None, dict[str, object] | None] | None) -> None:
        """Restore extra dictionary and slot attributes without changing date fields.

        Accept None, a string-keyed dictionary, or a (dictionary, slots) pair
        containing dictionaries or None. Entries are fixed before user setters
        run; existing dictionary attributes are updated. Returns None.
        """
        try:
            if state is None:
                return
            if type(state) is tuple and len(state) == 2:
                dictionary, slots = state
            else:
                dictionary, slots = state, None
            for value in (dictionary, slots):
                if value is not None and (type(value) is not dict or any(type(k) is not str for k in value)):
                    raise _own_error(TypeError("must contain dictionaries with string keys"), "state", state)
            # A user setter (or __dict__ lookup) may mutate the supplied state.
            # Fix the entries before invoking either hook, as with Delta restore.
            slot_items = tuple(slots.items()) if slots is not None else ()
            dictionary_items = tuple(dictionary.items()) if dictionary is not None else ()
            if dictionary is not None:
                try:
                    self.__dict__.update(dictionary_items)
                except Exception as error:
                    raise _location_error(_external_error(error), "", "state dictionary assignment")
            for name, value in slot_items:
                try:
                    setattr(self, name, value)
                except Exception as error:
                    if _critical(error):
                        raise
                    # A slot name is an exact validated str; no user display hook runs.
                    raise _location_error(_external_error(error), "", "state slot " + _preview(name))
        except Exception as error:
            _raise_argument_context(error, "Pydt.__setstate__", "arguments", None)


_pydt_register(Pydt, _timezone)
