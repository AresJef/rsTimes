"""Typed native Pldt columns and registered Polars namespaces.

Dynamic pl.Series/pl.Expr namespace discovery remains owned by Polars.
Use Pldt for concrete eager types; no custom expression container exists.

Date text inputs and string defaults accept real str subclasses and read
their native stored content, without calling __str__ or overridden sequence
methods. Call str(value) explicitly when conversion is intended.

Supported string parameters use their actual stored str content before library
cache, membership or name dispatch. Custom string display, hashing and equality
do not reinterpret formats, frequencies, units or timezone names. Genuine
constructor, date/timezone and explicit external protocols keep their contracts.
"""
from __future__ import annotations
from typing import Generic, TypeVar
from types import NotImplementedType
import numpy as np
import polars as pl
import pandas as pd
from pandas.tseries.offsets import Day, Hour, Micro, Milli, Minute, Nano, Second
from .delta import Delta
from .parser import Configs
from typing import Any, Literal, SupportsIndex, SupportsFloat, Self, TypeAlias, overload
from collections.abc import Iterable
from types import NotImplementedType
import datetime as _dt

_Unit: TypeAlias = Literal["ms", "us", "ns"]
_FixedFrequency: TypeAlias = str | _dt.timedelta | Nano | Micro | Milli | Second | Minute | Hour | Day
_Boolean: TypeAlias = bool | np.bool_
_Zone: TypeAlias = str | _dt.tzinfo | None
_DateValue: TypeAlias = str | _dt.date | np.datetime64 | SupportsIndex | float | np.float16 | np.float32 | np.float64 | None
_DateCollection: TypeAlias = Iterable[_DateValue] | np.ndarray | pl.Series
_DateInput: TypeAlias = _DateValue | _DateCollection
_DiffValue: TypeAlias = str | _dt.date | np.datetime64 | SupportsIndex | float
_DiffInput: TypeAlias = _DiffValue | Iterable[_DiffValue] | np.ndarray | pl.Series
_IntegerInput: TypeAlias = SupportsIndex | Iterable[SupportsIndex] | np.ndarray | pl.Series
_CalendarInput: TypeAlias = SupportsIndex | None | Iterable[SupportsIndex | None] | np.ndarray | pl.Series
_OptionalField: TypeAlias = SupportsIndex | None | Iterable[SupportsIndex | None] | np.ndarray | pl.Series
_Selection: TypeAlias = SupportsIndex | str | None | Iterable[SupportsIndex | str | None] | np.ndarray | pl.Series
_QuerySelection: TypeAlias = SupportsIndex | str | Iterable[SupportsIndex | str] | np.ndarray | pl.Series
_ExprIntegerInput: TypeAlias = _IntegerInput | pl.Expr
_ExprCalendarInput: TypeAlias = _CalendarInput | pl.Expr
_ExprOptionalField: TypeAlias = _OptionalField | pl.Expr
_ExprSelection: TypeAlias = _Selection | pl.Expr
_ExprQuerySelection: TypeAlias = _QuerySelection | pl.Expr
_NumericInput: TypeAlias = SupportsIndex | SupportsFloat | None | Iterable[SupportsIndex | SupportsFloat | None] | np.ndarray | pl.Series
_ActualDateInput: TypeAlias = _dt.date | None | Iterable[_dt.date | None] | np.ndarray | pl.Series
_DatetimeInput: TypeAlias = _dt.datetime | None | Iterable[_dt.datetime | None] | np.ndarray | pl.Series
_NumpyDateInput: TypeAlias = np.datetime64 | None | Iterable[np.datetime64 | None] | np.ndarray
_IsoInput: TypeAlias = str | None | Iterable[str | None] | np.ndarray | pl.Series
_CombineTime: TypeAlias = _dt.time | _DateInput | Iterable[_dt.time]
_BooleanMask: TypeAlias = Iterable[_Boolean] | np.ndarray | pl.Series
_Ambiguous: TypeAlias = Literal["raise", "NaT", "infer"] | _Boolean | _BooleanMask
_ExprAmbiguous: TypeAlias = _Ambiguous | pl.Expr
_Nonexistent: TypeAlias = Literal["raise", "NaT", "shift_forward", "shift_backward"] | _dt.timedelta
_DeltaInput: TypeAlias = Delta | Iterable[Delta] | np.ndarray | pl.Series

_PldtT = TypeVar("_PldtT", bound="Pldt")

