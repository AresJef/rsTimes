"""Type hints for rstimes.delta; executable behavior is supplied by Rust."""

from datetime import date, datetime, timedelta
from typing import Iterable, SupportsInt, TypeVar, overload
import numpy as np
from dateutil.relativedelta import relativedelta

_DateT = TypeVar("_DateT", bound=date)
_DeltaT = TypeVar("_DeltaT", bound="Delta")
_State = tuple[str, int, tuple[int, ...], int, dict[str, object] | None]

class Delta:
    """Typed interface to the native relative/absolute calendar Delta.

    Constructor order and return types match the actual Python interface.
    Complete argument, error and usage documentation lives on the native class.
    Field properties are read-only; unset absolute fields return None.
    """
    def __new__(
        cls: type[_DeltaT], years: SupportsInt = 0, quarters: SupportsInt = 0, months: SupportsInt = 0,
        weeks: SupportsInt | float = 0, days: SupportsInt | float = 0, hours: SupportsInt | float = 0,
        minutes: SupportsInt | float = 0, seconds: SupportsInt | float = 0, milliseconds: SupportsInt | float | float = 0,
        microseconds: SupportsInt | float | float = 0, year: SupportsInt = -1, month: SupportsInt = -1,
        day: SupportsInt = -1, weekday: SupportsInt = -1, hour: SupportsInt = -1,
        minute: SupportsInt = -1, second: SupportsInt = -1, millisecond: SupportsInt = -1,
        microsecond: SupportsInt = -1,
    ) -> _DeltaT:
        """Create a Delta value; see Delta for complete parameter descriptions."""
        ...
    def __init__(self, *args: object, **kwargs: object) -> None:
        """Leave the already constructed Delta value unchanged."""
        ...
    @classmethod
    def from_relativedelta(cls, rd: relativedelta) -> Delta:
        """Create a Delta from supported relativedelta fields.
        
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
        1"""
        ...
    def to_timedelta(self, start: date | datetime | None = None) -> timedelta:
        """Convert this Delta to an exact standard-library time span.
        
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
        datetime.timedelta(days=29)"""
        ...
    def apply_many(self, values: Iterable[object]) -> list[object]:
        """Add this Delta to each value and return the results in order.
        
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
        [datetime.date(2024, 1, 2), datetime.date(2024, 1, 3)]"""
        ...
    @property
    def years(self) -> int:
        """int: Normalized relative years; months are carried into this value."""
        ...
    @property
    def months(self) -> int:
        """int: Relative months after grouping years, in 0..11."""
        ...
    @property
    def days(self) -> int:
        """int: Relative days, including normalized weeks and clock carries."""
        ...
    @property
    def hours(self) -> int:
        """int: Normalized relative hours, in 0..23."""
        ...
    @property
    def minutes(self) -> int:
        """int: Normalized relative minutes, in 0..59."""
        ...
    @property
    def seconds(self) -> int:
        """int: Normalized relative seconds, in 0..59."""
        ...
    @property
    def microseconds(self) -> int:
        """int: Normalized relative microseconds, in 0..999999."""
        ...
    @property
    def year(self) -> int | None:
        """int | None: Absolute year replacement, or None when unset."""
        ...
    @property
    def month(self) -> int | None:
        """int | None: Absolute month replacement (1..12), or None when unset."""
        ...
    @property
    def day(self) -> int | None:
        """int | None: Absolute day replacement (1..31), or None when unset."""
        ...
    @property
    def weekday(self) -> int | None:
        """int | None: Absolute weekday replacement (Monday=0 to Sunday=6), or None."""
        ...
    @property
    def hour(self) -> int | None:
        """int | None: Absolute hour replacement (0..23), or None when unset."""
        ...
    @property
    def minute(self) -> int | None:
        """int | None: Absolute minute replacement (0..59), or None when unset."""
        ...
    @property
    def second(self) -> int | None:
        """int | None: Absolute second replacement (0..59), or None when unset."""
        ...
    @property
    def microsecond(self) -> int | None:
        """int | None: Absolute microsecond replacement (0..999999), or None."""
        ...
    @overload
    def __add__(self, o: _DateT, /) -> _DateT:
        """Add a Delta, timedelta, relativedelta, date/datetime or NumPy scalar.
        
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
        datetime timezone and fold are preserved. Arrays are not supported."""
        ...
    @overload
    def __add__(self, o: timedelta | Delta | relativedelta | np.timedelta64, /) -> Delta:
        """Add a Delta, timedelta, relativedelta, date/datetime or NumPy scalar.
        
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
        datetime timezone and fold are preserved. Arrays are not supported."""
        ...
    @overload
    def __add__(self, o: np.datetime64, /) -> datetime:
        """Add a Delta, timedelta, relativedelta, date/datetime or NumPy scalar.
        
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
        datetime timezone and fold are preserved. Arrays are not supported."""
        ...
    @overload
    def __radd__(self, o: _DateT, /) -> _DateT:
        """Apply reflected addition using the same date and duration rules as __add__.
        
        Parameters
        ----------
        other : object
            Left-hand date, duration or relativedelta operand.
        
        A direct reflected call with another Delta returns NotImplemented. Conversion,
        calendar and custom-constructor errors follow __add__."""
        ...
    @overload
    def __radd__(self, o: timedelta | relativedelta | np.timedelta64, /) -> Delta:
        """Apply reflected addition using the same date and duration rules as __add__.
        
        Parameters
        ----------
        other : object
            Left-hand date, duration or relativedelta operand.
        
        A direct reflected call with another Delta returns NotImplemented. Conversion,
        calendar and custom-constructor errors follow __add__."""
        ...
    @overload
    def __radd__(self, o: np.datetime64, /) -> datetime:
        """Apply reflected addition using the same date and duration rules as __add__.
        
        Parameters
        ----------
        other : object
            Left-hand date, duration or relativedelta operand.
        
        A direct reflected call with another Delta returns NotImplemented. Conversion,
        calendar and custom-constructor errors follow __add__."""
        ...
    def __sub__(self, o: timedelta | Delta | relativedelta | np.timedelta64, /) -> Delta:
        """Subtract Delta, timedelta, relativedelta or NumPy timedelta64 from this Delta.
        
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
            Third-party conversion and Python callback errors propagate."""
        ...
    @overload
    def __rsub__(self, o: _DateT, /) -> _DateT:
        """Subtract this Delta from a date/datetime, timedelta or supported NumPy scalar.
        
        Parameters
        ----------
        other : object
            Left-hand date, duration or relativedelta operand.
        
        relativedelta is also supported; direct reflected Delta calls return
        NotImplemented. Return types and calendar errors follow reflected dispatch,
        with OverflowError for unrepresentable negation or subtraction."""
        ...
    @overload
    def __rsub__(self, o: timedelta | relativedelta | np.timedelta64, /) -> Delta:
        """Subtract this Delta from a date/datetime, timedelta or supported NumPy scalar.
        
        Parameters
        ----------
        other : object
            Left-hand date, duration or relativedelta operand.
        
        relativedelta is also supported; direct reflected Delta calls return
        NotImplemented. Return types and calendar errors follow reflected dispatch,
        with OverflowError for unrepresentable negation or subtraction."""
        ...
    @overload
    def __rsub__(self, o: np.datetime64, /) -> datetime:
        """Subtract this Delta from a date/datetime, timedelta or supported NumPy scalar.
        
        Parameters
        ----------
        other : object
            Left-hand date, duration or relativedelta operand.
        
        relativedelta is also supported; direct reflected Delta calls return
        NotImplemented. Return types and calendar errors follow reflected dispatch,
        with OverflowError for unrepresentable negation or subtraction."""
        ...
    def __neg__(self) -> Delta:
        """Negate relative components and retain absolute replacements in a new Delta.
        
        Raises
        ------
        OverflowError
            A relative component cannot be negated or normalized."""
        ...
    def __abs__(self) -> Delta:
        """Return a new Delta with the frozen grouped-sign absolute-value behavior.
        
        Year/month and day/time groups use their leading normalized component's sign;
        absolute replacement fields are retained.
        
        Raises
        ------
        OverflowError
            Required negation or normalization cannot be represented."""
        ...
    def __eq__(self, o: object, /) -> bool:
        """Compare the values of two Delta objects.
        
        Returns
        -------
        bool or NotImplemented
            Whether all relative and absolute fields match. Other object types
            return NotImplemented and follow Python's reflected comparison rules.
        
        Notes
        -----
        Delta subclasses that inherit this comparison use the same value rules.
        Equal Delta values have equal hashes and can share dictionary keys."""
        ...
    def __ne__(self, o: object, /) -> bool:
        """Compare two Delta values for inequality.
        
        Returns
        -------
        bool or NotImplemented
            The opposite of field equality for Delta objects. Other types return
            NotImplemented without converting the operand."""
        ...
    def __bool__(self) -> bool:
        """Return whether a relative field is nonzero or an absolute field is set.
        
        Explicit absolute zero is set and therefore makes a Delta truthy."""
        ...
    def __repr__(self) -> str:
        """Return the runtime class name and set fields in the frozen display order.
        
        Zero relative fields and unset absolute fields are omitted; weekdays use MO
        through SU. __str__ resolves to the same representation."""
        ...
    def __hash__(self) -> int:
        """Return a stable hash based on the Delta value.
        
        Returns
        -------
        int
            Equal Delta values have equal hashes.
        
        Notes
        -----
        Additional subclass attributes do not change the Delta value or its hash."""
        ...
    def __getstate__(self) -> _State:
        """Return the saved fields and additional attributes used by this package.
        
        Returns
        -------
        tuple
            State used by the package's save/restore support.
        
        Notes
        -----
        Use pickle or copy for ordinary saving and copying."""
        ...
    def __setstate__(self, state: object) -> None:
        """Restore saved extra attributes while keeping this Delta value.
        
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
        trusted sources. Errors from subclass attribute handling are passed through."""
        ...
    def __reduce__(self) -> tuple[object, ...]:
        """Return the reconstruction recipe used by pickle.
        
        Returns
        -------
        tuple
            The same recipe as __reduce_ex__.
        
        Notes
        -----
        Only load pickle data from trusted sources."""
        ...
    def __reduce_ex__(self, protocol: int, /) -> tuple[object, ...]:
        """Return the recipe used by pickle to save this Delta.
        
        Parameters
        ----------
        protocol : int
            The protocol selected by pickle.
        
        Returns
        -------
        tuple
            A reconstruction recipe that preserves the value and additional attributes.
        
        Notes
        -----
        Only load pickle data from trusted sources."""
        ...
    def __copy__(self: _DeltaT) -> _DeltaT:
        """Return a separate object with the same Delta value and type.
        
        Returns
        -------
        Delta
            A shallow copy. Additional attribute values remain shared."""
        ...
    def __deepcopy__(self: _DeltaT, memo: dict[int, object]) -> _DeltaT:
        """Return a distinct deep copy, preserving subtype and tracking cycles.
        
        Parameters
        ----------
        memo : dict
            Python deepcopy's object-identity table, reused for recursion.
        
        Raises
        ------
        Exception
            Allocation, subclass and recursive deepcopy errors propagate."""
        ...