class Pldt(pl.Series):
    """A Polars Series of dates with calendar operations and nanosecond support.

    Examples
    --------
    >>> import polars as pl
    >>> from rstimes import Pldt
    >>> x = Pldt(["1970-01-01T00:00:00.000000001", None], name="time")
    >>> x.dtype == pl.Datetime("ns")
    True
    >>> x.to_physical().to_list()
    [1, None]
    >>> expr = pl.col("time").pldt.add(nanoseconds=1)
    >>> isinstance(expr, pl.Expr)
    True
    >>> pl.DataFrame({"time": x}).lazy().select(expr).collect()["time"].to_physical().to_list()
    [2, None]

    Parameters
    ----------
    data : one-dimensional date collection
        Text, actual date/datetime/NumPy scalar values, ticks or supported native
        columns. A bare scalar belongs in [value] or a named scalar factory with
        size. Mapping/set/table/nested/two-dimensional sources are rejected.
    unit : {"ms", "us", "ns"} or None
        Initial source-driven resolution. Text selects its actual declared fraction;
        numeric ticks default to ns; native dates retain a supported unit. Empty or
        untyped missing-only data defaults to ms. Explicit construction is lossless.
    name : str or None
        Column name; None retains a usable source name.
    copy : bool or numpy.bool_, default False
        True isolates native data. False allows safe sharing, but known externally
        writable storage may require an owned result before detached execution.
    default : independently complete date-like value or None
        Fill missing text YMD fields/two-digit-year reference when needed. Never
        supply clock, timezone, nanosecond or fold for the column.
    yearfirst, dayfirst : bool, numpy.bool_ or None
        Explicit non-None > Configs > True/False. False is an explicit setting.
    isoformat, strict : bool or numpy.bool_
        ISO-first with ordinary fallback, and explicit-field validation. These are
        not timezone policies or a request to replace parse failures with null.
    cfg : Configs or None
        Shared parser rules and explicitly configured source region names.
    tz : str, datetime.tzinfo or None
        Target zone. Named regions and representable whole-hour fixed offsets use
        native single-zone metadata. UTC normalizes; no hidden source-object table.
    ambiguous, nonexistent : policy
        Full approved localization policies. Already-known instants do not need
        another ambiguity choice; naive/UTC/fixed-offset paths avoid region work.

    Returns
    -------
    Pldt
        Independent Series shell with native Datetime(ms/us/ns) data and a separate
        validity bitmap. Valid int64 MIN is a real date, not null.

    Notes
    -----
    Existing date operations keep their unit and fail on precision/capacity loss;
    use as_unit explicitly. Scalar arguments broadcast, collections must match the
    source length, and length-one collections do not act as scalars. Null query
    results follow their actual result role. Numeric inputs reject booleans.

    Native replace/round/diff keep Polars meanings. Date field replacement, date
    round/ceil/floor and boundary-count diff use .pldt. Expressions remain ordinary
    pl.Expr and execute in the native plugin, without a Python row callback.
    """
    def to_datetime(self, year: _OptionalField=None, month: _OptionalField=None, day: _OptionalField=None, hour: _OptionalField=None, minute: _OptionalField=None, second: _OptionalField=None, microsecond: _OptionalField=None, nanosecond: _OptionalField=None) -> Self:
        """Set selected date and clock fields, fitting the day to the final month.

        Parameters
        ----------
        year : integer or one-dimensional integer collection or None
            Set the calendar year when supplied. Zero, negative and wide years depend on the
            date unit and chosen timezone.
        month : integer or one-dimensional integer collection or None
            Set the month using 1 through 12. None keeps the current month.
        day : integer or one-dimensional integer collection or None
            Set the day of the month using 1 through 31. None keeps the current day.
        hour : integer or one-dimensional integer collection or None
            Set the local hour using 0 through 23. None keeps the current hour.
        minute : integer or one-dimensional integer collection or None
            Set the local minute using 0 through 59. None keeps the current minute.
        second : integer or one-dimensional integer collection or None
            Set the local second using 0 through 59. None keeps the current second.
        microsecond : integer or one-dimensional integer collection or None
            Set the microsecond field using 0 through 999999. None keeps it. A supplied
            microsecond clears the previous nanosecond tail unless you supply nanosecond as
            well.
        nanosecond : integer or one-dimensional integer collection or None
            Set the additional nanosecond tail using 0 through 999. None keeps the tail unless
            microsecond is set.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        None keeps an optional field. An explicit zero sets a clock field to zero.
        A calendar day up to 31 is fitted to the final month's length.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-calendar.html#reader-pldt-month-and-fields
        """
        ...

    def to_date(self, year: _OptionalField=None, month: _OptionalField=None, day: _OptionalField=None) -> Self:
        """Set selected calendar fields and keep the time of day.

        Parameters
        ----------
        year : integer or one-dimensional integer collection or None
            Set the calendar year when supplied. Zero, negative and wide years depend on the
            date unit and chosen timezone.
        month : integer or one-dimensional integer collection or None
            Set the month using 1 through 12. None keeps the current month.
        day : integer or one-dimensional integer collection or None
            Set the day of the month using 1 through 31. None keeps the current day.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        None keeps an optional field. An explicit zero sets a clock field to zero.
        A calendar day up to 31 is fitted to the final month's length.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_time(self, hour: _OptionalField=None, minute: _OptionalField=None, second: _OptionalField=None, microsecond: _OptionalField=None, nanosecond: _OptionalField=None) -> Self:
        """Set selected clock fields and keep the calendar date.

        Parameters
        ----------
        hour : integer or one-dimensional integer collection or None
            Set the local hour using 0 through 23. None keeps the current hour.
        minute : integer or one-dimensional integer collection or None
            Set the local minute using 0 through 59. None keeps the current minute.
        second : integer or one-dimensional integer collection or None
            Set the local second using 0 through 59. None keeps the current second.
        microsecond : integer or one-dimensional integer collection or None
            Set the microsecond field using 0 through 999999. None keeps it. A supplied
            microsecond clears the previous nanosecond tail unless you supply nanosecond as
            well.
        nanosecond : integer or one-dimensional integer collection or None
            Set the additional nanosecond tail using 0 through 999. None keeps the tail unless
            microsecond is set.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        None keeps an optional field. An explicit zero sets a clock field to zero.
        The original calendar date stays in place.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_year(self, offset: _IntegerInput, month: _Selection=None, day: _OptionalField=None) -> Self:
        """Move by calendar years and optionally choose a month and day.

        Parameters
        ----------
        offset : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        month : integer, name or one-dimensional collection or None
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_quarter(self, offset: _IntegerInput, month: _OptionalField=None, day: _OptionalField=None) -> Self:
        """Move by calendar quarters and optionally choose a month within the quarter and a day.

        Parameters
        ----------
        offset : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        month : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_month(self, offset: _IntegerInput, day: _OptionalField=None) -> Self:
        """Move by calendar months, fitting the day to the destination month.

        Parameters
        ----------
        offset : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_weekday(self, offset: _IntegerInput, weekday: _Selection=None) -> Self:
        """Move by calendar weeks and optionally choose a weekday in the destination week.

        Parameters
        ----------
        offset : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weekday : integer, name or one-dimensional collection or None
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_day(self, offset: _IntegerInput) -> Self:
        """Move by calendar days, keeping the time of day.

        Parameters
        ----------
        offset : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Supply an integer offset. Zero keeps the same day and a negative offset moves backward.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_curr_year(self, month: _Selection=None, day: _OptionalField=None) -> Self:
        """Select the current calendar year and optionally choose a month and day.

        Parameters
        ----------
        month : integer, name or one-dimensional collection or None
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_prev_year(self, month: _Selection=None, day: _OptionalField=None) -> Self:
        """Select the previous calendar year and optionally choose a month and day.

        Parameters
        ----------
        month : integer, name or one-dimensional collection or None
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_next_year(self, month: _Selection=None, day: _OptionalField=None) -> Self:
        """Select the next calendar year and optionally choose a month and day.

        Parameters
        ----------
        month : integer, name or one-dimensional collection or None
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_curr_quarter(self, month: _OptionalField=None, day: _OptionalField=None) -> Self:
        """Select the current calendar quarter and optionally choose a month within that quarter and a day.

        Parameters
        ----------
        month : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_prev_quarter(self, month: _OptionalField=None, day: _OptionalField=None) -> Self:
        """Select the previous calendar quarter and optionally choose a month within that quarter and a day.

        Parameters
        ----------
        month : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_next_quarter(self, month: _OptionalField=None, day: _OptionalField=None) -> Self:
        """Select the next calendar quarter and optionally choose a month within that quarter and a day.

        Parameters
        ----------
        month : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_curr_month(self, day: _OptionalField=None) -> Self:
        """Select the current calendar month and fit the day to that month.

        Parameters
        ----------
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_prev_month(self, day: _OptionalField=None) -> Self:
        """Select the previous calendar month and fit the day to that month.

        Parameters
        ----------
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_next_month(self, day: _OptionalField=None) -> Self:
        """Select the next calendar month and fit the day to that month.

        Parameters
        ----------
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-calendar.html#reader-pldt-month-and-fields
        """
        ...

    def to_curr_weekday(self, weekday: _Selection=None) -> Self:
        """Select the current calendar week and optionally choose a weekday.

        Parameters
        ----------
        weekday : integer, name or one-dimensional collection or None
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_prev_weekday(self, weekday: _Selection=None) -> Self:
        """Select the previous calendar week and optionally choose a weekday.

        Parameters
        ----------
        weekday : integer, name or one-dimensional collection or None
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_next_weekday(self, weekday: _Selection=None) -> Self:
        """Select the next calendar week and optionally choose a weekday.

        Parameters
        ----------
        weekday : integer, name or one-dimensional collection or None
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_monday(self) -> Self:
        """Move to Monday of the current calendar week, keeping the time of day.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_tuesday(self) -> Self:
        """Move to Tuesday of the current calendar week, keeping the time of day.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_wednesday(self) -> Self:
        """Move to Wednesday of the current calendar week, keeping the time of day.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_thursday(self) -> Self:
        """Move to Thursday of the current calendar week, keeping the time of day.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_friday(self) -> Self:
        """Move to Friday of the current calendar week, keeping the time of day.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_saturday(self) -> Self:
        """Move to Saturday of the current calendar week, keeping the time of day.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_sunday(self) -> Self:
        """Move to Sunday of the current calendar week, keeping the time of day.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_yesterday(self) -> Self:
        """Move to the previous local calendar day, keeping the time of day.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_tomorrow(self) -> Self:
        """Move to the next local calendar day, keeping the time of day.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def add(self, years: _IntegerInput=0, quarters: _IntegerInput=0, months: _IntegerInput=0, weeks: _IntegerInput=0, days: _IntegerInput=0, hours: _IntegerInput=0, minutes: _IntegerInput=0, seconds: _IntegerInput=0, milliseconds: _IntegerInput=0, microseconds: _IntegerInput=0, nanoseconds: _IntegerInput=0) -> Self:
        """Add calendar months, days and clock increments in that order.

        Parameters
        ----------
        years : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        quarters : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        months : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weeks : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        days : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        hours : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        minutes : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        seconds : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        milliseconds : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        microseconds : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        nanoseconds : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Each increment is an integer. Omitted increments are zero, and negative increments reverse direction. An explicit None is invalid. The combined month change is applied before days and clock increments, with month-end adjustment on the resulting month.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.

        Examples
        --------
        >>> from rstimes import Pldt
        >>> events = Pldt(["2024-01-31 14:30", None])
        >>> print(events.add(months=1).isoformat().to_list())
        ['2024-02-29T14:30:00', None]

        >>> from rstimes import Pldt
        >>> Pldt([1], unit="us").add(microseconds=1, nanoseconds=-1000).to_physical().to_list()
        [1]
        """
        ...

    def sub(self, years: _IntegerInput=0, quarters: _IntegerInput=0, months: _IntegerInput=0, weeks: _IntegerInput=0, days: _IntegerInput=0, hours: _IntegerInput=0, minutes: _IntegerInput=0, seconds: _IntegerInput=0, milliseconds: _IntegerInput=0, microseconds: _IntegerInput=0, nanoseconds: _IntegerInput=0) -> Self:
        """Subtract calendar months, days and clock increments in that order.

        Parameters
        ----------
        years : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        quarters : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        months : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weeks : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        days : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        hours : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        minutes : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        seconds : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        milliseconds : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        microseconds : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        nanoseconds : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Each increment is an integer. Omitted increments are zero, and negative increments reverse direction. An explicit None is invalid. The combined month change is applied before days and clock increments, with month-end adjustment on the resulting month.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_first_of(self, unit: str) -> Self:
        """Move to the first calendar day of the selected period, keeping the time of day.

        The clock and subsecond digits are carried to the selected calendar day. A regional gap can require a valid clock on that day. If the entire selected day is missing, the operation raises an error.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-pldt-month-boundaries
        """
        ...

    def is_first_of(self, unit: str) -> pl.Series:
        """Test whether each date falls on the first calendar day of the selected period.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-pldt-month-boundaries
        """
        ...

    def to_last_of(self, unit: str) -> Self:
        """Move to the last calendar day of the selected period, keeping the time of day.

        The clock and subsecond digits are carried to the selected calendar day. A regional gap can require a valid clock on that day. If the entire selected day is missing, the operation raises an error.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-pldt-month-boundaries
        """
        ...

    def is_last_of(self, unit: str) -> pl.Series:
        """Test whether each date falls on the last calendar day of the selected period.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_start_of(self, unit: str) -> Self:
        """Move to the first valid instant of the selected period.

        Use the first or last valid time in the selected period, at the source precision. For example, a millisecond day ends at 23:59:59.999.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-pldt-month-boundaries
        """
        ...

    def is_start_of(self, unit: str) -> pl.Series:
        """Test whether each time equals the first valid instant of the selected period.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-pldt-month-boundaries
        """
        ...

    def to_end_of(self, unit: str) -> Self:
        """Move to the last valid instant of the selected period in the current unit.

        Use the first or last valid time in the selected period, at the source precision. For example, a millisecond day ends at 23:59:59.999.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-pldt-month-boundaries
        """
        ...

    def is_end_of(self, unit: str) -> pl.Series:
        """Test whether each time equals the last valid instant in the current unit.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def normalize(self) -> Self:
        """Return the real start of this local day, staying within the day.

        Choose the first valid instant of the source's local calendar day.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def snap(self, unit: str='s') -> Self:
        """Select the nearest real period start; equal distances select later.

        Parameters
        ----------
        unit : str
            One natural Y/Q/M/W/D/h/m/min/s/ms/us/ns period or an exact saved month/weekday name; no
            arbitrary multi-step frequency or numeric weekday.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> from rstimes import Pldt
        >>> events = Pldt(["2024-01-02 11:59", "2024-01-02 12:00", None])
        >>> print(events.snap("D").isoformat().to_list())
        ['2024-01-02T00:00:00', '2024-01-03T00:00:00', None]
        """
        ...

    def fsp(self, precision: SupportsIndex) -> Self:
        """Truncate the fractional second, preserving the current storage unit.

        Parameters
        ----------
        precision : SupportsIndex
            Single integer number of fractional-second digits. Negative values fail; 9 or more preserve
            existing precision without inventing finer data.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-pldt-second-grid
        """
        ...

    @property
    def year(self) -> pl.Series:
        """Signed calendar year as a nullable Int64 column.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def month(self) -> pl.Series:
        """One-based month as a nullable Int64 column.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def day(self) -> pl.Series:
        """One-based day as a nullable Int64 column.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def hour(self) -> pl.Series:
        """Hour within the local day as nullable Int64.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def minute(self) -> pl.Series:
        """Minute within the hour as nullable Int64.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def second(self) -> pl.Series:
        """Second within the minute as nullable Int64.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def microsecond(self) -> pl.Series:
        """Microsecond within the second as nullable Int64.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def nanosecond(self) -> pl.Series:
        """Additional nanosecond tail, 0 through 999, as nullable Int64.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    @property
    def weekday(self) -> pl.Series:
        """Weekday with Monday 0, as nullable Int64.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    @property
    def day_of_year(self) -> pl.Series:
        """One-based day within the local calendar year.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def days_in_month(self) -> pl.Series:
        """Number of days in the local calendar month.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def quarter(self) -> pl.Series:
        """One-based calendar quarter as nullable Int64.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def millisecond(self) -> pl.Series:
        """Millisecond within the second, from 0 through 999.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    @property
    def is_leap_year(self) -> pl.Series:
        """Whether the local year is leap; source null is False.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def isoyear(self) -> pl.Series:
        """Signed ISO week year, independently of UInt32 table capacity.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def isoweek(self) -> pl.Series:
        """One-based ISO week number.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def isoweekday(self) -> pl.Series:
        """ISO weekday with Monday 1.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def days_in_year(self) -> pl.Series:
        """Number of days in the local calendar year.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def days_bf_year(self) -> pl.Series:
        """Days before this calendar year, relative to 0001-01-01.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def days_in_quarter(self) -> pl.Series:
        """Number of calendar days in this quarter.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def days_bf_quarter(self) -> pl.Series:
        """Days in this year before the current quarter.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def day_of_quarter(self) -> pl.Series:
        """One-based day in this calendar quarter.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def days_bf_month(self) -> pl.Series:
        """Days in this year before the current month.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def day_of_month(self) -> pl.Series:
        """One-based local day of month.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_year(self, year: _IntegerInput) -> pl.Series:
        """Match scalar or equal-length integer year targets.

        Parameters
        ----------
        year : integer or one-dimensional integer collection
            An integer year or a same-length integer column paired by position. A valid
            integer outside the matching range yields False. Strings, booleans and missing targets are invalid.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Supply a valid target. A missing target, including None, raises TypeError.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        A missing source date returns False in the Boolean result.
        """
        ...

    def is_quarter(self, quarter: _IntegerInput) -> pl.Series:
        """Match scalar or equal-length integer quarter targets.

        Parameters
        ----------
        quarter : integer or one-dimensional integer collection
            Required scalar or equal-length integer quarter target. Legal nonmatches return False; missing
            targets fail even for source null.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def is_month(self, month: _QuerySelection) -> pl.Series:
        """Match integer or saved month names, by position; null is False.

        Parameters
        ----------
        month : integer, name or one-dimensional collection
            Month number or a month name in the library's default vocabulary.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Supply a valid target. A missing target, including None, raises TypeError.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        A missing source date returns False in the Boolean result.
        """
        ...

    def is_weekday(self, weekday: _QuerySelection) -> pl.Series:
        """Test for a local weekday by name or by number, with Monday as 0.

        Parameters
        ----------
        weekday : integer, name or one-dimensional collection
            Weekday number, with Monday as 0, or a weekday name in the library's default
            vocabulary.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def is_day(self, day: _IntegerInput) -> pl.Series:
        """Test whether each local day of the month equals the supplied day.

        Parameters
        ----------
        day : integer or one-dimensional integer collection
            An integer day or a same-length integer column paired by position. A valid
            integer outside the matching range yields False. Strings, booleans and missing targets are invalid.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Supply a valid target. A missing target, including None, raises TypeError.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        A missing source date returns False in the Boolean result.
        """
        ...

    def is_long_year(self) -> pl.Series:
        """Whether the local calendar year contains 53 ISO weeks; null is False.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def leap_bt_year(self, year: _IntegerInput) -> pl.Series:
        """Count leap years between row years and targets, lower inclusive.

        Parameters
        ----------
        year : integer or one-dimensional integer collection
            Required signed integer target year or exactly equal-length targets. Count leap years between
            the two years, lower inclusive and upper exclusive; missing targets fail even for null source
            dates.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Supply a valid target. A missing target, including None, raises TypeError.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        Each count describes the years between the two inputs.
        """
        ...

    def is_dst(self) -> pl.Series:
        """Whether the native zone has nonzero DST; naive/null is False.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def utcoffset_seconds(self) -> pl.Series:
        """Actual integer UTC offset; naive and missing rows are null.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_past(self) -> pl.Series:
        """Strictly before one captured reference; Expr captures on creation.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_future(self) -> pl.Series:
        """Strictly after one captured reference; Expr captures on creation.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def isocalendar(self) -> pl.Series:
        """Return the ISO year, week, and weekday in a Struct with UInt32 fields.

        Use isoyear() to read ISO years as signed integers.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            An input date has an ISO year outside the UInt32 range.

        Examples
        --------
        >>> from rstimes import Pldt
        >>> Pldt(["2021-01-01"]).isocalendar().to_list()
        [{'year': 2020, 'week': 53, 'day': 5}]
        """
        ...

    def timedf(self) -> pl.DataFrame:
        """Read the nine local calendar and clock fields.

        The fields are tm_year, tm_mon, tm_mday, tm_hour, tm_min, tm_sec,
        tm_wday, tm_yday, and tm_isdst. tm_sec is the whole second of the minute.

        Returns
        -------
        polars.DataFrame
            A Polars DataFrame with one column for each of the nine fields.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def utctimedf(self) -> pl.DataFrame:
        """Return UTC time fields; naive fields do not move and DST is zero.
        
        Returns
        -------
        pl.DataFrame
            Native nine-column time table with fixed child dtypes; source nulls remain null.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def toseconds(self, utc: _Boolean=False) -> pl.Series:
        """Return Float64 seconds in local coordinates, or UTC when requested.

        Parameters
        ----------
        utc : bool or numpy.bool_
            Use UTC coordinates when True; otherwise use local clock coordinates. A naive datetime remains
            timezone-naive.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> from rstimes import Pldt
        >>> x = Pldt(["1970-01-01 08:00:00"], tz="Asia/Shanghai", unit="us")
        >>> x.toseconds().to_list()
        [28800.0]
        >>> x.toseconds(utc=True).to_list()
        [0.0]
        """
        ...

    def tomicroseconds(self, utc: _Boolean=False) -> pl.Series:
        """Return Int64 microseconds, flooring only at this explicit output.

        Parameters
        ----------
        utc : bool or numpy.bool_
            Use UTC coordinates when True; otherwise use local clock coordinates. A naive datetime remains
            timezone-naive.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> from rstimes import Pldt
        >>> Pldt(["1970-01-01 00:00:00.000001"], unit="ns").tomicroseconds().to_list()
        [1]
        """
        ...

    def toordinal(self) -> pl.Series:
        """Return Int64 proleptic Gregorian day ordinals; missing stays null.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def timestamp(self) -> pl.Series:
        """Return Float64 UTC seconds; naive dates use the process local zone.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            The process local timezone is unavailable, or a naive time is repeated
            or nonexistent. Use tz_localize with an explicit ambiguous or nonexistent
            policy before calling timestamp().
        OverflowError
            A naive date's local time is outside the supported regional timezone range.

        Examples
        --------
        >>> from rstimes import Pldt
        >>> Pldt(["1970-01-01 08:00:00"], tz="Asia/Shanghai").timestamp().to_list()
        [0.0]
        """
        ...

    @property
    def values_naive(self) -> pl.Series:
        """Return a plain native Datetime column of local wall coordinates.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The local wall time exceeds the current tick unit's capacity,
            or the date is outside the supported regional timezone range."""
        ...

    @property
    def date(self) -> pl.Series:
        """Return a native Date column, checked against its signed32-day range.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The local date exceeds the native Date type's signed 32-bit day range,
            or the date is outside the supported regional timezone range."""
        ...

    @property
    def time(self) -> pl.Series:
        """Return a native Time column retaining the full time-of-day nanoseconds.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def isoformat(self, sep: str='T', timespec: str='auto') -> pl.Series:
        """Return ISO strings with explicit precision and colon-separated offsets.
        
        Parameters
        ----------
        sep : str
            Separator between ISO date and time, normally T.
        timespec : str
            auto/hours/minutes/seconds/milliseconds/microseconds/nanoseconds, including the approved
            h/m/min/s/ms/us/ns aliases; uppercase H and M are not accepted.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def strftime(self, format: str) -> pl.Series:
        """Return strings using native numeric/fraction fields or an eager system adapter.

        Parameters
        ----------
        format : str
            Shared strftime format. %f emits 9 digits for ns and 6 for ms/us; %.1f through %.9f emit a dot
            plus that many truncated/padded digits, and %.0f is empty. System-locale/platform directives
            are eager-only; numeric directives remain native in Expr.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> from rstimes import Pldt
        >>> Pldt([123456789], unit="ns").strftime("%f|%.3f|%.0f").to_list()
        ['123456789|.123|']
        """
        ...

    def ctime(self) -> pl.Series:
        """Return English ctime strings, independent of the process locale.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def month_name(self, locale: str | None=None) -> pl.Series:
        """Return compiled CLDR month names; the default language is English.

        Parameters
        ----------
        locale : str or None
            Supported CLDR locale such as en_US or zh_CN; None uses English. This does not change parser
            Configs.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def weekday_name(self, locale: str | None=None) -> pl.Series:
        """Return compiled CLDR weekday names; the default language is English.

        Parameters
        ----------
        locale : str or None
            Supported CLDR locale such as en_US or zh_CN; None uses English. This does not change parser
            Configs.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def tzname(self) -> pl.Series:
        """Return the native zone abbreviation at each instant, or null if naive.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def datetime(self) -> np.ndarray:
        """Return an object array of Pydt/None, explicitly truncating to microseconds.

        Returns
        -------
        np.ndarray
            The stated native/Python output representation. Genuine external callback choices and
            exceptions retain their normal protocol.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> from rstimes import Pldt
        >>> type(Pldt([0], unit="ns").datetime()[0]).__name__
        'Pydt'
        """
        ...

    @property
    def timetz(self) -> np.ndarray:
        """Return an object array of standard time/None, preserving zone and fold.
        
        Returns
        -------
        np.ndarray
            The stated native/Python output representation. Genuine external callback choices and
            exceptions retain their normal protocol.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def tzinfo(self) -> _dt.tzinfo | None:
        """Return the normalized timezone encoded by the entire column.
        
        Returns
        -------
        datetime.tzinfo or None
            None for naive dates, timezone.utc for UTC aliases, or ZoneInfo
            for another supported IANA key. Original object identity is absent
            from Polars metadata, including for empty columns."""
        ...

    @property
    def tz_available(self) -> set[str]:
        """Return region names supported by the bundled native backend.
        
        Returns
        -------
        set[str]
            A fresh set of supported keys, independent of the system ZoneInfo
            database. This does not resolve the local timezone or read dates."""
        ...

    def is_utc(self) -> bool:
        """Return whether the column's actual metadata represents UTC.
        
        Returns
        -------
        bool
            One boolean for the whole column, also for empty/all-null data.
            This query does not resolve the process-local timezone."""
        ...

    def is_local(self) -> bool:
        """Compare encoded metadata with the cached process-local zone.
        
        Returns
        -------
        bool
            False for naive dates without detecting a local zone. An aware
            column resolves the shared local service only when this is called;
            a failed lookup raises instead of silently assuming UTC."""
        ...

    def __init__(self, data: _DateCollection, *, unit: _Unit | None=None, name: str | None=None, copy: _Boolean=False, default: _DateValue=None, yearfirst: _Boolean | None=None, dayfirst: _Boolean | None=None, isoformat: _Boolean=True, strict: _Boolean=False, cfg: Configs | None=None, tz: _Zone=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> None:
        """Initialize this Pldt datetime Series from a one-dimensional collection.

        Parameters
        ----------
        data : one-dimensional date collection
            Supported dates, datetimes, text, numeric ticks or native one-dimensional
            columns. Legal mixtures and missing values are accepted. Scalar inputs,
            mappings, sets, tables and nested rows are rejected, without flattening.
        unit : {"ms", "us", "ns"}, default None
            Storage resolution ms/us/ns; Polars has no Datetime(s). None selects
            the resolution using source metadata and the documented parsing rules.
            An explicit unit must preserve the input precision and capacity.
        name : str, default None
            Column name. None retains a usable source name, or uses an empty name.
        copy : bool or numpy.bool_, default False
            True physically isolates date buffers. False allows safe sharing;
            it does not promise zero-copy or a snapshot of arbitrary input objects.
        default : date-like value, default None
            An independently complete fallback date, used only when text needs
            missing YMD fields or a two-digit-year reference. It supplies no
            clock, timezone, fractional second or fold.
        yearfirst : bool, numpy.bool_, default None
            Non-None overrides Configs; otherwise use its preference, or True
            when no Configs is supplied. False is an explicit preference.
        dayfirst : bool, numpy.bool_, default None
            Non-None overrides Configs; otherwise use its preference, or False
            when no Configs is supplied.
        isoformat : bool or numpy.bool_, default True
            Try ISO recognition before the general shared grammar. This is not
            an ISO-only validation option.
        strict : bool or numpy.bool_, default False
            Validate explicit parsed fields and conflicts. Regional ambiguity
            and missing-clock policies remain separate.
        cfg : Configs, default None
            Effective word/region rules; None uses built-in rules. Text with
            a regional name must have that name registered in these rules.
        tz : str, datetime.tzinfo, default None
            A supported target IANA name, ZoneInfo or representable standard
            fixed offset. None retains a supported aware source zone; naive
            sources remain naive. A non-None target localizes naive clocks or
            converts known instants. Business target rules that cannot be
            encoded by Polars raise ValueError instead of being replaced by key.
            ZoneInfo.from_file objects are not accepted as native target rules,
            even when their display key matches a standard name. Standard named
            constructors, no_cache and passive named subclasses remain supported.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask, default 'raise'
            Repeated-clock policy: 'raise', 'NaT', 'infer', a real boolean or
            an aligned boolean mask. Boolean choices follow pandas-compatible
            candidate rules, not universal earlier/later fold numbering.
        nonexistent : str or datetime.timedelta, default 'raise'
            One missing-clock policy: 'raise', 'NaT', 'shift_forward',
            'shift_backward' or a supported timedelta. Shifts select the
            nearest valid boundary; per-row policy lists are not supported.

        Returns
        -------
        None
            Initializes this Series instance; __init__ does not return a column.
            The surrounding Pldt(...) expression returns the initialized Pldt.

        Raises
        ------
        TypeError
            An input type, scalar protocol, shape or parameter role is unsupported.
        ValueError
            A field, precision conversion, target timezone or localization policy
            is invalid or unsupported.
        OverflowError
            A true value cannot be represented at the chosen unit.

        Examples
        --------
        >>> from datetime import datetime, timezone
        >>> from rstimes import Pldt
        >>> x = Pldt([1, None], unit="ns", name="time")
        >>> x.to_physical().to_list()
        [1, None]
        >>> aware = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
        >>> Pldt([aware], unit="us", tz=None).dtype.time_zone
        'UTC'
        """
        ...

    @classmethod
    def parse(cls, data: _DateCollection, *, unit: _Unit | None=None, name: str | None=None, copy: _Boolean=False, tz: _Zone=None, default: _DateValue=None, yearfirst: _Boolean | None=None, dayfirst: _Boolean | None=None, isoformat: _Boolean=True, strict: _Boolean=False, cfg: Configs | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Construct a date column through the same shared native input rules.

        Parameters
        ----------
        data : one-dimensional date collection
            Legal one-dimensional date collection; text/date/datetime/NumPy scalars/numeric ticks and
            supported native columns may mix. No scalar, mapping, set, table, nested row or automatic
            flattening.
        unit : {"ms", "us", "ns"} or None
            Without a unit, text uses us for up to six fractional digits and ns for seven
            through nine, even if the additional digits are zero. An explicit unit must represent every date without loss.
            Without a unit, preserve native Datetime resolution and use ns for bare ticks.
            An untyped empty or all-null input defaults to ms.
        name : str or None
            Set the result's column name. None keeps the source name when present.
            A subclass copy that returns the original cannot assign it a different name.
        copy : bool or numpy.bool_
            True isolates source date buffers; False permits safe sharing but does not promise zero-copy
            or an independent snapshot.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach the chosen zone to naive dates and convert aware dates to it while keeping
            their instants. With None, use the source timezone when the input can form a single
            zone.
        default : date-like value or None
            An independently complete fallback date, read only when needed to fill text YMD/two-digit-year
            reference. It does not supply the column clock, zone or fold.
        yearfirst : bool or numpy.bool_ or None
            Prefer the year as the first field in an ambiguous date. None uses the Configs
            setting when present, or True otherwise.
        dayfirst : bool or numpy.bool_ or None
            Prefer the day before the month in an ambiguous numeric date. None uses the Configs
            setting when present, or False otherwise.
        isoformat : bool or numpy.bool_
            Try ISO first and then shared ordinary parsing when needed; this is not ISO-only validation.
        strict : bool or numpy.bool_
            Validate explicit parsed date/clock fields and conflicts; it does not replace the regional DST
            policies.
        cfg : Configs or None
            Parser vocabulary and timezone aliases used by this call. None uses the built-in
            rules.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> from rstimes import Pldt
        >>> Pldt.parse(["1970-01-01T00:00:00.000000001"]).to_physical().to_list()
        [1]
        """
        ...

    @classmethod
    def strptime(cls, dtstr: _IsoInput, fmt: str, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, cfg: Configs | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Match a shared explicit format; scalar text requires size.

        Parameters
        ----------
        dtstr : str, one-dimensional collection of strings or None
            Source/target in this factory's stated role. Actual dtype/unit/zone and independent validity
            are preserved; a scalar broadcasts only where the named factory permits it.
        fmt : str
            Explicit parsing format. %f reads fractional seconds through ns; excess digits and a
            deliberately requested coarser unit truncate at this format-parse exit. %Z uses explicit
            Configs rules. Expr formats with %f require unit; timezone directives require tz.
        size : SupportsIndex or None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach the chosen zone to clocks parsed without a zone and convert aware parsed
            values to it. With None, keep a common zone from the parsed input if one is present.
        unit : {"ms", "us", "ns"} or None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str or None
            Set the result's column name. None keeps the source name when present.
        cfg : Configs or None
            Parser vocabulary and timezone aliases used by this call. None uses the built-in
            rules.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> from rstimes import Pldt
        >>> Pldt.strptime(["1970-01-01 00:00:00.123456789"], "%Y-%m-%d %H:%M:%S.%f", unit="ns").nanosecond.to_list()
        [789]
        """
        ...

    @classmethod
    def now(cls, size: SupportsIndex, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None) -> Self:
        """Repeat one current instant, or its local naive clock when tz is None.

        Parameters
        ----------
        size : SupportsIndex
            Number of copies of the sampled time. A zero count produces an empty date column.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Display the current instant in this timezone. With None, use the local clock and
            return naive values.
        unit : {"ms", "us", "ns"} or None
            Requested current-time resolution ms/us/ns; None selects us. This deliberately quantizes the
            current time and does not claim nanosecond clock accuracy.
        name : str or None
            Set the result's column name. None keeps the source name when present.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    @classmethod
    def today(cls, size: SupportsIndex, *, unit: _Unit | None=None, name: str | None=None) -> Self:
        """Repeat the current full local clock; this does not normalize midnight.

        Parameters
        ----------
        size : SupportsIndex
            Number of copies of the sampled time. A zero count produces an empty date column.
        unit : {"ms", "us", "ns"} or None
            Requested current-time resolution ms/us/ns; None selects us. This deliberately quantizes the
            current time and does not claim nanosecond clock accuracy.
        name : str or None
            Set the result's column name. None keeps the source name when present.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    @classmethod
    def utcnow(cls, size: SupportsIndex, *, unit: _Unit | None=None, name: str | None=None) -> Self:
        """Repeat one current true instant with UTC metadata and real precision.

        Parameters
        ----------
        size : SupportsIndex
            Number of copies of the sampled time. A zero count produces an empty date column.
        unit : {"ms", "us", "ns"} or None
            Requested current-time resolution ms/us/ns; None selects us. This deliberately quantizes the
            current time and does not claim nanosecond clock accuracy.
        name : str or None
            Set the result's column name. None keeps the source name when present.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    @classmethod
    def fromseconds(cls, seconds: _NumericInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Build dates from numeric seconds measured on a local clock.

        Parameters
        ----------
        seconds : number or one-dimensional numeric collection or None
            Numeric seconds in calendar coordinates, including supported finite fractions. Not Unix-local-
            time inference and not raw ticks in the output unit.
        size : SupportsIndex or None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach this zone to the local clock fields counted from midnight on 1970-01-01. With
            None, the result is timezone-naive.
        unit : {"ms", "us", "ns"} or None
            Choose ms, us or ns for the output. None selects us, or ns for a value requiring
            nanosecond precision. Every value must fit the chosen resolution exactly.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        A missing input value produces a null date. Other supplied fields still need to be valid. A scalar component repeats across the other supplied columns, which must have equal lengths.

        Examples
        --------
        >>> from rstimes import Pldt
        >>> Pldt.fromseconds([1e-9], unit="ns").to_physical().to_list()
        [1]
        """
        ...

    @classmethod
    def frommicroseconds(cls, us: _CalendarInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Build dates from integer microseconds measured on a local clock.

        Parameters
        ----------
        us : integer or one-dimensional integer collection or None
            Integer microseconds in the calendar coordinate system; floats/bools/text are rejected.
            Explicit unit conversion must be lossless.
        size : SupportsIndex or None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach this zone to the local clock fields counted from midnight on 1970-01-01. With
            None, the result is timezone-naive.
        unit : {"ms", "us", "ns"} or None
            Choose ms, us or ns for the output. None selects us. The input is always integer
            microseconds, and the result must fit the output unit exactly.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> from rstimes import Pldt
        >>> Pldt.frommicroseconds([1], unit="ns").to_physical().to_list()
        [1000]
        """
        ...

    @classmethod
    def fromtimestamp(cls, ts: _NumericInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None) -> Self:
        """Convert POSIX seconds to clock fields in the target timezone.

        Parameters
        ----------
        ts : number or one-dimensional numeric collection or None
            Numeric Unix seconds representing real UTC instants, including supported finite fractions. Not
            raw ticks in the output unit.
        size : SupportsIndex or None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Display each POSIX instant in this timezone. With None, use the system's local clock
            and return a timezone-naive column.
        unit : {"ms", "us", "ns"} or None
            Choose ms, us or ns for the output. None selects us, or ns for a value requiring
            nanosecond precision. Every value must fit the chosen resolution exactly.
        name : str or None
            Set the result's column name. None keeps the source name when present.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> from rstimes import Pldt
        >>> Pldt.fromtimestamp([0], tz="UTC", unit="us").to_physical().to_list()
        [0]
        """
        ...

    @classmethod
    def utcfromtimestamp(cls, ts: _NumericInput, *, size: SupportsIndex | None=None, unit: _Unit | None=None, name: str | None=None) -> Self:
        """Convert POSIX seconds to timezone-aware UTC dates.

        Parameters
        ----------
        ts : number or one-dimensional numeric collection or None
            Numeric Unix seconds representing real UTC instants, including supported finite fractions. Not
            raw ticks in the output unit.
        size : SupportsIndex or None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        unit : {"ms", "us", "ns"} or None
            Choose ms, us or ns for the output. None selects us, or ns for a value requiring
            nanosecond precision. Every value must fit the chosen resolution exactly.
        name : str or None
            Set the result's column name. None keeps the source name when present.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    @classmethod
    def fromdate(cls, dt: _ActualDateInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Take each source's local calendar date at midnight.

        Parameters
        ----------
        dt : date, datetime or one-dimensional date collection or None
            Actual Python date/datetime or native Date/Datetime column. Take local YMD, clear
            clock/fraction/source zone; strings, numbers and NumPy dates do not enter this specialized
            factory.
        size : SupportsIndex or None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. Use the source's local
            date. With None the result is naive at midnight. An explicit zone attaches at that midnight.
        unit : {"ms", "us", "ns"} or None
            Storage resolution ms/us/ns. Date inputs default to milliseconds. Datetime columns keep
            their declared unit. A Python datetime defaults to microseconds.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    @classmethod
    def fromdatetime(cls, dt: _DatetimeInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Read the complete source clock fields and keep the source zone by default.

        Parameters
        ----------
        dt : datetime or one-dimensional datetime collection or None
            Actual datetime/Pydt/Timestamp or native Datetime column. None target preserves source
            instants/zone; an explicit non-None target replaces the zone while retaining wall fields. Pure
            date, text, numbers and NumPy dates are rejected.
        size : SupportsIndex or None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. Omit tz or pass None to
            keep the source timezone and instant. An explicit zone reinterprets the source's local clock
            fields in that zone.
        unit : {"ms", "us", "ns"} or None
            Storage resolution ms/us/ns. Datetime columns keep their declared unit. A Python datetime
            defaults to microseconds.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-factories.html#reader-pldt-datetime-source-zone
        """
        ...

    @classmethod
    def fromdatetime64(cls, dt64: _NumpyDateInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Decode dates from the unit and multiplier of NumPy datetime64 values.

        Parameters
        ----------
        dt64 : numpy.datetime64 or one-dimensional NumPy date collection or None
            Actual NumPy datetime64 scalar/one-dimensional date source. Decode unit/multiplier directly;
            do not accept ordinary datetime or pandas/Polars date columns. An explicit zone localizes
            decoded clocks.
        size : SupportsIndex or None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach this timezone to the clock read from NumPy. With None, leave the decoded
            clock timezone-naive.
        unit : {"ms", "us", "ns"} or None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-factories.html#reader-pldt-numpy-date-input
        """
        ...

    @classmethod
    def fromordinal(cls, ordinal: _CalendarInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit='us', name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Build dates from Gregorian day numbers, with 1 for January 1 of year 1.

        Parameters
        ----------
        ordinal : integer or one-dimensional integer collection or None
            Gregorian ordinal with 0001-01-01 equal to 1. Zero and negative ordinals are real dates in the
            native target's capacity, not missing or skip sentinels.
        size : SupportsIndex or None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach this timezone at the computed local midnight. With None, return naive dates.
        unit : {"ms", "us", "ns"}, default "us"
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback. Explicit None is not accepted.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    @classmethod
    def fromisocalendar(cls, year: _CalendarInput, week: _CalendarInput, weekday: _CalendarInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit='us', name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Build dates from ISO week-years, week numbers and weekdays.

        Parameters
        ----------
        year : integer or one-dimensional integer collection or None
            Integer calendar/ISO year, including zero and negative years when the unit/backend can
            represent the result. An explicit missing component makes a missing row; it is not a preserve
            sentinel.
        week : integer or one-dimensional integer collection or None
            Integer day-of-year/ISO-week component, scalar or equal-length column. Values below 1 fail;
            approved upper convenience selection is retained. An explicit missing component makes a
            missing row.
        weekday : integer or one-dimensional integer collection or None
            ISO weekday: Monday 1 through Sunday 7. Values below 1 fail, values above 7 select Sunday; an
            explicit missing component makes a missing row.
        size : SupportsIndex or None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach this timezone at the computed local midnight. With None, return naive dates.
        unit : {"ms", "us", "ns"}, default "us"
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback. Explicit None is not accepted.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        A missing input value produces a null date. Other supplied fields still need to be valid. A scalar component repeats across the other supplied columns, which must have equal lengths.
        """
        ...

    @classmethod
    def fromdayofyear(cls, year: _CalendarInput, doy: _CalendarInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit='us', name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Build dates from years and their one-based day numbers.

        Parameters
        ----------
        year : integer or one-dimensional integer collection or None
            Integer calendar/ISO year, including zero and negative years when the unit/backend can
            represent the result. An explicit missing component makes a missing row; it is not a preserve
            sentinel.
        doy : integer or one-dimensional integer collection or None
            Integer day-of-year/ISO-week component, scalar or equal-length column. Values below 1 fail;
            approved upper convenience selection is retained. An explicit missing component makes a
            missing row.
        size : SupportsIndex or None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach this timezone at the computed local midnight. With None, return naive dates.
        unit : {"ms", "us", "ns"}, default "us"
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback. Explicit None is not accepted.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        A missing input value produces a null date. Other supplied fields still need to be valid. A scalar component repeats across the other supplied columns, which must have equal lengths.
        """
        ...

    @classmethod
    def combine(cls, date: _DateInput=None, time: _CombineTime=None, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Combine local YMD and clock fields; only the final result is a Pldt.

        Parameters
        ----------
        date : date-like value or one-dimensional date collection
            Local calendar date to combine with the supplied clock. None uses today's local
            calendar date. A missing row remains null.
        time : time, date-like value, clock column or None
            Clock fields and an optional source zone. A Python time can supply a timezone. A
            Polars Time column supplies native nanosecond fields. A scalar None means midnight.
            Null positions in a clock column remain null.
        size : SupportsIndex or None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach this timezone to the assembled local fields. With None, keep the clock's zone
            when it supplies one. A Polars Time column supplies clock fields and no zone.
        unit : {"ms", "us", "ns"} or None
            Choose ms, us or ns. None selects us, or ns when the clock supplies a nonzero
            nanosecond tail. The result must fit the output unit exactly.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-factories.html#pldt-combine-precise-clock
        """
        ...

    @classmethod
    def fromisoformat(cls, dtstr: _IsoInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Read complete strict ISO dates, retaining source fraction width.

        Parameters
        ----------
        dtstr : str, one-dimensional collection of strings or None
            Source/target in this factory's stated role. Actual dtype/unit/zone and independent validity
            are preserved; a scalar broadcasts only where the named factory permits it.
        size : SupportsIndex or None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach the chosen zone to naive ISO dates and convert ISO values with a zone to it.
            With None, keep a common zone from the input if one is present.
        unit : {"ms", "us", "ns"} or None
            Without a unit, text uses us for up to six fractional digits and ns for seven
            through nine, even if the additional digits are zero. An explicit unit must represent every date without loss.
            An empty or all-null text input without a declared resolution uses ms.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-factories.html#reader-pldt-iso-text
        """
        ...

    @classmethod
    def date_range(cls, start: _DateInput=None, *, end: _DateInput=None, periods: SupportsIndex | None=None, freq: object=None, tz: _Zone=None, normalize: _Boolean=False, inclusive: str='both', unit: _Unit | None=None, name: str | None=None, default: _DateValue=None, yearfirst: _Boolean | None=None, dayfirst: _Boolean | None=None, isoformat: _Boolean=True, strict: _Boolean=False, cfg: Configs | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Generate native calendar/elapsed dates; only special rules use optional pandas.

        Parameters
        ----------
        start : date-like value or one-dimensional date collection
            First boundary of the range. Supply a scalar date or a value the parser can read. A
            number is a tick of the specified unit, or of ns by default. None leaves the
            boundary unspecified.
        end : date-like value or one-dimensional date collection
            Last boundary of the range. Supply a scalar date or a value the parser can read. A
            number is a tick of the specified unit, or of ns by default. None leaves the
            boundary unspecified.
        periods : SupportsIndex or None
            Number of periods as a nonnegative integer.
        freq : object
            A frequency string, timedelta, or supported pandas DateOffset. The step can be positive
            (forward) or negative (backward). Semi-month starts (SMS) accept day anchors 2 through 27,
            and semi-month ends (SME) accept 1 through 27. With start, end, and periods supplied,
            freq=None spaces the values evenly between the endpoints. Otherwise None defaults to days.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Interpret naive endpoints in this timezone and convert aware endpoints into it. With
            None, use a common timezone from the endpoints if present.
        normalize : bool or numpy.bool_
            Move prepared endpoints to their local day boundary before range validation/generation when
            True.
        inclusive : str
            Keep both endpoints, only start (left), only end (right), or neither.
        unit : {"ms", "us", "ns"} or None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str or None
            Set the result's column name. None keeps the source name when present.
        default : date-like value or None
            An independently complete fallback date, read only when needed to fill text YMD/two-digit-year
            reference. It does not supply the column clock, zone or fold.
        yearfirst : bool or numpy.bool_ or None
            Prefer the year as the first field in an ambiguous date. None uses the Configs
            setting when present, or True otherwise.
        dayfirst : bool or numpy.bool_ or None
            Prefer the day before the month in an ambiguous numeric date. None uses the Configs
            setting when present, or False otherwise.
        isoformat : bool or numpy.bool_
            Try ISO first and then shared ordinary parsing when needed; this is not ISO-only validation.
        strict : bool or numpy.bool_
            Validate explicit parsed date/clock fields and conflicts; it does not replace the regional DST
            policies.
        cfg : Configs or None
            Parser vocabulary and timezone aliases used by this call. None uses the built-in
            rules.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> from rstimes import Pldt
        >>> Pldt.date_range("1970-01-01", periods=3, freq="s", unit="us").to_physical().to_list()
        [0, 1000000, 2000000]
        """
        ...

    def as_unit(self, unit: _Unit, round_ok: _Boolean=True) -> Self:
        """Return the chosen ms/us/ns resolution; round_ok=True floors precision loss.

        Parameters
        ----------
        unit : {"ms", "us", "ns"}
            Required target storage unit. Choose ms, us or ns.
        round_ok : bool or numpy.bool_
            True allows this explicit rescale to floor discarded precision toward earlier ticks; False
            requires an exact conversion.

        Returns
        -------
        Self
            Date column with the target unit. The column name, timezone and nulls are retained.

        Raises
        ------
        TypeError
            The unit or round_ok argument has an unsupported type.
        ValueError
            The unit is unsupported, or an exact conversion would lose precision.
        OverflowError
            A value exceeds the target unit's capacity, even when rounding is allowed.

        Examples
        --------
        >>> from rstimes import Pldt
        >>> Pldt([-1500], unit="ns").as_unit("us").to_physical().to_list()
        [-2]
        """
        ...

    def tz_localize(self, tz: _Zone, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Interpret naive clocks, or remove a timezone while keeping clocks.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. Attach the zone to
            naive local clocks. Pass None to remove the zone while keeping the local clock.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-timezones.html#reader-pldt-timezone-choices
        """
        ...

    def tz_convert(self, tz: _Zone) -> Self:
        """Preserve actual instants; None removes the UTC timezone metadata.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. The source must be
            timezone-aware. Pass None to convert to UTC and then remove the zone. A target zone
            preserves the instant.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-timezones.html#reader-pldt-timezone-choices
        """
        ...

    def astimezone(self, tz: _Zone=None, *, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Convert to the target; naive input uses the process-local timezone.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. Omit tz or pass None to
            use the system local timezone. A naive source is interpreted in the local timezone.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-timezones.html#reader-pldt-timezone-choices
        """
        ...

    def tz_switch(self, targ_tz: _Zone, base_tz: _Zone=None, naive: _Boolean=False, *, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Convert with an explicit naive source zone, optionally removing target metadata.

        Parameters
        ----------
        targ_tz : str, datetime.tzinfo or None
            Required target timezone. Use an IANA name, ZoneInfo or a representable standard fixed
            offset. Pass None to remove the timezone and keep local clocks. A non-None target converts
            the instant. naive=True removes a target timezone after conversion.
        base_tz : str, datetime.tzinfo or None
            Source timezone for a naive date when converting to a non-None target. It is required for
            that conversion. An aware source uses its own timezone.
        naive : bool or numpy.bool_
            Remove target timezone metadata after the requested conversion when True.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-timezones.html#reader-pldt-timezone-choices
        """
        ...

    def __copy__(self) -> Self:
        """Return an independent same-class shell with shallow business state.
        
        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def copy(self, name: str | None=None, deep: _Boolean=False) -> Self:
        """Copy dates and business state without rerunning business initialization.

        Parameters
        ----------
        name : str, default None
            Replacement column name. None retains the current name.
        deep : bool or numpy.bool_, default False
            Physically isolate date buffers and copy business state with one
            shared memo when True; otherwise share safe buffers/references.

        Returns
        -------
        Pldt
            A fresh same-class shell under the default protocol. Genuine custom
            copy/reduction hooks retain their return values and exceptions.

        Notes
        -----
        Custom shallow-copy hooks are looked up on the class and receive the source;
        custom deep-copy hooks are looked up on the instance and receive the memo,
        as in Python's copy module. Real descriptors, return choices and exceptions
        are preserved. Actual reducers follow copyreg and __reduce_ex__/__reduce__ fallback, including
        absent/None descriptors and dynamic lookup. Default date copying keeps
        its native buffer path; genuine state hooks retain their own behavior.
        """
        ...

    def __deepcopy__(self, memo: dict[int, Any] | None=None) -> Self:
        """Copy date buffers physically and business state with one shared memo.
        
        Parameters
        ----------
        memo : dict[int, Any] | None
            Existing Python deep-copy memo; aliases and cycles share this exact dictionary.
        
        Returns
        -------
        Self
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    # Own versioned business-state protocol, not native Series serialized bytes.
    def __getstate__(self) -> object:  # pyright: ignore[reportIncompatibleMethodOverride] -- TY037; see tests/typing/pyright_exceptions.json.
        """Return business dictionary/initialized slots, without native caches.
        
        Returns
        -------
        object
            The stated native/Python output representation. Genuine external callback choices and
            exceptions retain their normal protocol.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def __setstate__(self, state: object) -> None:
        """Restore business state without replacing the validated date core.
        
        Parameters
        ----------
        state : object
            Actual business state, separate from the validated native core; it cannot replace the core
            handle.
        
        Returns
        -------
        None
            The existing receiver/state/namespace is initialized; no result column is returned.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def __reduce__(self) -> str | tuple[object, ...]:
        """Return the versioned native core and separate business state recipe.
        
        Returns
        -------
        str | tuple[object, ...]
            The stated native/Python output representation. Genuine external callback choices and
            exceptions retain their normal protocol.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def __reduce_ex__(self, protocol: SupportsIndex) -> str | tuple[object, ...]:
        """Respect a genuine custom reduce hook, otherwise save the current core.
        
        Parameters
        ----------
        protocol : SupportsIndex
            Standard Python pickle/reduction protocol; only trusted serialized data should be loaded.
        
        Returns
        -------
        str | tuple[object, ...]
            The stated native/Python output representation. Genuine external callback choices and
            exceptions retain their normal protocol.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_numpy(self, *, writable: _Boolean=False, allow_copy: _Boolean=True, allow_nat_collision: _Boolean=False) -> np.ndarray:  # pyright: ignore[reportIncompatibleMethodOverride] -- TY038; see tests/typing/pyright_exceptions.json.
        """Use Polars' NumPy export, rejecting valid ticks that collide with NaT.

        Parameters
        ----------
        writable : bool or numpy.bool_
            Original Polars/NumPy export option, passed to the mature implementation. Requested
            conversions must preserve values/precision/validity unless the collision opt-in applies.
        allow_copy : bool or numpy.bool_
            Original Polars/NumPy export option, passed to the mature implementation. Requested
            conversions must preserve values/precision/validity unless the collision opt-in applies.
        allow_nat_collision : bool or numpy.bool_
            False rejects a valid int64 MIN that the target would turn into NaT. True explicitly permits
            only that representation collision.

        Returns
        -------
        np.ndarray
            The stated native/Python output representation. Genuine external callback choices and
            exceptions retain their normal protocol.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-output.html#pldt-numpy-explicit-nat-collision
        """
        ...

    def to_pandas(self, *, use_pyarrow_extension_array: _Boolean=False, allow_nat_collision: _Boolean=False, **kwargs: Any) -> pd.Series:
        """Use the complete Polars pandas export and check its actual date result.

        Parameters
        ----------
        use_pyarrow_extension_array : bool or numpy.bool_
            Original Polars/NumPy export option, passed to the mature implementation. Requested
            conversions must preserve values/precision/validity unless the collision opt-in applies.
        allow_nat_collision : bool or numpy.bool_
            False rejects a valid int64 MIN that the target would turn into NaT. True explicitly permits
            only that representation collision.
        kwargs : Any
            Original protocol argument, forwarded without inventing another interpretation.

        Returns
        -------
        pd.Series
            The stated native/Python output representation. Genuine external callback choices and
            exceptions retain their normal protocol.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-pandas-arrow.html#pldt-arrow-valid-endpoint-roundtrip
        """
        ...

    def __array__(self, dtype: Any=None, copy: bool | None=None) -> np.ndarray:
        """Retain native dtype/copy dispatch and validate explicit dtype changes.
        
        Parameters
        ----------
        dtype : Any
            Original Polars/NumPy export option, passed to the mature implementation. Requested
            conversions must preserve values/precision/validity unless the collision opt-in applies.
        copy : bool | None
            True requests an independent copy. False raises if the export needs a copy.
            None lets the native exporter decide whether to copy.
        
        Returns
        -------
        np.ndarray
            The stated native/Python output representation. Genuine external callback choices and
            exceptions retain their normal protocol.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def __array_ufunc__(self, ufunc: Any, method: Any, *inputs: Any, **kwargs: Any) -> Any:
        """Preserve NumPy temporal operands for the approved arithmetic routes.

        Parameters
        ----------
        ufunc : Any
            Original protocol argument, forwarded without inventing another interpretation.
        method : Any
            Original protocol argument, forwarded without inventing another interpretation.
        inputs : Any
            Original protocol argument, forwarded without inventing another interpretation.
        kwargs : Any
            Original protocol argument, forwarded without inventing another interpretation.

        Returns
        -------
        Any
            The stated native/Python output representation. Genuine external callback choices and
            exceptions retain their normal protocol.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-interop.html#reader-pldt-numpy-temporal-arithmetic
        """
        ...

    # Approved date arithmetic/Duration output differs from the generic Series Self stub.
    @overload
    def __add__(self, other: Delta | _dt.timedelta | np.timedelta64) -> Self:
        """Apply a calendar Delta or a fixed elapsed duration.

        Parameters
        ----------
        other : Delta, timedelta or numpy.timedelta64
            Actual increment; negative values reverse the direction.

        Returns
        -------
        Self
            Date result at the original fixed unit, with genuine subclass rules.
        """
        ...

    @overload
    def __add__(self, other: Any) -> Self | pl.Series | NotImplementedType:  # pyright: ignore[reportIncompatibleMethodOverride] -- TY039; see tests/typing/pyright_exceptions.json.
        """Apply a calendar Delta or fixed elapsed duration at the current unit.
        
        Parameters
        ----------
        other : Any
            Actual date/duration/Delta operand under ordinary Python negotiation. Unknown operands retain
            NotImplemented/original external protocol behavior.
        
        Returns
        -------
        Self | pl.Series | NotImplementedType
            The stated native/Python output representation. Genuine external callback choices and
            exceptions retain their normal protocol.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    # Approved date arithmetic/Duration output differs from the generic Series Self stub.
    @overload
    def __radd__(self, other: Delta | _dt.timedelta | np.timedelta64) -> Self:
        """Apply a calendar Delta or a fixed elapsed duration.

        Parameters
        ----------
        other : Delta, timedelta or numpy.timedelta64
            Actual increment; negative values reverse the direction.

        Returns
        -------
        Self
            Date result at the original fixed unit, with genuine subclass rules.
        """
        ...

    @overload
    def __radd__(self, other: Any) -> Self | pl.Series | NotImplementedType:
        """Apply reflected Delta/duration addition through normal Python negotiation.
        
        Parameters
        ----------
        other : Any
            Actual date/duration/Delta operand under ordinary Python negotiation. Unknown operands retain
            NotImplemented/original external protocol behavior.
        
        Returns
        -------
        Self | pl.Series | NotImplementedType
            The stated native/Python output representation. Genuine external callback choices and
            exceptions retain their normal protocol.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    # Approved date arithmetic/Duration output differs from the generic Series Self stub.
    @overload
    def __sub__(self, other: Delta | _dt.timedelta | np.timedelta64) -> Self:
        """Apply a calendar Delta or a fixed elapsed duration.

        Parameters
        ----------
        other : Delta, timedelta or numpy.timedelta64
            Actual increment; negative values reverse the direction.

        Returns
        -------
        Self
            Date result at the original fixed unit, with genuine subclass rules.
        """
        ...

    @overload
    def __sub__(self, other: _dt.date | np.datetime64 | Pldt | pd.DatetimeIndex) -> pl.Series:
        """Subtract real dates and return native elapsed durations.

        Parameters
        ----------
        other : date-like scalar or column
            Actual date values; naive and aware domains cannot be mixed.

        Returns
        -------
        polars.Series
            Duration at the source unit, with original missing positions.
        """
        ...

    @overload
    def __sub__(self, other: Any) -> Self | pl.Series | NotImplementedType:
        """Subtract Delta/duration, or return a native Duration Series for dates.
        
        Parameters
        ----------
        other : Any
            Actual date/duration/Delta operand under ordinary Python negotiation. Unknown operands retain
            NotImplemented/original external protocol behavior.
        
        Returns
        -------
        Self | pl.Series | NotImplementedType
            The stated native/Python output representation. Genuine external callback choices and
            exceptions retain their normal protocol.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def pldt(self) -> _SeriesNamespace[Self]:
        """Registered eager date namespace, retaining the concrete Pldt class.

        Returns
        -------
        _SeriesNamespace[Self]
            Native date operations; ordinary replace/round/diff stay Polars methods.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/api/inherited-pldt-accessors.html#ref-pldt-native-registered-accessor
        """
        ...

class _SeriesNamespace(Generic[_PldtT]):
    """Registered eager native Series date namespace.

    Parameters
    ----------
    series : pl.Series
        Actual native eager receiver.

    Returns
    -------
    _SeriesNamespace
        Date results are Pldt; actual Pldt subclass receivers retain their class.

    Examples
    --------
    See the complete example at
    https://aresjef.github.io/rsTimes/1.1.1/guides/pldt.html#pldt-parse-event-series
    """
    def to_datetime(self, year: _OptionalField=None, month: _OptionalField=None, day: _OptionalField=None, hour: _OptionalField=None, minute: _OptionalField=None, second: _OptionalField=None, microsecond: _OptionalField=None, nanosecond: _OptionalField=None) -> _PldtT:
        """Set selected date and clock fields, fitting the day to the final month.

        Parameters
        ----------
        year : integer or one-dimensional integer collection or None
            Set the calendar year when supplied. Zero, negative and wide years depend on the
            date unit and chosen timezone.
        month : integer or one-dimensional integer collection or None
            Set the month using 1 through 12. None keeps the current month.
        day : integer or one-dimensional integer collection or None
            Set the day of the month using 1 through 31. None keeps the current day.
        hour : integer or one-dimensional integer collection or None
            Set the local hour using 0 through 23. None keeps the current hour.
        minute : integer or one-dimensional integer collection or None
            Set the local minute using 0 through 59. None keeps the current minute.
        second : integer or one-dimensional integer collection or None
            Set the local second using 0 through 59. None keeps the current second.
        microsecond : integer or one-dimensional integer collection or None
            Set the microsecond field using 0 through 999999. None keeps it. A supplied
            microsecond clears the previous nanosecond tail unless you supply nanosecond as
            well.
        nanosecond : integer or one-dimensional integer collection or None
            Set the additional nanosecond tail using 0 through 999. None keeps the tail unless
            microsecond is set.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        None keeps an optional field. An explicit zero sets a clock field to zero.
        A calendar day up to 31 is fitted to the final month's length.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-calendar.html#reader-series-month-and-fields
        """
        ...

    def to_date(self, year: _OptionalField=None, month: _OptionalField=None, day: _OptionalField=None) -> _PldtT:
        """Set selected calendar fields and keep the time of day.

        Parameters
        ----------
        year : integer or one-dimensional integer collection or None
            Set the calendar year when supplied. Zero, negative and wide years depend on the
            date unit and chosen timezone.
        month : integer or one-dimensional integer collection or None
            Set the month using 1 through 12. None keeps the current month.
        day : integer or one-dimensional integer collection or None
            Set the day of the month using 1 through 31. None keeps the current day.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        None keeps an optional field. An explicit zero sets a clock field to zero.
        A calendar day up to 31 is fitted to the final month's length.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_time(self, hour: _OptionalField=None, minute: _OptionalField=None, second: _OptionalField=None, microsecond: _OptionalField=None, nanosecond: _OptionalField=None) -> _PldtT:
        """Set selected clock fields and keep the calendar date.

        Parameters
        ----------
        hour : integer or one-dimensional integer collection or None
            Set the local hour using 0 through 23. None keeps the current hour.
        minute : integer or one-dimensional integer collection or None
            Set the local minute using 0 through 59. None keeps the current minute.
        second : integer or one-dimensional integer collection or None
            Set the local second using 0 through 59. None keeps the current second.
        microsecond : integer or one-dimensional integer collection or None
            Set the microsecond field using 0 through 999999. None keeps it. A supplied
            microsecond clears the previous nanosecond tail unless you supply nanosecond as
            well.
        nanosecond : integer or one-dimensional integer collection or None
            Set the additional nanosecond tail using 0 through 999. None keeps the tail unless
            microsecond is set.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        None keeps an optional field. An explicit zero sets a clock field to zero.
        The original calendar date stays in place.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_year(self, offset: _IntegerInput, month: _Selection=None, day: _OptionalField=None) -> _PldtT:
        """Move by calendar years and optionally choose a month and day.

        Parameters
        ----------
        offset : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        month : integer, name or one-dimensional collection or None
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_quarter(self, offset: _IntegerInput, month: _OptionalField=None, day: _OptionalField=None) -> _PldtT:
        """Move by calendar quarters and optionally choose a month within the quarter and a day.

        Parameters
        ----------
        offset : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        month : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_month(self, offset: _IntegerInput, day: _OptionalField=None) -> _PldtT:
        """Move by calendar months, fitting the day to the destination month.

        Parameters
        ----------
        offset : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_weekday(self, offset: _IntegerInput, weekday: _Selection=None) -> _PldtT:
        """Move by calendar weeks and optionally choose a weekday in the destination week.

        Parameters
        ----------
        offset : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weekday : integer, name or one-dimensional collection or None
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_day(self, offset: _IntegerInput) -> _PldtT:
        """Move by calendar days, keeping the time of day.

        Parameters
        ----------
        offset : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Supply an integer offset. Zero keeps the same day and a negative offset moves backward.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_curr_year(self, month: _Selection=None, day: _OptionalField=None) -> _PldtT:
        """Select the current calendar year and optionally choose a month and day.

        Parameters
        ----------
        month : integer, name or one-dimensional collection or None
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_prev_year(self, month: _Selection=None, day: _OptionalField=None) -> _PldtT:
        """Select the previous calendar year and optionally choose a month and day.

        Parameters
        ----------
        month : integer, name or one-dimensional collection or None
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_next_year(self, month: _Selection=None, day: _OptionalField=None) -> _PldtT:
        """Select the next calendar year and optionally choose a month and day.

        Parameters
        ----------
        month : integer, name or one-dimensional collection or None
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_curr_quarter(self, month: _OptionalField=None, day: _OptionalField=None) -> _PldtT:
        """Select the current calendar quarter and optionally choose a month within that quarter and a day.

        Parameters
        ----------
        month : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_prev_quarter(self, month: _OptionalField=None, day: _OptionalField=None) -> _PldtT:
        """Select the previous calendar quarter and optionally choose a month within that quarter and a day.

        Parameters
        ----------
        month : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_next_quarter(self, month: _OptionalField=None, day: _OptionalField=None) -> _PldtT:
        """Select the next calendar quarter and optionally choose a month within that quarter and a day.

        Parameters
        ----------
        month : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_curr_month(self, day: _OptionalField=None) -> _PldtT:
        """Select the current calendar month and fit the day to that month.

        Parameters
        ----------
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_prev_month(self, day: _OptionalField=None) -> _PldtT:
        """Select the previous calendar month and fit the day to that month.

        Parameters
        ----------
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_next_month(self, day: _OptionalField=None) -> _PldtT:
        """Select the next calendar month and fit the day to that month.

        Parameters
        ----------
        day : integer or one-dimensional integer collection or None
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-calendar.html#reader-series-month-and-fields
        """
        ...

    def to_curr_weekday(self, weekday: _Selection=None) -> _PldtT:
        """Select the current calendar week and optionally choose a weekday.

        Parameters
        ----------
        weekday : integer, name or one-dimensional collection or None
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_prev_weekday(self, weekday: _Selection=None) -> _PldtT:
        """Select the previous calendar week and optionally choose a weekday.

        Parameters
        ----------
        weekday : integer, name or one-dimensional collection or None
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_next_weekday(self, weekday: _Selection=None) -> _PldtT:
        """Select the next calendar week and optionally choose a weekday.

        Parameters
        ----------
        weekday : integer, name or one-dimensional collection or None
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_monday(self) -> _PldtT:
        """Move to Monday of the current calendar week, keeping the time of day.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_tuesday(self) -> _PldtT:
        """Move to Tuesday of the current calendar week, keeping the time of day.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_wednesday(self) -> _PldtT:
        """Move to Wednesday of the current calendar week, keeping the time of day.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_thursday(self) -> _PldtT:
        """Move to Thursday of the current calendar week, keeping the time of day.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_friday(self) -> _PldtT:
        """Move to Friday of the current calendar week, keeping the time of day.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_saturday(self) -> _PldtT:
        """Move to Saturday of the current calendar week, keeping the time of day.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_sunday(self) -> _PldtT:
        """Move to Sunday of the current calendar week, keeping the time of day.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_yesterday(self) -> _PldtT:
        """Move to the previous local calendar day, keeping the time of day.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_tomorrow(self) -> _PldtT:
        """Move to the next local calendar day, keeping the time of day.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def add(self, years: _IntegerInput=0, quarters: _IntegerInput=0, months: _IntegerInput=0, weeks: _IntegerInput=0, days: _IntegerInput=0, hours: _IntegerInput=0, minutes: _IntegerInput=0, seconds: _IntegerInput=0, milliseconds: _IntegerInput=0, microseconds: _IntegerInput=0, nanoseconds: _IntegerInput=0) -> _PldtT:
        """Add calendar months, days and clock increments in that order.

        Parameters
        ----------
        years : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        quarters : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        months : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weeks : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        days : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        hours : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        minutes : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        seconds : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        milliseconds : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        microseconds : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        nanoseconds : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Each increment is an integer. Omitted increments are zero, and negative increments reverse direction. An explicit None is invalid. The combined month change is applied before days and clock increments, with month-end adjustment on the resulting month.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series("event", ["2024-01-31 14:30", None]).str.to_datetime(time_unit="us")
        >>> print(source.pldt.add(months=1).isoformat().to_list())
        ['2024-02-29T14:30:00', None]

        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', [1, None], dtype=pl.Datetime('us'))
        >>> dates = source.pldt.add(microseconds=1, nanoseconds=-1000)
        >>> print(dates.to_physical().to_list())
        [1, None]
        """
        ...

    def sub(self, years: _IntegerInput=0, quarters: _IntegerInput=0, months: _IntegerInput=0, weeks: _IntegerInput=0, days: _IntegerInput=0, hours: _IntegerInput=0, minutes: _IntegerInput=0, seconds: _IntegerInput=0, milliseconds: _IntegerInput=0, microseconds: _IntegerInput=0, nanoseconds: _IntegerInput=0) -> _PldtT:
        """Subtract calendar months, days and clock increments in that order.

        Parameters
        ----------
        years : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        quarters : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        months : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weeks : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        days : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        hours : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        minutes : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        seconds : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        milliseconds : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        microseconds : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        nanoseconds : integer or one-dimensional integer collection
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Each increment is an integer. Omitted increments are zero, and negative increments reverse direction. An explicit None is invalid. The combined month change is applied before days and clock increments, with month-end adjustment on the resulting month.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_first_of(self, unit: str) -> _PldtT:
        """Move to the first calendar day of the selected period, keeping the time of day.

        The clock and subsecond digits are carried to the selected calendar day. A regional gap can require a valid clock on that day. If the entire selected day is missing, the operation raises an error.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-month-boundaries
        """
        ...

    def is_first_of(self, unit: str) -> pl.Series:
        """Test whether each date falls on the first calendar day of the selected period.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-month-boundaries
        """
        ...

    def to_last_of(self, unit: str) -> _PldtT:
        """Move to the last calendar day of the selected period, keeping the time of day.

        The clock and subsecond digits are carried to the selected calendar day. A regional gap can require a valid clock on that day. If the entire selected day is missing, the operation raises an error.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-month-boundaries
        """
        ...

    def is_last_of(self, unit: str) -> pl.Series:
        """Test whether each date falls on the last calendar day of the selected period.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def to_start_of(self, unit: str) -> _PldtT:
        """Move to the first valid instant of the selected period.

        Use the first or last valid time in the selected period, at the source precision. For example, a millisecond day ends at 23:59:59.999.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-month-boundaries
        """
        ...

    def is_start_of(self, unit: str) -> pl.Series:
        """Test whether each time equals the first valid instant of the selected period.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-month-boundaries
        """
        ...

    def to_end_of(self, unit: str) -> _PldtT:
        """Move to the last valid instant of the selected period in the current unit.

        Use the first or last valid time in the selected period, at the source precision. For example, a millisecond day ends at 23:59:59.999.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-month-boundaries
        """
        ...

    def is_end_of(self, unit: str) -> pl.Series:
        """Test whether each time equals the last valid instant in the current unit.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def normalize(self) -> _PldtT:
        """Return the real start of this local day, staying within the day.

        Choose the first valid instant of the source's local calendar day.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def snap(self, unit: str='s') -> _PldtT:
        """Select the nearest real period start; equal distances select later.

        Parameters
        ----------
        unit : str
            One natural Y/Q/M/W/D/h/m/min/s/ms/us/ns period or an exact saved month/weekday name; no
            arbitrary multi-step frequency or numeric weekday.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series("event", ["2024-01-02 11:59", "2024-01-02 12:00", None])
        >>> dates = source.str.to_datetime(time_unit="us").pldt.snap("D")
        >>> print(dates.isoformat().to_list())
        ['2024-01-02T00:00:00', '2024-01-03T00:00:00', None]
        """
        ...

    def fsp(self, precision: SupportsIndex) -> _PldtT:
        """Truncate the fractional second, preserving the current storage unit.

        Parameters
        ----------
        precision : SupportsIndex
            Single integer number of fractional-second digits. Negative values fail; 9 or more preserve
            existing precision without inventing finer data.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-second-grid
        """
        ...

    @property
    def year(self) -> pl.Series:
        """Signed calendar year as a nullable Int64 column.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def month(self) -> pl.Series:
        """One-based month as a nullable Int64 column.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def day(self) -> pl.Series:
        """One-based day as a nullable Int64 column.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def hour(self) -> pl.Series:
        """Hour within the local day as nullable Int64.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def minute(self) -> pl.Series:
        """Minute within the hour as nullable Int64.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def second(self) -> pl.Series:
        """Second within the minute as nullable Int64.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def microsecond(self) -> pl.Series:
        """Microsecond within the second as nullable Int64.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def nanosecond(self) -> pl.Series:
        """Additional nanosecond tail, 0 through 999, as nullable Int64.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    @property
    def weekday(self) -> pl.Series:
        """Weekday with Monday 0, as nullable Int64.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    @property
    def day_of_year(self) -> pl.Series:
        """One-based day within the local calendar year.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def days_in_month(self) -> pl.Series:
        """Number of days in the local calendar month.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def quarter(self) -> pl.Series:
        """One-based calendar quarter as nullable Int64.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def millisecond(self) -> pl.Series:
        """Millisecond within the second, from 0 through 999.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    @property
    def is_leap_year(self) -> pl.Series:
        """Whether the local year is leap; source null is False.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def isoyear(self) -> pl.Series:
        """Signed ISO week year, independently of UInt32 table capacity.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def isoweek(self) -> pl.Series:
        """One-based ISO week number.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def isoweekday(self) -> pl.Series:
        """ISO weekday with Monday 1.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def days_in_year(self) -> pl.Series:
        """Number of days in the local calendar year.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def days_bf_year(self) -> pl.Series:
        """Days before this calendar year, relative to 0001-01-01.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def days_in_quarter(self) -> pl.Series:
        """Number of calendar days in this quarter.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def days_bf_quarter(self) -> pl.Series:
        """Days in this year before the current quarter.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def day_of_quarter(self) -> pl.Series:
        """One-based day in this calendar quarter.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def days_bf_month(self) -> pl.Series:
        """Days in this year before the current month.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def day_of_month(self) -> pl.Series:
        """One-based local day of month.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_year(self, year: _IntegerInput) -> pl.Series:
        """Match scalar or equal-length integer year targets.

        Parameters
        ----------
        year : integer or one-dimensional integer collection
            An integer year or a same-length integer column paired by position. A valid
            integer outside the matching range yields False. Strings, booleans and missing targets are invalid.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Supply a valid target. A missing target, including None, raises TypeError.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        A missing source date returns False in the Boolean result.
        """
        ...

    def is_quarter(self, quarter: _IntegerInput) -> pl.Series:
        """Match scalar or equal-length integer quarter targets.

        Parameters
        ----------
        quarter : integer or one-dimensional integer collection
            Required scalar or equal-length integer quarter target. Legal nonmatches return False; missing
            targets fail even for source null.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def is_month(self, month: _QuerySelection) -> pl.Series:
        """Match integer or saved month names, by position; null is False.

        Parameters
        ----------
        month : integer, name or one-dimensional collection
            Month number or a month name in the library's default vocabulary.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Supply a valid target. A missing target, including None, raises TypeError.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        A missing source date returns False in the Boolean result.
        """
        ...

    def is_weekday(self, weekday: _QuerySelection) -> pl.Series:
        """Test for a local weekday by name or by number, with Monday as 0.

        Parameters
        ----------
        weekday : integer, name or one-dimensional collection
            Weekday number, with Monday as 0, or a weekday name in the library's default
            vocabulary.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def is_day(self, day: _IntegerInput) -> pl.Series:
        """Test whether each local day of the month equals the supplied day.

        Parameters
        ----------
        day : integer or one-dimensional integer collection
            An integer day or a same-length integer column paired by position. A valid
            integer outside the matching range yields False. Strings, booleans and missing targets are invalid.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Supply a valid target. A missing target, including None, raises TypeError.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        A missing source date returns False in the Boolean result.
        """
        ...

    def is_long_year(self) -> pl.Series:
        """Whether the local calendar year contains 53 ISO weeks; null is False.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def leap_bt_year(self, year: _IntegerInput) -> pl.Series:
        """Count leap years between row years and targets, lower inclusive.

        Parameters
        ----------
        year : integer or one-dimensional integer collection
            Required signed integer target year or exactly equal-length targets. Count leap years between
            the two years, lower inclusive and upper exclusive; missing targets fail even for null source
            dates.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        Supply a valid target. A missing target, including None, raises TypeError.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        Each count describes the years between the two inputs.
        """
        ...

    def is_dst(self) -> pl.Series:
        """Whether the native zone has nonzero DST; naive/null is False.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def utcoffset_seconds(self) -> pl.Series:
        """Actual integer UTC offset; naive and missing rows are null.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_past(self) -> pl.Series:
        """Strictly before one captured reference; Expr captures on creation.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_future(self) -> pl.Series:
        """Strictly after one captured reference; Expr captures on creation.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def isocalendar(self) -> pl.Series:
        """Return the ISO year, week, and weekday in a Struct with UInt32 fields.

        Use isoyear() to read ISO years as signed integers.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            An input date has an ISO year outside the UInt32 range.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', ['2021-01-01']).str.to_datetime(time_unit='us')
        >>> dates = source.pldt.isocalendar()
        >>> print(dates.to_list())
        [{'year': 2020, 'week': 53, 'day': 5}]
        """
        ...

    def timedf(self) -> pl.DataFrame:
        """Read the nine local calendar and clock fields.

        The fields are tm_year, tm_mon, tm_mday, tm_hour, tm_min, tm_sec,
        tm_wday, tm_yday, and tm_isdst. tm_sec is the whole second of the minute.

        Returns
        -------
        polars.DataFrame
            A Polars DataFrame with one column for each of the nine fields.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def utctimedf(self) -> pl.DataFrame:
        """Return UTC time fields; naive fields do not move and DST is zero.
        
        Returns
        -------
        pl.DataFrame
            Native nine-column time table with fixed child dtypes; source nulls remain null.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def toseconds(self, utc: _Boolean=False) -> pl.Series:
        """Return Float64 seconds in local coordinates, or UTC when requested.

        Parameters
        ----------
        utc : bool or numpy.bool_
            Use UTC coordinates when True; otherwise use local clock coordinates. A naive datetime remains
            timezone-naive.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', [0, None], dtype=pl.Datetime('us', 'Asia/Shanghai'))
        >>> dates = source.pldt.toseconds()
        >>> print(dates.to_list())
        [28800.0, None]
        """
        ...

    def tomicroseconds(self, utc: _Boolean=False) -> pl.Series:
        """Return Int64 microseconds, flooring only at this explicit output.

        Parameters
        ----------
        utc : bool or numpy.bool_
            Use UTC coordinates when True; otherwise use local clock coordinates. A naive datetime remains
            timezone-naive.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', [-1500, None], dtype=pl.Datetime('ns'))
        >>> dates = source.pldt.tomicroseconds()
        >>> print(dates.to_list())
        [-2, None]
        """
        ...

    def toordinal(self) -> pl.Series:
        """Return Int64 proleptic Gregorian day ordinals; missing stays null.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def timestamp(self) -> pl.Series:
        """Return Float64 UTC seconds; naive dates use the process local zone.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            The process local timezone is unavailable, or a naive time is repeated
            or nonexistent. Use tz_localize with an explicit ambiguous or nonexistent
            policy before calling timestamp().
        OverflowError
            A naive date's local time is outside the supported regional timezone range.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', [0, None], dtype=pl.Datetime('us', 'Asia/Shanghai'))
        >>> dates = source.pldt.timestamp()
        >>> print(dates.to_list())
        [0.0, None]
        """
        ...

    @property
    def values_naive(self) -> pl.Series:
        """Return a plain native Datetime column of local wall coordinates.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The local wall time exceeds the current tick unit's capacity,
            or the date is outside the supported regional timezone range."""
        ...

    @property
    def date(self) -> pl.Series:
        """Return a native Date column, checked against its signed32-day range.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The local date exceeds the native Date type's signed 32-bit day range,
            or the date is outside the supported regional timezone range."""
        ...

    @property
    def time(self) -> pl.Series:
        """Return a native Time column retaining the full time-of-day nanoseconds.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def isoformat(self, sep: str='T', timespec: str='auto') -> pl.Series:
        """Return ISO strings with explicit precision and colon-separated offsets.
        
        Parameters
        ----------
        sep : str
            Separator between ISO date and time, normally T.
        timespec : str
            auto/hours/minutes/seconds/milliseconds/microseconds/nanoseconds, including the approved
            h/m/min/s/ms/us/ns aliases; uppercase H and M are not accepted.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def strftime(self, format: str) -> pl.Series:
        """Return strings using native numeric/fraction fields or an eager system adapter.

        Parameters
        ----------
        format : str
            Shared strftime format. %f emits 9 digits for ns and 6 for ms/us; %.1f through %.9f emit a dot
            plus that many truncated/padded digits, and %.0f is empty. System-locale/platform directives
            are eager-only; numeric directives remain native in Expr.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', [123_456_789, None], dtype=pl.Datetime('ns'))
        >>> dates = source.pldt.strftime('%f|%.3f|%.0f')
        >>> print(dates.to_list())
        ['123456789|.123|', None]
        """
        ...

    def ctime(self) -> pl.Series:
        """Return English ctime strings, independent of the process locale.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def month_name(self, locale: str | None=None) -> pl.Series:
        """Return compiled CLDR month names; the default language is English.

        Parameters
        ----------
        locale : str or None
            Supported CLDR locale such as en_US or zh_CN; None uses English. This does not change parser
            Configs.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def weekday_name(self, locale: str | None=None) -> pl.Series:
        """Return compiled CLDR weekday names; the default language is English.

        Parameters
        ----------
        locale : str or None
            Supported CLDR locale such as en_US or zh_CN; None uses English. This does not change parser
            Configs.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def tzname(self) -> pl.Series:
        """Return the native zone abbreviation at each instant, or null if naive.
        
        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def datetime(self) -> np.ndarray:
        """Return an object array of Pydt/None, explicitly truncating to microseconds.

        Returns
        -------
        np.ndarray
            The stated native/Python output representation. Genuine external callback choices and
            exceptions retain their normal protocol.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', [1234, None], dtype=pl.Datetime('ns'))
        >>> dates = source.pldt.datetime()
        >>> print(type(dates[0]).__name__, dates[0].isoformat(), dates[1])
        Pydt 1970-01-01T00:00:00.000001 None
        """
        ...

    @property
    def timetz(self) -> np.ndarray:
        """Return an object array of standard time/None, preserving zone and fold.
        
        Returns
        -------
        np.ndarray
            The stated native/Python output representation. Genuine external callback choices and
            exceptions retain their normal protocol.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    @property
    def tzinfo(self) -> _dt.tzinfo | None:
        """Return the normalized timezone encoded by the entire column.
        
        Returns
        -------
        datetime.tzinfo or None
            None for naive dates, timezone.utc for UTC aliases, or ZoneInfo
            for another supported IANA key. Original object identity is absent
            from Polars metadata, including for empty columns."""
        ...

    @property
    def tz_available(self) -> set[str]:
        """Return region names supported by the bundled native backend.
        
        Returns
        -------
        set[str]
            A fresh set of supported keys, independent of the system ZoneInfo
            database. This does not resolve the local timezone or read dates."""
        ...

    def is_utc(self) -> bool:
        """Return whether the column's actual metadata represents UTC.
        
        Returns
        -------
        bool
            One boolean for the whole column, also for empty/all-null data.
            This query does not resolve the process-local timezone."""
        ...

    def is_local(self) -> bool:
        """Compare encoded metadata with the cached process-local zone.
        
        Returns
        -------
        bool
            False for naive dates without detecting a local zone. An aware
            column resolves the shared local service only when this is called;
            a failed lookup raises instead of silently assuming UTC."""
        ...

    def diff(self, dtobj: _DiffInput, unit: str, absolute: _Boolean=False, inclusive: str='one') -> pl.Series:
        """Count date-unit boundaries; numeric targets are seconds, not ticks.

        Parameters
        ----------
        dtobj : date-like value or one-dimensional date collection
            Source/target in this factory's stated role. Actual dtype/unit/zone and independent validity
            are preserved; a scalar broadcasts only where the named factory permits it.
        unit : str
            Boundary bucket Y/Q/M/W/D/h/m/min/s/ms/us/ns; it is not a storage-unit conversion.
        absolute : bool or numpy.bool_
            Original protocol argument, forwarded without inventing another interpretation.
        inclusive : str
            Use 'one' for the signed difference in unit boundaries, 'both' to include
            both endpoints, or 'neither' to exclude both. The native Series.diff
            compares rows with their predecessors by default.

        Returns
        -------
        pl.Series
            Native result Series with the operation's dtype and original row order/null role; it is not
            wrapped as Pldt.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', ['2024-01-03', None]).str.to_datetime(time_unit='us')
        >>> dates = source.pldt.diff('2024-01-01', 'D')
        >>> print(dates.to_list())
        [2, None]

        Using the accessor on a Pldt

        >>> from rstimes import Pldt
        >>> Pldt(["2024-01-03"]).pldt.diff("2024-01-01", "D").to_list()
        [2]
        """
        ...

    def round(self, freq: _FixedFrequency='s') -> _PldtT:
        """Round to the nearest point on a fixed time grid, breaking ties toward an even tick.

        Parameters
        ----------
        freq : str | datetime.timedelta | pandas fixed offset
            Positive fixed grid, for example '15min' or timedelta(minutes=15). With pandas
            installed, accept Timedelta and exact Nano, Micro, Milli, Second, Minute, Hour or Day
            offsets. A single value applied to the entire column.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-second-grid
        """
        ...

    def ceil(self, freq: _FixedFrequency='s') -> _PldtT:
        """Round up to the first point on a fixed time grid at or after each date.

        Parameters
        ----------
        freq : str | datetime.timedelta | pandas fixed offset
            Positive fixed grid, for example '15min' or timedelta(minutes=15). With pandas
            installed, accept Timedelta and exact Nano, Micro, Milli, Second, Minute, Hour or Day
            offsets. A single value applied to the entire column.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-second-grid
        """
        ...

    def floor(self, freq: _FixedFrequency='s') -> _PldtT:
        """Round down to the last point on a fixed time grid at or before each date.

        Parameters
        ----------
        freq : str | datetime.timedelta | pandas fixed offset
            Positive fixed grid, for example '15min' or timedelta(minutes=15). With pandas
            installed, accept Timedelta and exact Nano, Micro, Milli, Second, Minute, Hour or Day
            offsets. A single value applied to the entire column.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-second-grid
        """
        ...

    def add_delta(self, delta: _DeltaInput) -> _PldtT:
        """Apply actual Delta rules and return one final Pldt column.

        Parameters
        ----------
        delta : Delta or one-dimensional Delta collection
            Actual Delta scalar or equal-length Delta values. All absolute fields and relative nanoseconds
            remain intact; source data is not modified.

        Returns
        -------
        Pldt
            One final date column in the source unit, timezone and name. Native rules and per-row
            callbacks retain source nulls. A real whole-column callback instead owns its returned
            values and validity, including values at formerly null source positions; every returned
            value is checked for awareness, exact precision and final capacity. Its date collection
            must have the complete source length. A business subclass is constructed once.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> from rstimes import Delta
        >>> source = pl.Series('event', ['2024-01-31', None]).str.to_datetime(time_unit='us')
        >>> dates = source.pldt.add_delta(Delta(months=1))
        >>> print(dates.dt.date().cast(pl.String).to_list())
        ['2024-02-29', None]

        Using the accessor on a Pldt

        >>> from rstimes import Delta, Pldt
        >>> class Fill(Delta):
        ...     def __radd__(self, column):
        ...         return Pldt([7, None], unit="us")
        >>> Pldt([None, 0], unit="us").pldt.add_delta(Fill()).to_physical().to_list()
        [7, None]

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def sub_delta(self, delta: _DeltaInput) -> _PldtT:
        """Reverse relative Delta quantities while retaining absolute fields.

        Parameters
        ----------
        delta : Delta or one-dimensional Delta collection
            Actual Delta scalar or equal-length Delta values. All absolute fields and relative nanoseconds
            remain intact; source data is not modified.

        Returns
        -------
        Pldt
            One final date column in the source unit, timezone and name. Native rules and per-row
            callbacks retain source nulls. A real whole-column callback instead owns its returned
            values and validity, including values at formerly null source positions; every returned
            value is checked for awareness, exact precision and final capacity. Its date collection
            must have the complete source length. A business subclass is constructed once.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-arithmetic.html#reader-series-subtract-delta
        """
        ...

    def replace(self, year: _OptionalField=None, month: _OptionalField=None, day: _OptionalField=None, hour: _OptionalField=None, minute: _OptionalField=None, second: _OptionalField=None, microsecond: _OptionalField=None, nanosecond: _OptionalField=None, tzinfo: _Zone= ..., *, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Strictly merge date fields; omitted tzinfo retains, None removes the zone.

        Parameters
        ----------
        year : integer or one-dimensional integer collection or None
            Set the calendar year when supplied. Zero, negative and wide years depend on the
            date unit and chosen timezone.
        month : integer or one-dimensional integer collection or None
            Set the month using 1 through 12. None keeps the current month.
        day : integer or one-dimensional integer collection or None
            Set the day of the month using 1 through 31. None keeps the current day.
        hour : integer or one-dimensional integer collection or None
            Set the local hour using 0 through 23. None keeps the current hour.
        minute : integer or one-dimensional integer collection or None
            Set the local minute using 0 through 59. None keeps the current minute.
        second : integer or one-dimensional integer collection or None
            Set the local second using 0 through 59. None keeps the current second.
        microsecond : integer or one-dimensional integer collection or None
            Set the microsecond field using 0 through 999999. None keeps it. A supplied
            microsecond clears the previous nanosecond tail unless you supply nanosecond as
            well.
        nanosecond : integer or one-dimensional integer collection or None
            Set the additional nanosecond tail using 0 through 999. None keeps the tail unless
            microsecond is set.
        tzinfo : str, datetime.tzinfo or None
            Omit tzinfo to keep the current zone. Pass None to remove the zone while keeping the
            local clock. A supplied timezone assigns that zone to the edited clock fields.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        None keeps an optional field. An explicit zero sets a clock field to zero.
        A supplied year, month or day must form a real date.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', ['2024-01-31', None]).str.to_datetime(time_unit='us')
        >>> dates = source.pldt.replace(day=28, month=2)
        >>> print(dates.dt.date().cast(pl.String).to_list())
        ['2024-02-28', None]

        Using the accessor on a Pldt

        >>> from rstimes import Pldt
        >>> Pldt(["2024-01-31"]).pldt.replace(day=28, month=2).day.to_list()
        [28]
        """
        ...

    def __init__(self, series: pl.Series) -> None:
        """Initialize the registered native namespace.
        
        Parameters
        ----------
        series : pl.Series
            Native Polars receiver retained by its registered namespace; expression construction does not
            collect data.
        
        Returns
        -------
        None
            The existing receiver/state/namespace is initialized; no result column is returned.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def fromisoformat(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Parse complete ISO text into one native date column.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach the chosen zone to naive ISO dates and convert ISO values with a zone to it.
            With None, keep a common zone from the input if one is present.
        unit : {"ms", "us", "ns"} or None
            Without a unit, text uses us for up to six fractional digits and ns for seven
            through nine, even if the additional digits are zero. An explicit unit must represent every date without loss.
            An empty or all-null text input without a declared resolution uses ms.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-factories.html#reader-series-iso-text
        """
        ...

    def combine(self, time: _CombineTime=None, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Use this Series for dates and compose one final native Pldt.

        Parameters
        ----------
        time : time, date-like value, clock column or None
            Clock fields and an optional source zone. A Python time can supply a timezone. A
            Polars Time column supplies native nanosecond fields. A scalar None means midnight.
            Null positions in a clock column remain null.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach this timezone to the assembled local fields. With None, keep the clock's zone
            when it supplies one. A Polars Time column supplies clock fields and no zone.
        unit : {"ms", "us", "ns"} or None
            Choose ms, us or ns. None selects us, or ns when the clock supplies a nonzero
            nanosecond tail. The result must fit the output unit exactly.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-factories.html#reader-series-combine-clock
        """
        ...

    def fromordinal(self, *, tz: _Zone=None, unit: _Unit='us', name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Build dates from Gregorian day numbers, with 1 for January 1 of year 1.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach this timezone at the computed local midnight. With None, return naive dates.
        unit : {"ms", "us", "ns"}, default "us"
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback. Explicit None is not accepted.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def fromisocalendar(self, week: _CalendarInput, weekday: _CalendarInput, *, tz: _Zone=None, unit: _Unit='us', name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Build dates from ISO week-years, week numbers and weekdays.

        Parameters
        ----------
        week : integer or one-dimensional integer collection or None
            Integer day-of-year/ISO-week component, scalar or equal-length column. Values below 1 fail;
            approved upper convenience selection is retained. An explicit missing component makes a
            missing row.
        weekday : integer or one-dimensional integer collection or None
            ISO weekday: Monday 1 through Sunday 7. Values below 1 fail, values above 7 select Sunday; an
            explicit missing component makes a missing row.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach this timezone at the computed local midnight. With None, return naive dates.
        unit : {"ms", "us", "ns"}, default "us"
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback. Explicit None is not accepted.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def fromdayofyear(self, doy: _CalendarInput, *, tz: _Zone=None, unit: _Unit='us', name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Build dates from years and their one-based day numbers.

        Parameters
        ----------
        doy : integer or one-dimensional integer collection or None
            Integer day-of-year/ISO-week component, scalar or equal-length column. Values below 1 fail;
            approved upper convenience selection is retained. An explicit missing component makes a
            missing row.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach this timezone at the computed local midnight. With None, return naive dates.
        unit : {"ms", "us", "ns"}, default "us"
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback. Explicit None is not accepted.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def parse(self, *, unit: _Unit | None=None, name: str | None=None, copy: _Boolean=False, tz: _Zone=None, default: _DateValue=None, yearfirst: _Boolean | None=None, dayfirst: _Boolean | None=None, isoformat: _Boolean=True, strict: _Boolean=False, cfg: Configs | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Parse supported native data into a Pldt without a Python row UDF.

        Parameters
        ----------
        unit : {"ms", "us", "ns"} or None
            Without a unit, text uses us for up to six fractional digits and ns for seven
            through nine, even if the additional digits are zero. An explicit unit must represent every date without loss.
            Without a unit, preserve native Datetime resolution and use ns for bare ticks.
            An untyped empty or all-null input defaults to ms.
        name : str or None
            Set the result's column name. None keeps the source name when present.
            A subclass copy that returns the original cannot assign it a different name.
        copy : bool or numpy.bool_
            True isolates source date buffers; False permits safe sharing but does not promise zero-copy
            or an independent snapshot.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach the chosen zone to naive dates and convert aware dates to it while keeping
            their instants. With None, use the source timezone when the input can form a single
            zone.
        default : date-like value or None
            An independently complete fallback date, read only when needed to fill text YMD/two-digit-year
            reference. It does not supply the column clock, zone or fold.
        yearfirst : bool or numpy.bool_ or None
            Prefer the year as the first field in an ambiguous date. None uses the Configs
            setting when present, or True otherwise.
        dayfirst : bool or numpy.bool_ or None
            Prefer the day before the month in an ambiguous numeric date. None uses the Configs
            setting when present, or False otherwise.
        isoformat : bool or numpy.bool_
            Try ISO first and then shared ordinary parsing when needed; this is not ISO-only validation.
        strict : bool or numpy.bool_
            Validate explicit parsed date/clock fields and conflicts; it does not replace the regional DST
            policies.
        cfg : Configs or None
            Parser vocabulary and timezone aliases used by this call. None uses the built-in
            rules.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', ['1970-01-01T00:00:00.000000001', None])
        >>> dates = source.pldt.parse(unit='ns')
        >>> print(dates.to_physical().to_list())
        [1, None]
        """
        ...

    def strptime(self, fmt: str, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, cfg: Configs | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Match text using the shared format language and final output unit.

        Parameters
        ----------
        fmt : str
            Explicit parsing format. %f reads fractional seconds through ns; excess digits and a
            deliberately requested coarser unit truncate at this format-parse exit. %Z uses explicit
            Configs rules. Expr formats with %f require unit; timezone directives require tz.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach the chosen zone to clocks parsed without a zone and convert aware parsed
            values to it. With None, keep a common zone from the parsed input if one is present.
        unit : {"ms", "us", "ns"} or None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str or None
            Set the result's column name. None keeps the source name when present.
        cfg : Configs or None
            Parser vocabulary and timezone aliases used by this call. None uses the built-in
            rules.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', ['1970-01-01 00:00:00.123456789', None])
        >>> dates = source.pldt.strptime('%Y-%m-%d %H:%M:%S.%f', unit='ns')
        >>> print(dates.to_physical().to_list())
        [123456789, None]
        """
        ...

    def fromseconds(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Build dates from a Series of seconds measured on a local clock.

        Parameters
        ----------
        tz : str, tzinfo or None
            Attach this zone to the clock fields counted from midnight on 1970-01-01.
            With None, the clock fields remain timezone-naive.
        unit : {"ms", "us", "ns"} or None
            Store the result at this resolution. The default is "us" or "ns" if
            any value needs nanosecond precision.
        name : str or None
            Use this column name. None keeps the source name.
        ambiguous : str, bool or boolean column
            Choose how to handle a repeated local time. The default raises an error.
            Use "NaT", "infer", a boolean, or a mask aligned by position.
        nonexistent : str or datetime.timedelta
            Choose how to handle a missing local time. The default raises an error.
            Use "NaT", "shift_forward", "shift_backward", or one timedelta.

        Returns
        -------
        Pldt
            A date column with the source nulls in the same positions.

        Notes
        -----
        A requested unit must represent every result exactly. Use a finer unit
        when seconds carry additional fractional digits. Use fromtimestamp to
        convert POSIX instants into a target timezone.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> seconds = pl.Series("seconds", [1, None, -1])
        >>> dates = seconds.pldt.fromseconds(unit="ms")
        >>> dates.to_physical().to_list()
        [1000, None, -1000]
        """
        ...

    def frommicroseconds(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Build dates from integer microseconds measured on a local clock.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach this zone to the local clock fields counted from midnight on 1970-01-01. With
            None, the result is timezone-naive.
        unit : {"ms", "us", "ns"} or None
            Choose ms, us or ns for the output. None selects us. The input is always integer
            microseconds, and the result must fit the output unit exactly.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', [1, None, -1])
        >>> dates = source.pldt.frommicroseconds(unit='ns')
        >>> print(dates.to_physical().to_list())
        [1000, None, -1000]
        """
        ...

    def fromtimestamp(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None) -> _PldtT:
        """Convert POSIX seconds to clock fields in the target timezone.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Display each POSIX instant in this timezone. With None, use the system's local clock
            and return a timezone-naive column.
        unit : {"ms", "us", "ns"} or None
            Choose ms, us or ns for the output. None selects us, or ns for a value requiring
            nanosecond precision. Every value must fit the chosen resolution exactly.
        name : str or None
            Set the result's column name. None keeps the source name when present.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', [0, None])
        >>> dates = source.pldt.fromtimestamp(tz='Asia/Tokyo', unit='us')
        >>> print(dates.dt.strftime('%Y-%m-%d %H:%M %z').to_list())
        ['1970-01-01 09:00 +0900', None]
        """
        ...

    def utcfromtimestamp(self, *, unit: _Unit | None=None, name: str | None=None) -> _PldtT:
        """Convert POSIX seconds to timezone-aware UTC dates.

        Parameters
        ----------
        unit : {"ms", "us", "ns"} or None
            Choose ms, us or ns for the output. None selects us, or ns for a value requiring
            nanosecond precision. Every value must fit the chosen resolution exactly.
        name : str or None
            Set the result's column name. None keeps the source name when present.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def fromdate(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Take each source's local calendar date at midnight.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. Use the source's local
            date. With None the result is naive at midnight. An explicit zone attaches at that midnight.
        unit : {"ms", "us", "ns"} or None
            Storage resolution ms/us/ns. Date inputs default to milliseconds. Datetime columns keep
            their declared unit.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        """
        ...

    def fromdatetime(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Read the complete source clock fields and keep the source zone by default.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. Omit tz or pass None to
            keep the source timezone and instant. An explicit zone reinterprets the source's local clock
            fields in that zone.
        unit : {"ms", "us", "ns"} or None
            Storage resolution ms/us/ns. Datetime columns keep their declared unit.
        name : str or None
            Set the result's column name. None keeps the source name when present.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-factories.html#reader-series-datetime-source-zone
        """
        ...

    def as_unit(self, unit: _Unit, round_ok: _Boolean=True) -> _PldtT:
        """Convert Date/Datetime storage with explicit loss permission.

        Parameters
        ----------
        unit : {"ms", "us", "ns"}
            Required target storage unit. Choose ms, us or ns.
        round_ok : bool or numpy.bool_
            True allows this explicit rescale to floor discarded precision toward earlier ticks; False
            requires an exact conversion.

        Returns
        -------
        Pldt
            Date column with the target unit. The column name, timezone and nulls are retained.

        Raises
        ------
        TypeError
            The unit or round_ok argument has an unsupported type.
        ValueError
            The unit is unsupported, or an exact conversion would lose precision.
        OverflowError
            A value exceeds the target unit's capacity, even when rounding is allowed.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> values = pl.Series("event", [-1500, None], dtype=pl.Datetime("ns", "UTC"))
        >>> values.pldt.as_unit("us").to_physical().to_list()
        [-2, None]
        """
        ...

    def tz_localize(self, tz: _Zone, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Interpret naive clocks, or remove a timezone while keeping clocks.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. Attach the zone to
            naive local clocks. Pass None to remove the zone while keeping the local clock.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-timezones.html#reader-series-timezone-choices
        """
        ...

    def tz_convert(self, tz: _Zone) -> _PldtT:
        """Preserve actual instants; None removes the UTC timezone metadata.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. The source must be
            timezone-aware. Pass None to convert to UTC and then remove the zone. A target zone
            preserves the instant.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-timezones.html#reader-series-timezone-choices
        """
        ...

    def astimezone(self, tz: _Zone=None, *, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Convert to the target; naive input uses the process-local timezone.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. Omit tz or pass None to
            use the system local timezone. A naive source is interpreted in the local timezone.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-timezones.html#reader-series-timezone-choices
        """
        ...

    def tz_switch(self, targ_tz: _Zone, base_tz: _Zone=None, naive: _Boolean=False, *, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Convert with an explicit naive source zone, optionally removing target metadata.

        Parameters
        ----------
        targ_tz : str, datetime.tzinfo or None
            Required target timezone. Use an IANA name, ZoneInfo or a representable standard fixed
            offset. Pass None to remove the timezone and keep local clocks. A non-None target converts
            the instant. naive=True removes a target timezone after conversion.
        base_tz : str, datetime.tzinfo or None
            Source timezone for a naive date when converting to a non-None target. It is required for
            that conversion. An aware source uses its own timezone.
        naive : bool or numpy.bool_
            Remove target timezone metadata after the requested conversion when True.
        ambiguous : str, bool, numpy.bool_ or one-dimensional boolean mask
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        Pldt
            Date result with the requested metadata and validity. Existing operations keep their unit
            except explicit as_unit; source nulls remain missing and explicit localization policies may
            add nulls. Normal business subclasses follow one whole-column constructor; copy/state use
            their actual protocols.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-timezones.html#reader-series-timezone-choices
        """
        ...

class _ExprNamespace:
    """Registered native Expr date namespace; no implicit collection.

    Parameters
    ----------
    expr : pl.Expr
        Native expression receiver.

    Returns
    -------
    _ExprNamespace
        Operations return native pl.Expr, with schema fixed before execution.

    Examples
    --------
    See the complete example at
    https://aresjef.github.io/rsTimes/1.1.1/getting-started/polars-query.html#getting-started-polars-parse-null
    """
    def to_datetime(self, year: _ExprOptionalField=None, month: _ExprOptionalField=None, day: _ExprOptionalField=None, hour: _ExprOptionalField=None, minute: _ExprOptionalField=None, second: _ExprOptionalField=None, microsecond: _ExprOptionalField=None, nanosecond: _ExprOptionalField=None) -> pl.Expr:
        """Set selected date and clock fields, fitting the day to the final month.

        Parameters
        ----------
        year : integer or one-dimensional integer collection or None or polars.Expr
            Set the calendar year when supplied. Zero, negative and wide years depend on the
            date unit and chosen timezone.
        month : integer or one-dimensional integer collection or None or polars.Expr
            Set the month using 1 through 12. None keeps the current month.
        day : integer or one-dimensional integer collection or None or polars.Expr
            Set the day of the month using 1 through 31. None keeps the current day.
        hour : integer or one-dimensional integer collection or None or polars.Expr
            Set the local hour using 0 through 23. None keeps the current hour.
        minute : integer or one-dimensional integer collection or None or polars.Expr
            Set the local minute using 0 through 59. None keeps the current minute.
        second : integer or one-dimensional integer collection or None or polars.Expr
            Set the local second using 0 through 59. None keeps the current second.
        microsecond : integer or one-dimensional integer collection or None or polars.Expr
            Set the microsecond field using 0 through 999999. None keeps it. A supplied
            microsecond clears the previous nanosecond tail unless you supply nanosecond as
            well.
        nanosecond : integer or one-dimensional integer collection or None or polars.Expr
            Set the additional nanosecond tail using 0 through 999. None keeps the tail unless
            microsecond is set.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        None keeps an optional field. An explicit zero sets a clock field to zero.
        A calendar day up to 31 is fitted to the final month's length.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-calendar.html#reader-expr-month-and-fields
        """
        ...

    def to_date(self, year: _ExprOptionalField=None, month: _ExprOptionalField=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Set selected calendar fields and keep the time of day.

        Parameters
        ----------
        year : integer or one-dimensional integer collection or None or polars.Expr
            Set the calendar year when supplied. Zero, negative and wide years depend on the
            date unit and chosen timezone.
        month : integer or one-dimensional integer collection or None or polars.Expr
            Set the month using 1 through 12. None keeps the current month.
        day : integer or one-dimensional integer collection or None or polars.Expr
            Set the day of the month using 1 through 31. None keeps the current day.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        None keeps an optional field. An explicit zero sets a clock field to zero.
        A calendar day up to 31 is fitted to the final month's length.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_time(self, hour: _ExprOptionalField=None, minute: _ExprOptionalField=None, second: _ExprOptionalField=None, microsecond: _ExprOptionalField=None, nanosecond: _ExprOptionalField=None) -> pl.Expr:
        """Set selected clock fields and keep the calendar date.

        Parameters
        ----------
        hour : integer or one-dimensional integer collection or None or polars.Expr
            Set the local hour using 0 through 23. None keeps the current hour.
        minute : integer or one-dimensional integer collection or None or polars.Expr
            Set the local minute using 0 through 59. None keeps the current minute.
        second : integer or one-dimensional integer collection or None or polars.Expr
            Set the local second using 0 through 59. None keeps the current second.
        microsecond : integer or one-dimensional integer collection or None or polars.Expr
            Set the microsecond field using 0 through 999999. None keeps it. A supplied
            microsecond clears the previous nanosecond tail unless you supply nanosecond as
            well.
        nanosecond : integer or one-dimensional integer collection or None or polars.Expr
            Set the additional nanosecond tail using 0 through 999. None keeps the tail unless
            microsecond is set.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        None keeps an optional field. An explicit zero sets a clock field to zero.
        The original calendar date stays in place.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_year(self, offset: _ExprIntegerInput, month: _ExprSelection=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Move by calendar years and optionally choose a month and day.

        Parameters
        ----------
        offset : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        month : integer, name or one-dimensional collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_quarter(self, offset: _ExprIntegerInput, month: _ExprOptionalField=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Move by calendar quarters and optionally choose a month within the quarter and a day.

        Parameters
        ----------
        offset : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        month : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_month(self, offset: _ExprIntegerInput, day: _ExprOptionalField=None) -> pl.Expr:
        """Move by calendar months, fitting the day to the destination month.

        Parameters
        ----------
        offset : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        day : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_weekday(self, offset: _ExprIntegerInput, weekday: _ExprSelection=None) -> pl.Expr:
        """Move by calendar weeks and optionally choose a weekday in the destination week.

        Parameters
        ----------
        offset : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weekday : integer, name or one-dimensional collection or None or polars.Expr
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_day(self, offset: _ExprIntegerInput) -> pl.Expr:
        """Move by calendar days, keeping the time of day.

        Parameters
        ----------
        offset : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Supply an integer offset. Zero keeps the same day and a negative offset moves backward.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_curr_year(self, month: _ExprSelection=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the current calendar year and optionally choose a month and day.

        Parameters
        ----------
        month : integer, name or one-dimensional collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_prev_year(self, month: _ExprSelection=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the previous calendar year and optionally choose a month and day.

        Parameters
        ----------
        month : integer, name or one-dimensional collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_next_year(self, month: _ExprSelection=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the next calendar year and optionally choose a month and day.

        Parameters
        ----------
        month : integer, name or one-dimensional collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_curr_quarter(self, month: _ExprOptionalField=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the current calendar quarter and optionally choose a month within that quarter and a day.

        Parameters
        ----------
        month : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_prev_quarter(self, month: _ExprOptionalField=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the previous calendar quarter and optionally choose a month within that quarter and a day.

        Parameters
        ----------
        month : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_next_quarter(self, month: _ExprOptionalField=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the next calendar quarter and optionally choose a month within that quarter and a day.

        Parameters
        ----------
        month : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_curr_month(self, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the current calendar month and fit the day to that month.

        Parameters
        ----------
        day : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_prev_month(self, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the previous calendar month and fit the day to that month.

        Parameters
        ----------
        day : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_next_month(self, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the next calendar month and fit the day to that month.

        Parameters
        ----------
        day : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Optional selectors use None to keep the source position when it fits. An offset of zero still applies any supplied selectors.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-calendar.html#reader-expr-month-and-fields
        """
        ...

    def to_curr_weekday(self, weekday: _ExprSelection=None) -> pl.Expr:
        """Select the current calendar week and optionally choose a weekday.

        Parameters
        ----------
        weekday : integer, name or one-dimensional collection or None or polars.Expr
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def to_prev_weekday(self, weekday: _ExprSelection=None) -> pl.Expr:
        """Select the previous calendar week and optionally choose a weekday.

        Parameters
        ----------
        weekday : integer, name or one-dimensional collection or None or polars.Expr
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def to_next_weekday(self, weekday: _ExprSelection=None) -> pl.Expr:
        """Select the next calendar week and optionally choose a weekday.

        Parameters
        ----------
        weekday : integer, name or one-dimensional collection or None or polars.Expr
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def to_monday(self) -> pl.Expr:
        """Move to Monday of the current calendar week, keeping the time of day.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def to_tuesday(self) -> pl.Expr:
        """Move to Tuesday of the current calendar week, keeping the time of day.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def to_wednesday(self) -> pl.Expr:
        """Move to Wednesday of the current calendar week, keeping the time of day.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def to_thursday(self) -> pl.Expr:
        """Move to Thursday of the current calendar week, keeping the time of day.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def to_friday(self) -> pl.Expr:
        """Move to Friday of the current calendar week, keeping the time of day.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def to_saturday(self) -> pl.Expr:
        """Move to Saturday of the current calendar week, keeping the time of day.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def to_sunday(self) -> pl.Expr:
        """Move to Sunday of the current calendar week, keeping the time of day.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def to_yesterday(self) -> pl.Expr:
        """Move to the previous local calendar day, keeping the time of day.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def to_tomorrow(self) -> pl.Expr:
        """Move to the next local calendar day, keeping the time of day.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def add(self, years: _ExprIntegerInput=0, quarters: _ExprIntegerInput=0, months: _ExprIntegerInput=0, weeks: _ExprIntegerInput=0, days: _ExprIntegerInput=0, hours: _ExprIntegerInput=0, minutes: _ExprIntegerInput=0, seconds: _ExprIntegerInput=0, milliseconds: _ExprIntegerInput=0, microseconds: _ExprIntegerInput=0, nanoseconds: _ExprIntegerInput=0) -> pl.Expr:
        """Add calendar months, days and clock increments in that order.

        Parameters
        ----------
        years : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        quarters : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        months : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weeks : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        days : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        hours : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        minutes : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        seconds : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        milliseconds : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        microseconds : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        nanoseconds : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Each increment is an integer. Omitted increments are zero, and negative increments reverse direction. An explicit None is invalid. The combined month change is applied before days and clock increments, with month-end adjustment on the resulting month.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series("event", ["2024-01-31 14:30", None]).str.to_datetime(time_unit="us")
        >>> frame = source.to_frame()
        >>> expr = pl.col("event").pldt.add(months=1)
        >>> dates = frame.lazy().select(expr).collect()["event"]
        >>> print(dates.dt.strftime("%Y-%m-%dT%H:%M:%S").to_list())
        ['2024-02-29T14:30:00', None]

        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', [1, None], dtype=pl.Datetime('us'))])
        >>> expr = pl.col('event').pldt.add(microseconds=1, nanoseconds=-1000)
        >>> dates = frame.select(expr)['event']
        >>> print(dates.to_physical().to_list())
        [1, None]
        """
        ...

    def sub(self, years: _ExprIntegerInput=0, quarters: _ExprIntegerInput=0, months: _ExprIntegerInput=0, weeks: _ExprIntegerInput=0, days: _ExprIntegerInput=0, hours: _ExprIntegerInput=0, minutes: _ExprIntegerInput=0, seconds: _ExprIntegerInput=0, milliseconds: _ExprIntegerInput=0, microseconds: _ExprIntegerInput=0, nanoseconds: _ExprIntegerInput=0) -> pl.Expr:
        """Subtract calendar months, days and clock increments in that order.

        Parameters
        ----------
        years : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        quarters : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        months : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weeks : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        days : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        hours : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        minutes : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        seconds : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        milliseconds : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        microseconds : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        nanoseconds : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Each increment is an integer. Omitted increments are zero, and negative increments reverse direction. An explicit None is invalid. The combined month change is applied before days and clock increments, with month-end adjustment on the resulting month.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.
        """
        ...

    def to_first_of(self, unit: str) -> pl.Expr:
        """Move to the first calendar day of the selected period, keeping the time of day.

        The clock and subsecond digits are carried to the selected calendar day. A regional gap can require a valid clock on that day. If the entire selected day is missing, the operation raises an error.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-month-boundaries
        """
        ...

    def is_first_of(self, unit: str) -> pl.Expr:
        """Test whether each date falls on the first calendar day of the selected period.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-month-boundaries
        """
        ...

    def to_last_of(self, unit: str) -> pl.Expr:
        """Move to the last calendar day of the selected period, keeping the time of day.

        The clock and subsecond digits are carried to the selected calendar day. A regional gap can require a valid clock on that day. If the entire selected day is missing, the operation raises an error.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-month-boundaries
        """
        ...

    def is_last_of(self, unit: str) -> pl.Expr:
        """Test whether each date falls on the last calendar day of the selected period.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def to_start_of(self, unit: str) -> pl.Expr:
        """Move to the first valid instant of the selected period.

        Use the first or last valid time in the selected period, at the source precision. For example, a millisecond day ends at 23:59:59.999.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-month-boundaries
        """
        ...

    def is_start_of(self, unit: str) -> pl.Expr:
        """Test whether each time equals the first valid instant of the selected period.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-month-boundaries
        """
        ...

    def to_end_of(self, unit: str) -> pl.Expr:
        """Move to the last valid instant of the selected period in the current unit.

        Use the first or last valid time in the selected period, at the source precision. For example, a millisecond day ends at 23:59:59.999.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-month-boundaries
        """
        ...

    def is_end_of(self, unit: str) -> pl.Expr:
        """Test whether each time equals the last valid instant in the current unit.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def normalize(self) -> pl.Expr:
        """Return the real start of this local day, staying within the day.

        Choose the first valid instant of the source's local calendar day.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def snap(self, unit: str='s') -> pl.Expr:
        """Select the nearest real period start; equal distances select later.

        Parameters
        ----------
        unit : str
            One natural Y/Q/M/W/D/h/m/min/s/ms/us/ns period or an exact saved month/weekday name; no
            arbitrary multi-step frequency or numeric weekday.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame({"event": ["2024-01-02 11:59", "2024-01-02 12:00", None]})
        >>> expr = pl.col("event").pldt.parse(unit="us").pldt.snap("D")
        >>> print(frame.lazy().select(expr).collect()["event"].dt.strftime("%Y-%m-%dT%H:%M:%S").to_list())
        ['2024-01-02T00:00:00', '2024-01-03T00:00:00', None]
        """
        ...

    def fsp(self, precision: SupportsIndex) -> pl.Expr:
        """Truncate the fractional second, preserving the current storage unit.

        Parameters
        ----------
        precision : SupportsIndex
            Single integer number of fractional-second digits. Negative values fail; 9 or more preserve
            existing precision without inventing finer data.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-second-grid
        """
        ...

    @property
    def year(self) -> pl.Expr:
        """Signed calendar year as a nullable Int64 column.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    @property
    def month(self) -> pl.Expr:
        """One-based month as a nullable Int64 column.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    @property
    def day(self) -> pl.Expr:
        """One-based day as a nullable Int64 column.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    @property
    def hour(self) -> pl.Expr:
        """Hour within the local day as nullable Int64.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    @property
    def minute(self) -> pl.Expr:
        """Minute within the hour as nullable Int64.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    @property
    def second(self) -> pl.Expr:
        """Second within the minute as nullable Int64.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    @property
    def microsecond(self) -> pl.Expr:
        """Microsecond within the second as nullable Int64.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    @property
    def nanosecond(self) -> pl.Expr:
        """Additional nanosecond tail, 0 through 999, as nullable Int64.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    @property
    def weekday(self) -> pl.Expr:
        """Weekday with Monday 0, as nullable Int64.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    @property
    def day_of_year(self) -> pl.Expr:
        """One-based day within the local calendar year.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    @property
    def days_in_month(self) -> pl.Expr:
        """Number of days in the local calendar month.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    @property
    def quarter(self) -> pl.Expr:
        """One-based calendar quarter as nullable Int64.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    @property
    def millisecond(self) -> pl.Expr:
        """Millisecond within the second, from 0 through 999.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    @property
    def is_leap_year(self) -> pl.Expr:
        """Whether the local year is leap; source null is False.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def isoyear(self) -> pl.Expr:
        """Signed ISO week year, independently of UInt32 table capacity.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def isoweek(self) -> pl.Expr:
        """One-based ISO week number.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def isoweekday(self) -> pl.Expr:
        """ISO weekday with Monday 1.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def days_in_year(self) -> pl.Expr:
        """Number of days in the local calendar year.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def days_bf_year(self) -> pl.Expr:
        """Days before this calendar year, relative to 0001-01-01.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def days_in_quarter(self) -> pl.Expr:
        """Number of calendar days in this quarter.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def days_bf_quarter(self) -> pl.Expr:
        """Days in this year before the current quarter.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def day_of_quarter(self) -> pl.Expr:
        """One-based day in this calendar quarter.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def days_bf_month(self) -> pl.Expr:
        """Days in this year before the current month.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def day_of_month(self) -> pl.Expr:
        """One-based local day of month.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def is_year(self, year: _ExprIntegerInput) -> pl.Expr:
        """Match scalar or equal-length integer year targets.

        Parameters
        ----------
        year : integer or one-dimensional integer collection or polars.Expr
            An integer year or a same-length integer column paired by position. A valid
            integer outside the matching range yields False. Strings, booleans and missing targets are invalid.
            Use an integer-valued expression for a target supplied by the query.

        Returns
        -------
        pl.Expr
            An Expr producing a Boolean column. With a valid target, a null source date yields False.

        Raises
        ------
        TypeError
            Unsupported Python arguments, including a literal None target, fail
            when the expression is created.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        polars.exceptions.ComputeError
            If a target expression with a valid dtype yields a null, Polars raises this
            error while evaluating the rows in select or collect.

        Notes
        -----
        A scalar applies to each row. A target column must have the source length
        and is paired by position. Schema planning checks the input types, and
        a target error can report a position within the evaluated batch.
        """
        ...

    def is_quarter(self, quarter: _ExprIntegerInput) -> pl.Expr:
        """Match scalar or equal-length integer quarter targets.

        Parameters
        ----------
        quarter : integer or one-dimensional integer collection or polars.Expr
            Required scalar or equal-length integer quarter target. Legal nonmatches return False; missing
            targets fail even for source null.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def is_month(self, month: _ExprQuerySelection) -> pl.Expr:
        """Match integer or saved month names, by position; null is False.

        Parameters
        ----------
        month : integer, name or one-dimensional collection or polars.Expr
            Required month number or name from the default vocabulary. A column pairs by position.

        Returns
        -------
        pl.Expr
            An Expr producing a Boolean column. With a valid target, a null source date yields False.

        Raises
        ------
        TypeError
            Unsupported Python arguments, including a literal None target, fail
            when the expression is created.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        polars.exceptions.ComputeError
            If a target expression with a valid dtype yields a null, Polars raises this
            error while evaluating the rows in select or collect.

        Notes
        -----
        A scalar applies to each row. A target column must have the source length
        and is paired by position. Schema planning checks the input types, and
        a target error can report a position within the evaluated batch.
        """
        ...

    def is_weekday(self, weekday: _ExprQuerySelection) -> pl.Expr:
        """Test for a local weekday by name or by number, with Monday as 0.

        Parameters
        ----------
        weekday : integer, name or one-dimensional collection or polars.Expr
            Weekday number, with Monday as 0, or a weekday name in the library's default
            vocabulary.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def is_day(self, day: _ExprIntegerInput) -> pl.Expr:
        """Test whether each local day of the month equals the supplied day.

        Parameters
        ----------
        day : integer or one-dimensional integer collection or polars.Expr
            An integer day or a same-length integer column paired by position. A valid
            integer outside the matching range yields False. Strings, booleans and missing targets are invalid.
            Use an integer-valued expression for a target supplied by the query.

        Returns
        -------
        pl.Expr
            An Expr producing a Boolean column. With a valid target, a null source date yields False.

        Raises
        ------
        TypeError
            Unsupported Python arguments, including a literal None target, fail
            when the expression is created.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        polars.exceptions.ComputeError
            If a target expression with a valid dtype yields a null, Polars raises this
            error while evaluating the rows in select or collect.

        Notes
        -----
        A scalar applies to each row. A target column must have the source length
        and is paired by position. Schema planning checks the input types, and
        a target error can report a position within the evaluated batch.
        """
        ...

    def is_long_year(self) -> pl.Expr:
        """Whether the local calendar year contains 53 ISO weeks; null is False.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def leap_bt_year(self, year: _ExprIntegerInput) -> pl.Expr:
        """Count leap years between row years and targets, lower inclusive.

        Parameters
        ----------
        year : integer or one-dimensional integer collection or polars.Expr
            Required integer year or an equal-length column of years. Count leap years from the lower year inclusive to the upper year exclusive.

        Returns
        -------
        pl.Expr
            An Expr producing a nullable integer count. A null source date yields null.

        Raises
        ------
        TypeError
            Unsupported Python arguments, including a literal None target, fail
            when the expression is created.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        polars.exceptions.ComputeError
            If a target expression with a valid dtype yields a null, Polars raises this
            error while evaluating the rows in select or collect.

        Notes
        -----
        A scalar applies to each row. A target column must have the source length
        and is paired by position. Schema planning checks the input types, and
        a target error can report a position within the evaluated batch.
        """
        ...

    def is_dst(self) -> pl.Expr:
        """Whether the native zone has nonzero DST; naive/null is False.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def utcoffset_seconds(self) -> pl.Expr:
        """Actual integer UTC offset; naive and missing rows are null.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def is_past(self) -> pl.Expr:
        """Strictly before one captured reference; Expr captures on creation.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def is_future(self) -> pl.Expr:
        """Strictly after one captured reference; Expr captures on creation.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def isocalendar(self) -> pl.Expr:
        """Return the ISO year, week, and weekday in a Struct with UInt32 fields.

        Use isoyear() to read ISO years as signed integers.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression can fail during planning or evaluation. An ISO year
            outside the UInt32 range fails during select or collect.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', ['2021-01-01']).str.to_datetime(time_unit='us')])
        >>> expr = pl.col('event').pldt.isocalendar()
        >>> dates = frame.select(expr)['event']
        >>> print(dates.to_list())
        [{'year': 2020, 'week': 53, 'day': 5}]
        """
        ...

    def timedf(self) -> pl.Expr:
        """Read the nine local calendar and clock fields.

        The fields are tm_year, tm_mon, tm_mday, tm_hour, tm_min, tm_sec,
        tm_wday, tm_yday, and tm_isdst. tm_sec is the whole second of the minute.

        Returns
        -------
        pl.Expr
            A native expression. Both select and collect produce one Struct column with nine fields.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def utctimedf(self) -> pl.Expr:
        """Return UTC time fields; naive fields do not move and DST is zero.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def toseconds(self, utc: _Boolean=False) -> pl.Expr:
        """Return Float64 seconds in local coordinates, or UTC when requested.

        Parameters
        ----------
        utc : bool or numpy.bool_
            Use UTC coordinates when True; otherwise use local clock coordinates. A naive datetime remains
            timezone-naive.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', [0, None], dtype=pl.Datetime('us', 'Asia/Shanghai'))])
        >>> expr = pl.col('event').pldt.toseconds()
        >>> dates = frame.select(expr)['event']
        >>> print(dates.to_list())
        [28800.0, None]
        """
        ...

    def tomicroseconds(self, utc: _Boolean=False) -> pl.Expr:
        """Return Int64 microseconds, flooring only at this explicit output.

        Parameters
        ----------
        utc : bool or numpy.bool_
            Use UTC coordinates when True; otherwise use local clock coordinates. A naive datetime remains
            timezone-naive.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', [-1500, None], dtype=pl.Datetime('ns'))])
        >>> expr = pl.col('event').pldt.tomicroseconds()
        >>> dates = frame.select(expr)['event']
        >>> print(dates.to_list())
        [-2, None]
        """
        ...

    def toordinal(self) -> pl.Expr:
        """Return Int64 proleptic Gregorian day ordinals; missing stays null.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def timestamp(self) -> pl.Expr:
        """Return Float64 UTC seconds; naive dates use the process local zone.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        An unresolved local time or a date beyond the local zone's range fails during evaluation.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', [0, None], dtype=pl.Datetime('us', 'Asia/Shanghai'))])
        >>> expr = pl.col('event').pldt.timestamp()
        >>> dates = frame.select(expr)['event']
        >>> print(dates.to_list())
        [0.0, None]
        """
        ...

    @property
    def values_naive(self) -> pl.Expr:
        """Return a plain native Datetime column of local wall coordinates.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        A local wall time beyond the tick unit's range fails during evaluation.
        """
        ...

    @property
    def date(self) -> pl.Expr:
        """Return a native Date column, checked against its signed32-day range.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        A local date beyond the native Date range fails during evaluation.
        """
        ...

    @property
    def time(self) -> pl.Expr:
        """Return a native Time column retaining the full time-of-day nanoseconds.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def isoformat(self, sep: str='T', timespec: str='auto') -> pl.Expr:
        """Return ISO strings with explicit precision and colon-separated offsets.

        Parameters
        ----------
        sep : str
            Separator between ISO date and time, normally T.
        timespec : str
            auto/hours/minutes/seconds/milliseconds/microseconds/nanoseconds, including the approved
            h/m/min/s/ms/us/ns aliases; uppercase H and M are not accepted.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def strftime(self, format: str) -> pl.Expr:
        """Return strings using native numeric/fraction fields or an eager system adapter.

        Parameters
        ----------
        format : str
            Shared strftime format. %f emits 9 digits for ns and 6 for ms/us; %.1f through %.9f emit a dot
            plus that many truncated/padded digits, and %.0f is empty. System-locale/platform directives
            are eager-only; numeric directives remain native in Expr.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', [123_456_789, None], dtype=pl.Datetime('ns'))])
        >>> expr = pl.col('event').pldt.strftime('%f|%.3f|%.0f')
        >>> dates = frame.select(expr)['event']
        >>> print(dates.to_list())
        ['123456789|.123|', None]
        """
        ...

    def ctime(self) -> pl.Expr:
        """Return English ctime strings, independent of the process locale.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def month_name(self, locale: str | None=None) -> pl.Expr:
        """Return compiled CLDR month names; the default language is English.

        Parameters
        ----------
        locale : str or None
            Supported CLDR locale such as en_US or zh_CN; None uses English. This does not change parser
            Configs.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def weekday_name(self, locale: str | None=None) -> pl.Expr:
        """Return compiled CLDR weekday names; the default language is English.

        Parameters
        ----------
        locale : str or None
            Supported CLDR locale such as en_US or zh_CN; None uses English. This does not change parser
            Configs.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def tzname(self) -> pl.Expr:
        """Return the native zone abbreviation at each instant, or null if naive.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        polars.exceptions.ComputeError
            An expression with unsupported input or an invalid value can fail during
            planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def diff(self, dtobj: _DiffInput | pl.Expr, unit: str, absolute: _Boolean=False, inclusive: str='one') -> pl.Expr:
        """Return native Int64 boundary counts in the logical row domain.

        Parameters
        ----------
        dtobj : date-like value or one-dimensional date collection or polars.Expr
            Source/target in this factory's stated role. Actual dtype/unit/zone and independent validity
            are preserved; a scalar broadcasts only where the named factory permits it.
        unit : str
            Boundary bucket Y/Q/M/W/D/h/m/min/s/ms/us/ns; it is not a storage-unit conversion.
        absolute : bool or numpy.bool_
            Original protocol argument, forwarded without inventing another interpretation.
        inclusive : str
            Use 'one' for the signed difference in unit boundaries, 'both' to include
            both endpoints, or 'neither' to exclude both. The native Series.diff
            compares rows with their predecessors by default.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', ['2024-01-03', None]).str.to_datetime(time_unit='us')])
        >>> expr = pl.col('event').pldt.diff('2024-01-01', 'D')
        >>> dates = frame.select(expr)['event']
        >>> print(dates.to_list())
        [2, None]
        """
        ...

    def round(self, freq: _FixedFrequency='s') -> pl.Expr:
        """Round to the nearest point on a fixed time grid, breaking ties toward an even tick.

        Parameters
        ----------
        freq : str | datetime.timedelta | pandas fixed offset
            Positive fixed grid, for example '15min' or timedelta(minutes=15). With pandas
            installed, accept Timedelta and exact Nano, Micro, Milli, Second, Minute, Hour or Day
            offsets. A single value applied to the entire column.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-second-grid
        """
        ...

    def ceil(self, freq: _FixedFrequency='s') -> pl.Expr:
        """Round up to the first point on a fixed time grid at or after each date.

        Parameters
        ----------
        freq : str | datetime.timedelta | pandas fixed offset
            Positive fixed grid, for example '15min' or timedelta(minutes=15). With pandas
            installed, accept Timedelta and exact Nano, Micro, Milli, Second, Minute, Hour or Day
            offsets. A single value applied to the entire column.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-second-grid
        """
        ...

    def floor(self, freq: _FixedFrequency='s') -> pl.Expr:
        """Round down to the last point on a fixed time grid at or before each date.

        Parameters
        ----------
        freq : str | datetime.timedelta | pandas fixed offset
            Positive fixed grid, for example '15min' or timedelta(minutes=15). With pandas
            installed, accept Timedelta and exact Nano, Micro, Milli, Second, Minute, Hour or Day
            offsets. A single value applied to the entire column.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-second-grid
        """
        ...

    def add_delta(self, delta: _DeltaInput) -> pl.Expr:
        """Build a native Expr from concrete ordinary Delta snapshots.

        Parameters
        ----------
        delta : Delta or one-dimensional Delta collection
            Actual Delta scalar or equal-length Delta values. All absolute fields and relative nanoseconds
            remain intact; source data is not modified.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-calendar.html#expr-apply-concrete-delta
        """
        ...

    def sub_delta(self, delta: _DeltaInput) -> pl.Expr:
        """Build a native Expr reversing only relative Delta quantities.

        Parameters
        ----------
        delta : Delta or one-dimensional Delta collection
            Actual Delta scalar or equal-length Delta values. All absolute fields and relative nanoseconds
            remain intact; source data is not modified.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-calendar.html#reader-expr-subtract-delta
        """
        ...

    def replace(self, year: _ExprOptionalField=None, month: _ExprOptionalField=None, day: _ExprOptionalField=None, hour: _ExprOptionalField=None, minute: _ExprOptionalField=None, second: _ExprOptionalField=None, microsecond: _ExprOptionalField=None, nanosecond: _ExprOptionalField=None, tzinfo: _Zone= ..., *, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Strictly merge date fields; omitted tzinfo retains, None removes the zone.

        Parameters
        ----------
        year : integer or one-dimensional integer collection or None or polars.Expr
            Set the calendar year when supplied. Zero, negative and wide years depend on the
            date unit and chosen timezone.
        month : integer or one-dimensional integer collection or None or polars.Expr
            Set the month using 1 through 12. None keeps the current month.
        day : integer or one-dimensional integer collection or None or polars.Expr
            Set the day of the month using 1 through 31. None keeps the current day.
        hour : integer or one-dimensional integer collection or None or polars.Expr
            Set the local hour using 0 through 23. None keeps the current hour.
        minute : integer or one-dimensional integer collection or None or polars.Expr
            Set the local minute using 0 through 59. None keeps the current minute.
        second : integer or one-dimensional integer collection or None or polars.Expr
            Set the local second using 0 through 59. None keeps the current second.
        microsecond : integer or one-dimensional integer collection or None or polars.Expr
            Set the microsecond field using 0 through 999999. None keeps it. A supplied
            microsecond clears the previous nanosecond tail unless you supply nanosecond as
            well.
        nanosecond : integer or one-dimensional integer collection or None or polars.Expr
            Set the additional nanosecond tail using 0 through 999. None keeps the tail unless
            microsecond is set.
        tzinfo : str, datetime.tzinfo or None
            Omit tzinfo to keep the current zone. Pass None to remove the zone while keeping the
            local clock. A supplied timezone assigns that zone to the edited clock fields.
        ambiguous : str, bool, numpy.bool_, one-dimensional boolean mask or polars.Expr
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows. A Boolean
            expression can supply the mask.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        None keeps an optional field. An explicit zero sets a clock field to zero.
        A supplied year, month or day must form a real date.
        A scalar applies to each row. One-dimensional inputs pair by position and must match the source length, including missing rows.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', ['2024-01-31', None]).str.to_datetime(time_unit='us')])
        >>> expr = pl.col('event').pldt.replace(day=28, month=2)
        >>> dates = frame.select(expr)['event']
        >>> print(dates.dt.date().cast(pl.String).to_list())
        ['2024-02-28', None]
        """
        ...

    def __init__(self, expr: pl.Expr) -> None:
        """Initialize the registered native namespace.
        
        Parameters
        ----------
        expr : pl.Expr
            Native Polars receiver retained by its registered namespace; expression construction does not
            collect data.
        
        Returns
        -------
        None
            The existing receiver/state/namespace is initialized; no result column is returned.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def fromisoformat(self, *, tz: _Zone=None, unit: _Unit | None=None, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Parse a strict ISO String Expr with a fixed unit/timezone schema.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. Give an explicit output
            timezone if ISO text contains a timezone. This is checked when reading the values.
        unit : {"ms", "us", "ns"} or None
            Use ms/us/ns for String input, including whole-second text and String columns containing
            only nulls. This is checked when the schema is resolved. A Null input uses milliseconds if
            no unit is given.
        ambiguous : str, bool, numpy.bool_, one-dimensional boolean mask or polars.Expr
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows. A Boolean
            expression can supply the mask.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-inputs.html#reader-expr-iso-text
        """
        ...

    def combine(self, time: _CombineTime | pl.Expr=None, *, tz: _Zone=None, unit: _Unit | None=None, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Compose a date Expr with a native clock, keeping a fixed schema.

        Parameters
        ----------
        time : time, date-like value, clock column or None or polars.Expr
            Clock fields and an optional source zone. A Python time can supply a timezone. A
            Polars Time column supplies native nanosecond fields. A scalar None means midnight.
            Null positions in a clock column remain null.
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. An explicit timezone
            attaches to the combined local clock. A typed Datetime clock can supply its timezone. If a
            String clock contains a timezone, give an explicit target.
        unit : {"ms", "us", "ns"} or None
            Choose ms, us or ns. A future clock column of Time, Datetime(ns), String or
            floating-point seconds requires an explicit unit. A Python time commonly defaults to
            us. The result must fit the output unit exactly.
        ambiguous : str, bool, numpy.bool_, one-dimensional boolean mask or polars.Expr
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows. A Boolean
            expression can supply the mask.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-inputs.html#reader-expr-combine-clock
        """
        ...

    def fromordinal(self, *, tz: _Zone=None, unit: _Unit='us', ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Build dates from Gregorian day numbers, with 1 for January 1 of year 1.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach this timezone at the computed local midnight. With None, return naive dates.
        unit : {"ms", "us", "ns"}, default "us"
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback. Explicit None is not accepted.
        ambiguous : str, bool, numpy.bool_, one-dimensional boolean mask or polars.Expr
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows. A Boolean
            expression can supply the mask.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def fromisocalendar(self, week: _ExprCalendarInput, weekday: _ExprCalendarInput, *, tz: _Zone=None, unit: _Unit='us', ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Build dates from ISO week-years, week numbers and weekdays.

        Parameters
        ----------
        week : integer or one-dimensional integer collection or None or polars.Expr
            Integer day-of-year/ISO-week component, scalar or equal-length column. Values below 1 fail;
            approved upper convenience selection is retained. An explicit missing component makes a
            missing row.
        weekday : integer or one-dimensional integer collection or None or polars.Expr
            ISO weekday: Monday 1 through Sunday 7. Values below 1 fail, values above 7 select Sunday; an
            explicit missing component makes a missing row.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach this timezone at the computed local midnight. With None, return naive dates.
        unit : {"ms", "us", "ns"}, default "us"
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback. Explicit None is not accepted.
        ambiguous : str, bool, numpy.bool_, one-dimensional boolean mask or polars.Expr
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows. A Boolean
            expression can supply the mask.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def fromdayofyear(self, doy: _ExprCalendarInput, *, tz: _Zone=None, unit: _Unit='us', ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Build dates from years and their one-based day numbers.

        Parameters
        ----------
        doy : integer or one-dimensional integer collection or None or polars.Expr
            Integer day-of-year/ISO-week component, scalar or equal-length column. Values below 1 fail;
            approved upper convenience selection is retained. An explicit missing component makes a
            missing row.
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach this timezone at the computed local midnight. With None, return naive dates.
        unit : {"ms", "us", "ns"}, default "us"
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback. Explicit None is not accepted.
        ambiguous : str, bool, numpy.bool_, one-dimensional boolean mask or polars.Expr
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows. A Boolean
            expression can supply the mask.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def parse(self, *, unit: _Unit | None=None, tz: _Zone=None, default: _DateValue=None, yearfirst: _Boolean | None=None, dayfirst: _Boolean | None=None, isoformat: _Boolean=True, strict: _Boolean=False, cfg: Configs | None=None, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Freeze shared String parsing rules and a static output schema.

        Parameters
        ----------
        unit : {"ms", "us", "ns"} or None
            Use ms/us/ns for String input, even for a String column containing only nulls. Without a
            unit, Datetime keeps its declared unit, Date and Null use milliseconds, and numeric ticks
            use nanoseconds. A missing unit for String is rejected when the schema is resolved.
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. Give an explicit output
            timezone if text contains a timezone. This is checked when reading the values.
        default : date-like value or None
            Supply a complete fallback date. The expression prepares it at creation and uses it
            for missing calendar fields or a two-digit year. Clock, timezone and fold come from the input.
        yearfirst : bool or numpy.bool_ or None
            Prefer the year as the first field in an ambiguous date. None uses the Configs
            setting when present, or True otherwise.
        dayfirst : bool or numpy.bool_ or None
            Prefer the day before the month in an ambiguous numeric date. None uses the Configs
            setting when present, or False otherwise.
        isoformat : bool or numpy.bool_
            Try ISO first and then shared ordinary parsing when needed; this is not ISO-only validation.
        strict : bool or numpy.bool_
            Validate explicit parsed date/clock fields and conflicts; it does not replace the regional DST
            policies.
        cfg : Configs or None
            Shared Configs word/region rules. None uses the existing defaults; Expr freezes effective
            rules when it is created.
        ambiguous : str, bool, numpy.bool_, one-dimensional boolean mask or polars.Expr
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows. A Boolean
            expression can supply the mask.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', ['1970-01-01T00:00:00.000000001', None])])
        >>> expr = pl.col('event').pldt.parse(unit='ns')
        >>> dates = frame.select(expr)['event']
        >>> print(dates.to_physical().to_list())
        [1, None]
        """
        ...

    def strptime(self, fmt: str, *, tz: _Zone=None, unit: _Unit | None=None, cfg: Configs | None=None, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Parse text with a format and a known output unit.

        Parameters
        ----------
        fmt : str
            Parsing format. An active %f reads fractional seconds through nanoseconds. A literal %%f
            matches text. %Z uses the explicit Configs rules.
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. Formats with an active
            timezone directive require an explicit output timezone when creating the expression.
        unit : {"ms", "us", "ns"} or None
            Use ms/us/ns. An active %f fractional-second directive requires a unit when creating the
            expression. Formats without that directive default to microseconds, including a literal %%f.
            Choosing a coarser unit truncates fractional digits at output.
        cfg : Configs or None
            Shared Configs word/region rules. None uses the existing defaults; Expr freezes effective
            rules when it is created.
        ambiguous : str, bool, numpy.bool_, one-dimensional boolean mask or polars.Expr
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows. A Boolean
            expression can supply the mask.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', ['1970-01-01 00:00:00.123456789', None])])
        >>> expr = pl.col('event').pldt.strptime('%Y-%m-%d %H:%M:%S.%f', unit='ns')
        >>> dates = frame.select(expr)['event']
        >>> print(dates.to_physical().to_list())
        [123456789, None]
        """
        ...

    def fromseconds(self, *, tz: _Zone=None, unit: _Unit | None=None, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Build a date expression from a column of seconds measured on a local clock.

        Parameters
        ----------
        tz : str, tzinfo or None
            Attach this zone to the clock fields counted from midnight on 1970-01-01.
            With None, the clock fields remain timezone-naive.
        unit : {"ms", "us", "ns"} or None
            Store the result at this resolution. An integer column defaults to
            "us". Give a unit for a floating-point column so Polars can plan its dtype.
        ambiguous : str, bool or boolean column
            Choose how to handle a repeated local time. The default raises an error.
            Use "NaT", "infer", a boolean, or a same-length boolean mask, including a Boolean expression.
        nonexistent : str or datetime.timedelta
            Choose how to handle a missing local time. The default raises an error.
            Use "NaT", "shift_forward", "shift_backward", or one timedelta.

        Returns
        -------
        polars.Expr
            A native expression that evaluates to dates with the source column name
            and null positions.

        Notes
        -----
        A requested unit must represent every result exactly. Use a finer unit
        when seconds carry additional fractional digits. Python option errors can
        occur when the expression is created. Polars reports schema and row errors
        when it plans or evaluates the expression. Use fromtimestamp to convert
        POSIX instants into a target timezone.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame({"seconds": [1, None, -1]})
        >>> expr = pl.col("seconds").pldt.fromseconds(unit="ms")
        >>> dates = frame.select(expr)["seconds"]
        >>> dates.to_physical().to_list()
        [1000, None, -1000]
        """
        ...

    def frommicroseconds(self, *, tz: _Zone=None, unit: _Unit | None=None, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Build dates from integer microseconds measured on a local clock.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach this zone to the local clock fields counted from midnight on 1970-01-01. With
            None, the result is timezone-naive.
        unit : {"ms", "us", "ns"} or None
            Choose ms, us or ns for the output. None selects us. The input is an integer
            microsecond column, and the result must fit the output unit exactly.
        ambiguous : str, bool, numpy.bool_, one-dimensional boolean mask or polars.Expr
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows. A Boolean
            expression can supply the mask.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', [1, None, -1])])
        >>> expr = pl.col('event').pldt.frommicroseconds(unit='ns')
        >>> dates = frame.select(expr)['event']
        >>> print(dates.to_physical().to_list())
        [1000, None, -1000]
        """
        ...

    def fromtimestamp(self, *, tz: _Zone=None, unit: _Unit | None=None) -> pl.Expr:
        """Convert POSIX seconds to clock fields in the target timezone.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Display each POSIX instant in this timezone. With None, use the system's local clock
            and return a timezone-naive column.
        unit : {"ms", "us", "ns"} or None
            Choose ms, us or ns for the output. An integer source defaults to us. Give an
            explicit unit for floating-point seconds. Every value must fit the chosen resolution
            exactly.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', [0, None])])
        >>> expr = pl.col('event').pldt.fromtimestamp(tz='Asia/Tokyo', unit='us')
        >>> dates = frame.select(expr)['event']
        >>> print(dates.dt.strftime('%Y-%m-%d %H:%M %z').to_list())
        ['1970-01-01 09:00 +0900', None]
        """
        ...

    def utcfromtimestamp(self, *, unit: _Unit | None=None) -> pl.Expr:
        """Convert POSIX seconds to timezone-aware UTC dates.

        Parameters
        ----------
        unit : {"ms", "us", "ns"} or None
            Choose ms, us or ns for the output. An integer source defaults to us. Give an
            explicit unit for floating-point seconds. Every value must fit the chosen resolution
            exactly.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def fromdate(self, *, tz: _Zone=None, unit: _Unit | None=None, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Take each source's local calendar date at midnight.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. Use the source's local
            date. With None the result is naive at midnight. An explicit zone attaches at that midnight.
        unit : {"ms", "us", "ns"} or None
            Storage resolution ms/us/ns. Date inputs default to milliseconds. Datetime columns keep
            their declared unit.
        ambiguous : str, bool, numpy.bool_, one-dimensional boolean mask or polars.Expr
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows. A Boolean
            expression can supply the mask.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        ...

    def fromdatetime(self, *, tz: _Zone=None, unit: _Unit | None=None, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Read the complete source clock fields and keep the source zone by default.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. Omit tz or pass None to
            keep the source timezone and instant. An explicit zone reinterprets the source's local clock
            fields in that zone.
        unit : {"ms", "us", "ns"} or None
            Storage resolution ms/us/ns. Datetime columns keep their declared unit.
        ambiguous : str, bool, numpy.bool_, one-dimensional boolean mask or polars.Expr
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows. A Boolean
            expression can supply the mask.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-inputs.html#reader-expr-datetime-source-zone
        """
        ...

    def as_unit(self, unit: _Unit, round_ok: _Boolean=True) -> pl.Expr:
        """Return an Expr with statically selected ms/us/ns resolution.

        Parameters
        ----------
        unit : {"ms", "us", "ns"}
            Required target storage unit. Choose ms, us or ns.
        round_ok : bool or numpy.bool_
            True allows this explicit rescale to floor discarded precision toward earlier ticks; False
            requires an exact conversion.

        Returns
        -------
        pl.Expr
            Native Polars expression. Evaluate it to obtain a Polars Series with the target unit. The
            column name, timezone and nulls are retained.

        Raises
        ------
        TypeError
            Creating the expression rejects an unsupported type for unit or round_ok.
        ValueError
            Creating the expression rejects any unit string outside ms, us and ns.
        polars.exceptions.ComputeError
            During select or collect, a value would lose precision with round_ok=False,
            or would exceed the target unit's capacity even when rounding is allowed.

        Notes
        -----
        Schema planning for a Datetime input exposes the target unit and preserves
        the timezone without converting any row values. A conversion error can
        report the position within the batch being evaluated.

        Examples
        --------
        >>> import polars as pl
        >>> import rstimes.pldt
        >>> values = pl.Series("event", [-1500, None], dtype=pl.Datetime("ns", "UTC"))
        >>> frame = pl.DataFrame([values])
        >>> converted = pl.col("event").pldt.as_unit("us")
        >>> frame.select(converted)["event"].to_physical().to_list()
        [-2, None]
        >>> frame.lazy().select(converted).collect()["event"].to_physical().to_list()
        [-2, None]
        """
        ...

    def tz_localize(self, tz: _Zone, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Interpret naive clocks, or remove a timezone while keeping clocks.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. Attach the zone to
            naive local clocks. Pass None to remove the zone while keeping the local clock.
        ambiguous : str, bool, numpy.bool_, one-dimensional boolean mask or polars.Expr
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows. A Boolean
            expression can supply the mask.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-timezones.html#reader-expr-timezone-choices
        """
        ...

    def tz_convert(self, tz: _Zone) -> pl.Expr:
        """Preserve actual instants; None removes the UTC timezone metadata.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. The source must be
            timezone-aware. Pass None to convert to UTC and then remove the zone. A target zone
            preserves the instant.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-timezones.html#reader-expr-timezone-choices
        """
        ...

    def astimezone(self, tz: _Zone=None, *, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Convert to the target; naive input uses the process-local timezone.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, ZoneInfo or a representable standard fixed offset. Omit tz or pass None to
            use the system local timezone. A naive source is interpreted in the local timezone.
        ambiguous : str, bool, numpy.bool_, one-dimensional boolean mask or polars.Expr
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows. A Boolean
            expression can supply the mask.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-timezones.html#reader-expr-timezone-choices
        """
        ...

    def tz_switch(self, targ_tz: _Zone, base_tz: _Zone=None, naive: _Boolean=False, *, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Convert with an explicit naive source zone, optionally removing target metadata.

        Parameters
        ----------
        targ_tz : str, datetime.tzinfo or None
            Required target timezone. Use an IANA name, ZoneInfo or a representable standard fixed
            offset. Pass None to remove the timezone and keep local clocks. A non-None target converts
            the instant. naive=True removes a target timezone after conversion.
        base_tz : str, datetime.tzinfo or None
            Source timezone for a naive date when converting to a non-None target. It is required for
            that conversion. An aware source uses its own timezone. A supplied base_tz is validated
            before the input schema is known.
        naive : bool or numpy.bool_
            Remove target timezone metadata after the requested conversion when True.
        ambiguous : str, bool, numpy.bool_, one-dimensional boolean mask or polars.Expr
            Choose 'raise' (default), 'NaT', 'infer', a boolean or a same-length boolean mask.
            True chooses the daylight-saving side according to the zone's transition rules, and
            False chooses the other side. Infer uses the order of the input rows. A Boolean
            expression can supply the mask.
        nonexistent : str or datetime.timedelta
            Choose 'raise' (default), 'NaT', 'shift_forward', 'shift_backward', or a single
            timedelta. The shift choices use the closest valid boundary at the current
            precision.

        Returns
        -------
        pl.Expr
            A native expression evaluated by Polars in select or collect.

        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.

        Notes
        -----
        In a Polars query, invalid Python options can fail when the expression is created.
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-timezones.html#reader-expr-timezone-choices
        """
        ...

