"""Typed native Pldt columns and registered Polars namespaces.

Dynamic pl.Series/pl.Expr namespace discovery remains owned by Polars.
Use Pldt for concrete eager types; no custom expression container exists.
"""
from __future__ import annotations
from typing import Generic, TypeVar
from types import NotImplementedType
import numpy as np
import polars as pl
import pandas as pd
from .delta import Delta
from .parser import Configs
from typing import Any, Literal, SupportsIndex, SupportsFloat, Self, TypeAlias, overload
from collections.abc import Iterable
from types import NotImplementedType
import datetime as _dt

_Unit: TypeAlias = Literal["ms", "us", "ns"]
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
    """A real Polars Series subclass with shared native date rules.
    
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
    
    Examples
    --------
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
    """
    def to_datetime(self, year: _OptionalField=None, month: _OptionalField=None, day: _OptionalField=None, hour: _OptionalField=None, minute: _OptionalField=None, second: _OptionalField=None, microsecond: _OptionalField=None, nanosecond: _OptionalField=None) -> Self:
        """Merge legal fields once; fit a legal day intent to the final month.
        
        Parameters
        ----------
        year : _OptionalField
            Optional integer field/selector. None retains the source. Year may be zero/negative/wide
            within the native unit and regional backend capacity. Strict replace requires a real resulting
            date; calendar conveniences keep their separate valid upper-selection/month-end rules.
        month : _OptionalField
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _OptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        hour : _OptionalField
            Optional integer field/selector. None retains the source. Hour is 0-23. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        minute : _OptionalField
            Optional integer field/selector. None retains the source. Minute is 0-59. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        second : _OptionalField
            Optional integer field/selector. None retains the source. Second is 0-59. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        microsecond : _OptionalField
            Optional integer field/selector. None retains the source. Microsecond is 0-999999; setting it
            clears the old ns tail unless nanosecond is supplied. Strict replace requires a real resulting
            date; calendar conveniences keep their separate valid upper-selection/month-end rules.
        nanosecond : _OptionalField
            Optional integer field/selector. None retains the source. Nanosecond is the additional 0-999
            tail; zero explicitly clears it. Strict replace requires a real resulting date; calendar
            conveniences keep their separate valid upper-selection/month-end rules.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_date(self, year: _OptionalField=None, month: _OptionalField=None, day: _OptionalField=None) -> Self:
        """Merge legal fields once; fit a legal day intent to the final month.
        
        Parameters
        ----------
        year : _OptionalField
            Optional integer field/selector. None retains the source. Year may be zero/negative/wide
            within the native unit and regional backend capacity. Strict replace requires a real resulting
            date; calendar conveniences keep their separate valid upper-selection/month-end rules.
        month : _OptionalField
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _OptionalField
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_time(self, hour: _OptionalField=None, minute: _OptionalField=None, second: _OptionalField=None, microsecond: _OptionalField=None, nanosecond: _OptionalField=None) -> Self:
        """Merge legal fields once; fit a legal day intent to the final month.
        
        Parameters
        ----------
        hour : _OptionalField
            Optional integer field/selector. None retains the source. Hour is 0-23. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        minute : _OptionalField
            Optional integer field/selector. None retains the source. Minute is 0-59. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        second : _OptionalField
            Optional integer field/selector. None retains the source. Second is 0-59. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        microsecond : _OptionalField
            Optional integer field/selector. None retains the source. Microsecond is 0-999999; setting it
            clears the old ns tail unless nanosecond is supplied. Strict replace requires a real resulting
            date; calendar conveniences keep their separate valid upper-selection/month-end rules.
        nanosecond : _OptionalField
            Optional integer field/selector. None retains the source. Nanosecond is the additional 0-999
            tail; zero explicitly clears it. Strict replace requires a real resulting date; calendar
            conveniences keep their separate valid upper-selection/month-end rules.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_year(self, offset: _IntegerInput, month: _Selection=None, day: _OptionalField=None) -> Self:
        """Move local calendar periods, retaining precision and fitting month end.
        
        Parameters
        ----------
        offset : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        month : _Selection
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _OptionalField
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_quarter(self, offset: _IntegerInput, month: _OptionalField=None, day: _OptionalField=None) -> Self:
        """Move local calendar periods, retaining precision and fitting month end.
        
        Parameters
        ----------
        offset : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        month : _OptionalField
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : _OptionalField
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_month(self, offset: _IntegerInput, day: _OptionalField=None) -> Self:
        """Move local calendar periods, retaining precision and fitting month end.
        
        Parameters
        ----------
        offset : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        day : _OptionalField
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_weekday(self, offset: _IntegerInput, weekday: _Selection=None) -> Self:
        """Move local calendar periods, retaining precision and fitting month end.
        
        Parameters
        ----------
        offset : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weekday : _Selection
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_day(self, offset: _IntegerInput) -> Self:
        """Move local calendar periods, retaining precision and fitting month end.
        
        Parameters
        ----------
        offset : _IntegerInput
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_curr_year(self, month: _Selection=None, day: _OptionalField=None) -> Self:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _Selection
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _OptionalField
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_prev_year(self, month: _Selection=None, day: _OptionalField=None) -> Self:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _Selection
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _OptionalField
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_next_year(self, month: _Selection=None, day: _OptionalField=None) -> Self:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _Selection
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _OptionalField
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_curr_quarter(self, month: _OptionalField=None, day: _OptionalField=None) -> Self:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _OptionalField
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : _OptionalField
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_prev_quarter(self, month: _OptionalField=None, day: _OptionalField=None) -> Self:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _OptionalField
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : _OptionalField
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_next_quarter(self, month: _OptionalField=None, day: _OptionalField=None) -> Self:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _OptionalField
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : _OptionalField
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_curr_month(self, day: _OptionalField=None) -> Self:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        day : _OptionalField
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_prev_month(self, day: _OptionalField=None) -> Self:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        day : _OptionalField
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_next_month(self, day: _OptionalField=None) -> Self:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        day : _OptionalField
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_curr_weekday(self, weekday: _Selection=None) -> Self:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        weekday : _Selection
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_prev_weekday(self, weekday: _Selection=None) -> Self:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        weekday : _Selection
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_next_weekday(self, weekday: _Selection=None) -> Self:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        weekday : _Selection
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_monday(self) -> Self:
        """Select this week's monday, using Monday as day zero.
        
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

    def to_tuesday(self) -> Self:
        """Select this week's tuesday, using Monday as day zero.
        
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

    def to_wednesday(self) -> Self:
        """Select this week's wednesday, using Monday as day zero.
        
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

    def to_thursday(self) -> Self:
        """Select this week's thursday, using Monday as day zero.
        
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

    def to_friday(self) -> Self:
        """Select this week's friday, using Monday as day zero.
        
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

    def to_saturday(self) -> Self:
        """Select this week's saturday, using Monday as day zero.
        
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

    def to_sunday(self) -> Self:
        """Select this week's sunday, using Monday as day zero.
        
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

    def to_yesterday(self) -> Self:
        """Move one local calendar day, retaining clock and nanoseconds.
        
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

    def to_tomorrow(self) -> Self:
        """Move one local calendar day, retaining clock and nanoseconds.
        
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

    def add(self, years: _IntegerInput=0, quarters: _IntegerInput=0, months: _IntegerInput=0, weeks: _IntegerInput=0, days: _IntegerInput=0, hours: _IntegerInput=0, minutes: _IntegerInput=0, seconds: _IntegerInput=0, milliseconds: _IntegerInput=0, microseconds: _IntegerInput=0, nanoseconds: _IntegerInput=0) -> Self:
        """Combine integer calendar increments before final precision/capacity checks.
        
        Parameters
        ----------
        years : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        quarters : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        months : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weeks : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        days : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        hours : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        minutes : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        seconds : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        milliseconds : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        microseconds : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        nanoseconds : _IntegerInput
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar.
        
        Examples
        --------
        >>> Pldt([1], unit="us").add(microseconds=1, nanoseconds=-1000).to_physical().to_list()
        [1]"""
        ...

    def sub(self, years: _IntegerInput=0, quarters: _IntegerInput=0, months: _IntegerInput=0, weeks: _IntegerInput=0, days: _IntegerInput=0, hours: _IntegerInput=0, minutes: _IntegerInput=0, seconds: _IntegerInput=0, milliseconds: _IntegerInput=0, microseconds: _IntegerInput=0, nanoseconds: _IntegerInput=0) -> Self:
        """Combine integer calendar increments before final precision/capacity checks.
        
        Parameters
        ----------
        years : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        quarters : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        months : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weeks : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        days : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        hours : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        minutes : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        seconds : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        milliseconds : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        microseconds : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        nanoseconds : _IntegerInput
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_first_of(self, unit: str) -> Self:
        """Select a calendar boundary while preserving date unit and timezone.
        
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_first_of(self, unit: str) -> pl.Series:
        """Query the actual calendar boundary; missing source dates are False.
        
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_last_of(self, unit: str) -> Self:
        """Select a calendar boundary while preserving date unit and timezone.
        
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_last_of(self, unit: str) -> pl.Series:
        """Query the actual calendar boundary; missing source dates are False.
        
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_start_of(self, unit: str) -> Self:
        """Select a calendar boundary while preserving date unit and timezone.
        
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_start_of(self, unit: str) -> pl.Series:
        """Query the actual calendar boundary; missing source dates are False.
        
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_end_of(self, unit: str) -> Self:
        """Select a calendar boundary while preserving date unit and timezone.
        
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_end_of(self, unit: str) -> pl.Series:
        """Query the actual calendar boundary; missing source dates are False.
        
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def normalize(self) -> Self:
        """Return the real start of this local day, staying within the day.
        
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
        >>> Pldt(["1970-01-01 12:00:00"], unit="us").snap("D").to_physical().to_list()
        [86400000000]"""
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
            The true final result exceeds the current unit/target capacity."""
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
        """Additional nanosecond tail, 0 through999, as nullable Int64.
        
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
    def weekday(self) -> pl.Series:
        """Weekday with Monday0, as nullable Int64.
        
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
        """Millisecond within the second, from0 through999.
        
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
        """ISO weekday with Monday1.
        
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
        """Days before this calendar year, relative to0001-01-01.
        
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
        year : _IntegerInput
            Required scalar or equal-length target; legal nonmatching numeric values return False. Missing
            targets fail even for source null; unknown/empty saved month names fail instead of silently
            returning False.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def is_quarter(self, quarter: _IntegerInput) -> pl.Series:
        """Match scalar or equal-length integer quarter targets.
        
        Parameters
        ----------
        quarter : _IntegerInput
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_month(self, month: _QuerySelection) -> pl.Series:
        """Match integer or saved month names, by position; null is False.
        
        Parameters
        ----------
        month : _QuerySelection
            Required scalar or equal-length target; legal nonmatching numeric values return False. Missing
            targets fail even for source null; unknown/empty saved month names fail instead of silently
            returning False.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def is_weekday(self, weekday: _QuerySelection) -> pl.Series:
        """Match integer or saved weekday names, with Monday0.
        
        Parameters
        ----------
        weekday : _QuerySelection
            Required scalar or equal-length integer/saved-name target, Monday 0. Legal nonmatching
            integers return False; missing/unknown/empty targets fail even for source null.
        
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

    def is_day(self, day: _IntegerInput) -> pl.Series:
        """Match scalar or equal-length integer day targets.
        
        Parameters
        ----------
        day : _IntegerInput
            Required scalar or equal-length target; legal nonmatching numeric values return False. Missing
            targets fail even for source null; unknown/empty saved month names fail instead of silently
            returning False.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def is_long_year(self) -> pl.Series:
        """Whether the calendar year has53 ISO weeks; null is False.
        
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
        year : _IntegerInput
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
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
        """Return year/week/day as a native Struct with UInt32 fields.
        
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
        >>> Pldt(["2021-01-01"]).isocalendar().to_list()
        [{'year': 2020, 'week': 53, 'day': 5}]"""
        ...

    def timedf(self) -> pl.DataFrame:
        """Return local time fields as an eager DataFrame or native Struct Expr.
        
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
        utc : _Boolean
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
        >>> x = Pldt(["1970-01-01 08:00:00"], tz="Asia/Shanghai", unit="us")
        >>> x.toseconds().to_list()
        [28800.0]
        >>> x.toseconds(utc=True).to_list()
        [0.0]"""
        ...

    def tomicroseconds(self, utc: _Boolean=False) -> pl.Series:
        """Return Int64 microseconds, flooring only at this explicit output.
        
        Parameters
        ----------
        utc : _Boolean
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
        >>> Pldt(["1970-01-01 00:00:00.000001"], unit="ns").tomicroseconds().to_list()
        [1]"""
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
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        
        Examples
        --------
        >>> Pldt(["1970-01-01 08:00:00"], tz="Asia/Shanghai").timestamp().to_list()
        [0.0]"""
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
            The true final result exceeds the current unit/target capacity."""
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
            The true final result exceeds the current unit/target capacity."""
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
            H/M/s/ms/us/ns aliases.
        
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
        >>> Pldt([123456789], unit="ns").strftime("%f|%.3f|%.0f").to_list()
        ['123456789|.123|']"""
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
        locale : str | None
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def weekday_name(self, locale: str | None=None) -> pl.Series:
        """Return compiled CLDR weekday names; the default language is English.
        
        Parameters
        ----------
        locale : str | None
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
            The true final result exceeds the current unit/target capacity."""
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
        >>> type(Pldt([0], unit="ns").datetime()[0]).__name__
        'Pydt'"""
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
        """Initialize the registered native namespace.
        
        Parameters
        ----------
        data : _DateCollection
            Legal one-dimensional date collection; text/date/datetime/NumPy scalars/numeric ticks and
            supported native columns may mix. No scalar, mapping, set, table, nested row or automatic
            flattening.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        copy : _Boolean
            True isolates source date buffers; False permits safe sharing but does not promise zero-copy
            or an independent snapshot.
        default : _DateValue
            An independently complete fallback date, read only when needed to fill text YMD/two-digit-year
            reference. It does not supply the column clock, zone or fold.
        yearfirst : _Boolean | None
            Explicit non-None boolean wins over Configs. Without either, yearfirst=True/dayfirst=False;
            False is an explicit preference.
        dayfirst : _Boolean | None
            Explicit non-None boolean wins over Configs. Without either, yearfirst=True/dayfirst=False;
            False is an explicit preference.
        isoformat : _Boolean
            Try ISO first and then shared ordinary parsing when needed; this is not ISO-only validation.
        strict : _Boolean
            Validate explicit parsed date/clock fields and conflicts; it does not replace the regional DST
            policies.
        cfg : Configs | None
            Shared Configs word/region rules. None uses the existing defaults; Expr freezes effective
            rules when it is created.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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

    @classmethod
    def parse(cls, data: _DateCollection, *, unit: _Unit | None=None, name: str | None=None, copy: _Boolean=False, tz: _Zone=None, default: _DateValue=None, yearfirst: _Boolean | None=None, dayfirst: _Boolean | None=None, isoformat: _Boolean=True, strict: _Boolean=False, cfg: Configs | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Construct a date column through the same shared native input rules.
        
        Parameters
        ----------
        data : _DateCollection
            Legal one-dimensional date collection; text/date/datetime/NumPy scalars/numeric ticks and
            supported native columns may mix. No scalar, mapping, set, table, nested row or automatic
            flattening.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        copy : _Boolean
            True isolates source date buffers; False permits safe sharing but does not promise zero-copy
            or an independent snapshot.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        default : _DateValue
            An independently complete fallback date, read only when needed to fill text YMD/two-digit-year
            reference. It does not supply the column clock, zone or fold.
        yearfirst : _Boolean | None
            Explicit non-None boolean wins over Configs. Without either, yearfirst=True/dayfirst=False;
            False is an explicit preference.
        dayfirst : _Boolean | None
            Explicit non-None boolean wins over Configs. Without either, yearfirst=True/dayfirst=False;
            False is an explicit preference.
        isoformat : _Boolean
            Try ISO first and then shared ordinary parsing when needed; this is not ISO-only validation.
        strict : _Boolean
            Validate explicit parsed date/clock fields and conflicts; it does not replace the regional DST
            policies.
        cfg : Configs | None
            Shared Configs word/region rules. None uses the existing defaults; Expr freezes effective
            rules when it is created.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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
        >>> Pldt.parse(["1970-01-01T00:00:00.000000001"]).to_physical().to_list()
        [1]"""
        ...

    @classmethod
    def strptime(cls, dtstr: _IsoInput, fmt: str, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, cfg: Configs | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Match a shared explicit format; scalar text requires size.
        
        Parameters
        ----------
        dtstr : _IsoInput
            Source/target in this factory's stated role. Actual dtype/unit/zone and independent validity
            are preserved; a scalar broadcasts only where the named factory permits it.
        fmt : str
            Explicit parsing format. %f reads fractional seconds through ns; excess digits and a
            deliberately requested coarser unit truncate at this format-parse exit. %Z uses explicit
            Configs rules. Expr formats with %f require unit; timezone directives require tz.
        size : SupportsIndex | None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        cfg : Configs | None
            Shared Configs word/region rules. None uses the existing defaults; Expr freezes effective
            rules when it is created.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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
        >>> Pldt.strptime(["1970-01-01 00:00:00.123456789"], "%Y-%m-%d %H:%M:%S.%f", unit="ns").nanosecond.to_list()
        [789]"""
        ...

    @classmethod
    def now(cls, size: SupportsIndex, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None) -> Self:
        """Repeat one current instant, or its local naive clock when tz is None.
        
        Parameters
        ----------
        size : SupportsIndex
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Requested current-time resolution ms/us/ns; None selects us. This deliberately quantizes the
            current time and does not claim nanosecond clock accuracy.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        
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

    @classmethod
    def today(cls, size: SupportsIndex, *, unit: _Unit | None=None, name: str | None=None) -> Self:
        """Repeat the current full local clock; this does not normalize midnight.
        
        Parameters
        ----------
        size : SupportsIndex
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        unit : _Unit | None
            Requested current-time resolution ms/us/ns; None selects us. This deliberately quantizes the
            current time and does not claim nanosecond clock accuracy.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        
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

    @classmethod
    def utcnow(cls, size: SupportsIndex, *, unit: _Unit | None=None, name: str | None=None) -> Self:
        """Repeat one current true instant with UTC metadata and real precision.
        
        Parameters
        ----------
        size : SupportsIndex
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        unit : _Unit | None
            Requested current-time resolution ms/us/ns; None selects us. This deliberately quantizes the
            current time and does not claim nanosecond clock accuracy.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        
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

    @classmethod
    def fromseconds(cls, seconds: _NumericInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Read the fixed input quantity and construct one native date column.
        
        Parameters
        ----------
        seconds : _NumericInput
            Numeric seconds in calendar coordinates, including supported finite fractions. Not Unix-local-
            time inference and not raw ticks in the output unit.
        size : SupportsIndex | None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Eager default is at least us, selecting ns for a real nonzero tail. Expr integer seconds
            default to us; floating seconds require explicit ms/us/ns in schema preparation. An explicit
            output unit must be lossless.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar.
        
        Examples
        --------
        >>> Pldt.fromseconds([1e-9], unit="ns").to_physical().to_list()
        [1]"""
        ...

    @classmethod
    def frommicroseconds(cls, us: _CalendarInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Read the fixed input quantity and construct one native date column.
        
        Parameters
        ----------
        us : _CalendarInput
            Integer microseconds in the calendar coordinate system; floats/bools/text are rejected.
            Explicit unit conversion must be lossless.
        size : SupportsIndex | None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Output storage ms/us/ns; None selects us. Input always means integer microseconds, including
            on Expr; explicit conversion must be lossless.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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
        >>> Pldt.frommicroseconds([1], unit="ns").to_physical().to_list()
        [1000]"""
        ...

    @classmethod
    def fromtimestamp(cls, ts: _NumericInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None) -> Self:
        """Read the fixed input quantity and construct one native date column.
        
        Parameters
        ----------
        ts : _NumericInput
            Numeric Unix seconds representing real UTC instants, including supported finite fractions. Not
            raw ticks in the output unit.
        size : SupportsIndex | None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Eager default is at least us, selecting ns for a real nonzero tail. Expr integer seconds
            default to us; floating seconds require explicit ms/us/ns in schema preparation. An explicit
            output unit must be lossless.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        
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
        >>> Pldt.fromtimestamp([0], tz="UTC", unit="us").to_physical().to_list()
        [0]"""
        ...

    @classmethod
    def utcfromtimestamp(cls, ts: _NumericInput, *, size: SupportsIndex | None=None, unit: _Unit | None=None, name: str | None=None) -> Self:
        """Read the fixed input quantity and construct one native date column.
        
        Parameters
        ----------
        ts : _NumericInput
            Numeric Unix seconds representing real UTC instants, including supported finite fractions. Not
            raw ticks in the output unit.
        size : SupportsIndex | None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        unit : _Unit | None
            Eager default is at least us, selecting ns for a real nonzero tail. Expr integer seconds
            default to us; floating seconds require explicit ms/us/ns in schema preparation. An explicit
            output unit must be lossless.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        
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

    @classmethod
    def fromdate(cls, dt: _ActualDateInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Read the named actual date source, keeping its local/instant role.
        
        Parameters
        ----------
        dt : _ActualDateInput
            Actual Python date/datetime or native Date/Datetime column. Take local YMD, clear
            clock/fraction/source zone; strings, numbers and NumPy dates do not enter this specialized
            factory.
        size : SupportsIndex | None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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

    @classmethod
    def fromdatetime(cls, dt: _DatetimeInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Read the named actual date source, keeping its local/instant role.
        
        Parameters
        ----------
        dt : _DatetimeInput
            Actual datetime/Pydt/Timestamp or native Datetime column. None target preserves source
            instants/zone; an explicit non-None target replaces the zone while retaining wall fields. Pure
            date, text, numbers and NumPy dates are rejected.
        size : SupportsIndex | None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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

    @classmethod
    def fromdatetime64(cls, dt64: _NumpyDateInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Read the named actual date source, keeping its local/instant role.
        
        Parameters
        ----------
        dt64 : _NumpyDateInput
            Actual NumPy datetime64 scalar/one-dimensional date source. Decode unit/multiplier directly;
            do not accept ordinary datetime or pandas/Polars date columns. An explicit zone localizes
            decoded clocks.
        size : SupportsIndex | None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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

    @classmethod
    def fromordinal(cls, ordinal: _CalendarInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None='us', name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Resolve real integer calendar components into one checked date column.
        
        Parameters
        ----------
        ordinal : _CalendarInput
            Gregorian ordinal with 0001-01-01 equal to 1. Zero and negative ordinals are real dates in the
            native target's capacity, not missing or skip sentinels.
        size : SupportsIndex | None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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

    @classmethod
    def fromisocalendar(cls, year: _CalendarInput, week: _CalendarInput, weekday: _CalendarInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None='us', name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Resolve real integer calendar components into one checked date column.
        
        Parameters
        ----------
        year : _CalendarInput
            Integer calendar/ISO year, including zero and negative years when the unit/backend can
            represent the result. An explicit missing component makes a missing row; it is not a preserve
            sentinel.
        week : _CalendarInput
            Integer day-of-year/ISO-week component, scalar or equal-length column. Values below 1 fail;
            approved upper convenience selection is retained. An explicit missing component makes a
            missing row.
        weekday : _CalendarInput
            ISO weekday: Monday 1 through Sunday 7. Values below 1 fail, values above 7 select Sunday; an
            explicit missing component makes a missing row.
        size : SupportsIndex | None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    @classmethod
    def fromdayofyear(cls, year: _CalendarInput, doy: _CalendarInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None='us', name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Resolve real integer calendar components into one checked date column.
        
        Parameters
        ----------
        year : _CalendarInput
            Integer calendar/ISO year, including zero and negative years when the unit/backend can
            represent the result. An explicit missing component makes a missing row; it is not a preserve
            sentinel.
        doy : _CalendarInput
            Integer day-of-year/ISO-week component, scalar or equal-length column. Values below 1 fail;
            approved upper convenience selection is retained. An explicit missing component makes a
            missing row.
        size : SupportsIndex | None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    @classmethod
    def combine(cls, date: _DateInput=None, time: _CombineTime=None, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Combine local YMD and clock fields; only the final result is a Pldt.
        
        Parameters
        ----------
        date : _DateInput
            Source/target in this factory's stated role. Actual dtype/unit/zone and independent validity
            are preserved; a scalar broadcasts only where the named factory permits it.
        time : _CombineTime
            Source/target in this factory's stated role. Actual dtype/unit/zone and independent validity
            are preserved; a scalar broadcasts only where the named factory permits it.
        size : SupportsIndex | None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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

    @classmethod
    def fromisoformat(cls, dtstr: _IsoInput, *, size: SupportsIndex | None=None, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Read complete strict ISO dates, retaining source fraction width.
        
        Parameters
        ----------
        dtstr : _IsoInput
            Source/target in this factory's stated role. Actual dtype/unit/zone and independent validity
            are preserved; a scalar broadcasts only where the named factory permits it.
        size : SupportsIndex | None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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

    @classmethod
    def date_range(cls, start: _DateInput=None, *, end: _DateInput=None, periods: SupportsIndex | None=None, freq: object=None, tz: _Zone=None, normalize: _Boolean=False, inclusive: str='both', unit: _Unit | None=None, name: str | None=None, default: _DateValue=None, yearfirst: _Boolean | None=None, dayfirst: _Boolean | None=None, isoformat: _Boolean=True, strict: _Boolean=False, cfg: Configs | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Generate native calendar/elapsed dates; only special rules use optional pandas.
        
        Parameters
        ----------
        start : _DateInput
            Source/target in this factory's stated role. Actual dtype/unit/zone and independent validity
            are preserved; a scalar broadcasts only where the named factory permits it.
        end : _DateInput
            Source/target in this factory's stated role. Actual dtype/unit/zone and independent validity
            are preserved; a scalar broadcasts only where the named factory permits it.
        periods : SupportsIndex | None
            Single nonnegative integer count. Named scalar factories require size; a supplied collection
            cannot also supply size.
        freq : object
            Positive fixed rounding grid, for example 15min, or this range factory's approved native
            calendar/special delegated rule. A single value, never a row-wise column.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        normalize : _Boolean
            Move prepared endpoints to their local day boundary before range validation/generation when
            True.
        inclusive : str
            For diff: 'one' (ordinary signed difference), 'both' or 'neither'. For date_range: 'both',
            'left', 'right' or 'neither' endpoint inclusion.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        default : _DateValue
            An independently complete fallback date, read only when needed to fill text YMD/two-digit-year
            reference. It does not supply the column clock, zone or fold.
        yearfirst : _Boolean | None
            Explicit non-None boolean wins over Configs. Without either, yearfirst=True/dayfirst=False;
            False is an explicit preference.
        dayfirst : _Boolean | None
            Explicit non-None boolean wins over Configs. Without either, yearfirst=True/dayfirst=False;
            False is an explicit preference.
        isoformat : _Boolean
            Try ISO first and then shared ordinary parsing when needed; this is not ISO-only validation.
        strict : _Boolean
            Validate explicit parsed date/clock fields and conflicts; it does not replace the regional DST
            policies.
        cfg : Configs | None
            Shared Configs word/region rules. None uses the existing defaults; Expr freezes effective
            rules when it is created.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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
        >>> Pldt.date_range("1970-01-01", periods=3, freq="s", unit="us").to_physical().to_list()
        [0, 1000000, 2000000]"""
        ...

    def as_unit(self, unit: _Unit, round_ok: _Boolean=True) -> Self:
        """Return the chosen ms/us/ns resolution; round_ok=True floors precision loss.
        
        Parameters
        ----------
        unit : _Unit
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        round_ok : _Boolean
            True allows this explicit rescale to floor discarded precision toward earlier ticks; False
            requires an exact conversion.
        
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
        >>> Pldt([-1500], unit="ns").as_unit("us").to_physical().to_list()
        [-2]"""
        ...

    def tz_localize(self, tz: _Zone, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Interpret naive clocks, or remove a timezone while keeping clocks.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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

    def tz_convert(self, tz: _Zone) -> Self:
        """Preserve actual instants; None removes the UTC timezone metadata.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        
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

    def astimezone(self, tz: _Zone=None, *, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Convert to the target; naive input uses the process-local timezone.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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

    def tz_switch(self, targ_tz: _Zone, base_tz: _Zone=None, naive: _Boolean=False, *, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Self:
        """Convert with an explicit naive source zone, optionally removing target metadata.
        
        Parameters
        ----------
        targ_tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        base_tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        naive : _Boolean
            Remove target timezone metadata after the requested conversion when True.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
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
        name : str or None, default None
            Replacement column name. None retains the current name.
        deep : bool or numpy.bool_, default False
            Physically isolate date buffers and copy business state with one
            shared memo when True; otherwise share safe buffers/references.
        
        Returns
        -------
        Pldt
            A fresh same-class shell under the default protocol. Genuine custom
            copy/reduction hooks retain their return values and exceptions."""
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
    def __getstate__(self) -> object:  # type: ignore[override]
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

    def to_numpy(self, *, writable: _Boolean=False, allow_copy: _Boolean=True, allow_nat_collision: _Boolean=False) -> np.ndarray:
        """Use Polars' NumPy export, rejecting valid ticks that collide with NaT.
        
        Parameters
        ----------
        writable : _Boolean
            Original Polars/NumPy export option, passed to the mature implementation. Requested
            conversions must preserve values/precision/validity unless the collision opt-in applies.
        allow_copy : _Boolean
            Original Polars/NumPy export option, passed to the mature implementation. Requested
            conversions must preserve values/precision/validity unless the collision opt-in applies.
        allow_nat_collision : _Boolean
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_pandas(self, *, use_pyarrow_extension_array: _Boolean=False, allow_nat_collision: _Boolean=False, **kwargs: Any) -> pd.Series:
        """Use the complete Polars pandas export and check its actual date result.
        
        Parameters
        ----------
        use_pyarrow_extension_array : _Boolean
            Original Polars/NumPy export option, passed to the mature implementation. Requested
            conversions must preserve values/precision/validity unless the collision opt-in applies.
        allow_nat_collision : _Boolean
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def __array__(self, dtype: Any=None, copy: _Boolean | None=None) -> np.ndarray:
        """Retain native dtype/copy dispatch and validate explicit dtype changes.
        
        Parameters
        ----------
        dtype : Any
            Original Polars/NumPy export option, passed to the mature implementation. Requested
            conversions must preserve values/precision/validity unless the collision opt-in applies.
        copy : _Boolean | None
            True isolates source date buffers; False permits safe sharing but does not promise zero-copy
            or an independent snapshot.
        
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
            The true final result exceeds the current unit/target capacity."""
        ...

    # Approved date arithmetic/Duration output differs from the generic Series Self stub.
    @overload  # type: ignore[override]
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
    def __add__(self, other: Any) -> Self | pl.Series | NotImplementedType:
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
    @overload  # type: ignore[override]
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
        Date results are Pldt; actual Pldt subclass receivers retain their class."""
    def to_datetime(self, year: _OptionalField=None, month: _OptionalField=None, day: _OptionalField=None, hour: _OptionalField=None, minute: _OptionalField=None, second: _OptionalField=None, microsecond: _OptionalField=None, nanosecond: _OptionalField=None) -> _PldtT:
        """Merge legal fields once; fit a legal day intent to the final month.
        
        Parameters
        ----------
        year : _OptionalField
            Optional integer field/selector. None retains the source. Year may be zero/negative/wide
            within the native unit and regional backend capacity. Strict replace requires a real resulting
            date; calendar conveniences keep their separate valid upper-selection/month-end rules.
        month : _OptionalField
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _OptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        hour : _OptionalField
            Optional integer field/selector. None retains the source. Hour is 0-23. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        minute : _OptionalField
            Optional integer field/selector. None retains the source. Minute is 0-59. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        second : _OptionalField
            Optional integer field/selector. None retains the source. Second is 0-59. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        microsecond : _OptionalField
            Optional integer field/selector. None retains the source. Microsecond is 0-999999; setting it
            clears the old ns tail unless nanosecond is supplied. Strict replace requires a real resulting
            date; calendar conveniences keep their separate valid upper-selection/month-end rules.
        nanosecond : _OptionalField
            Optional integer field/selector. None retains the source. Nanosecond is the additional 0-999
            tail; zero explicitly clears it. Strict replace requires a real resulting date; calendar
            conveniences keep their separate valid upper-selection/month-end rules.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_date(self, year: _OptionalField=None, month: _OptionalField=None, day: _OptionalField=None) -> _PldtT:
        """Merge legal fields once; fit a legal day intent to the final month.
        
        Parameters
        ----------
        year : _OptionalField
            Optional integer field/selector. None retains the source. Year may be zero/negative/wide
            within the native unit and regional backend capacity. Strict replace requires a real resulting
            date; calendar conveniences keep their separate valid upper-selection/month-end rules.
        month : _OptionalField
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _OptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_time(self, hour: _OptionalField=None, minute: _OptionalField=None, second: _OptionalField=None, microsecond: _OptionalField=None, nanosecond: _OptionalField=None) -> _PldtT:
        """Merge legal fields once; fit a legal day intent to the final month.
        
        Parameters
        ----------
        hour : _OptionalField
            Optional integer field/selector. None retains the source. Hour is 0-23. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        minute : _OptionalField
            Optional integer field/selector. None retains the source. Minute is 0-59. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        second : _OptionalField
            Optional integer field/selector. None retains the source. Second is 0-59. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        microsecond : _OptionalField
            Optional integer field/selector. None retains the source. Microsecond is 0-999999; setting it
            clears the old ns tail unless nanosecond is supplied. Strict replace requires a real resulting
            date; calendar conveniences keep their separate valid upper-selection/month-end rules.
        nanosecond : _OptionalField
            Optional integer field/selector. None retains the source. Nanosecond is the additional 0-999
            tail; zero explicitly clears it. Strict replace requires a real resulting date; calendar
            conveniences keep their separate valid upper-selection/month-end rules.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_year(self, offset: _IntegerInput, month: _Selection=None, day: _OptionalField=None) -> _PldtT:
        """Move local calendar periods, retaining precision and fitting month end.
        
        Parameters
        ----------
        offset : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        month : _Selection
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _OptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_quarter(self, offset: _IntegerInput, month: _OptionalField=None, day: _OptionalField=None) -> _PldtT:
        """Move local calendar periods, retaining precision and fitting month end.
        
        Parameters
        ----------
        offset : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        month : _OptionalField
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : _OptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_month(self, offset: _IntegerInput, day: _OptionalField=None) -> _PldtT:
        """Move local calendar periods, retaining precision and fitting month end.
        
        Parameters
        ----------
        offset : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        day : _OptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_weekday(self, offset: _IntegerInput, weekday: _Selection=None) -> _PldtT:
        """Move local calendar periods, retaining precision and fitting month end.
        
        Parameters
        ----------
        offset : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weekday : _Selection
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_day(self, offset: _IntegerInput) -> _PldtT:
        """Move local calendar periods, retaining precision and fitting month end.
        
        Parameters
        ----------
        offset : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_curr_year(self, month: _Selection=None, day: _OptionalField=None) -> _PldtT:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _Selection
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _OptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_prev_year(self, month: _Selection=None, day: _OptionalField=None) -> _PldtT:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _Selection
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _OptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_next_year(self, month: _Selection=None, day: _OptionalField=None) -> _PldtT:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _Selection
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _OptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_curr_quarter(self, month: _OptionalField=None, day: _OptionalField=None) -> _PldtT:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _OptionalField
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : _OptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_prev_quarter(self, month: _OptionalField=None, day: _OptionalField=None) -> _PldtT:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _OptionalField
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : _OptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_next_quarter(self, month: _OptionalField=None, day: _OptionalField=None) -> _PldtT:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _OptionalField
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : _OptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_curr_month(self, day: _OptionalField=None) -> _PldtT:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        day : _OptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_prev_month(self, day: _OptionalField=None) -> _PldtT:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        day : _OptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_next_month(self, day: _OptionalField=None) -> _PldtT:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        day : _OptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_curr_weekday(self, weekday: _Selection=None) -> _PldtT:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        weekday : _Selection
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.
        
        Returns
        -------
        _PldtT
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

    def to_prev_weekday(self, weekday: _Selection=None) -> _PldtT:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        weekday : _Selection
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.
        
        Returns
        -------
        _PldtT
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

    def to_next_weekday(self, weekday: _Selection=None) -> _PldtT:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        weekday : _Selection
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.
        
        Returns
        -------
        _PldtT
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

    def to_monday(self) -> _PldtT:
        """Select this week's monday, using Monday as day zero.
        
        Returns
        -------
        _PldtT
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

    def to_tuesday(self) -> _PldtT:
        """Select this week's tuesday, using Monday as day zero.
        
        Returns
        -------
        _PldtT
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

    def to_wednesday(self) -> _PldtT:
        """Select this week's wednesday, using Monday as day zero.
        
        Returns
        -------
        _PldtT
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

    def to_thursday(self) -> _PldtT:
        """Select this week's thursday, using Monday as day zero.
        
        Returns
        -------
        _PldtT
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

    def to_friday(self) -> _PldtT:
        """Select this week's friday, using Monday as day zero.
        
        Returns
        -------
        _PldtT
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

    def to_saturday(self) -> _PldtT:
        """Select this week's saturday, using Monday as day zero.
        
        Returns
        -------
        _PldtT
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

    def to_sunday(self) -> _PldtT:
        """Select this week's sunday, using Monday as day zero.
        
        Returns
        -------
        _PldtT
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

    def to_yesterday(self) -> _PldtT:
        """Move one local calendar day, retaining clock and nanoseconds.
        
        Returns
        -------
        _PldtT
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

    def to_tomorrow(self) -> _PldtT:
        """Move one local calendar day, retaining clock and nanoseconds.
        
        Returns
        -------
        _PldtT
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

    def add(self, years: _IntegerInput=0, quarters: _IntegerInput=0, months: _IntegerInput=0, weeks: _IntegerInput=0, days: _IntegerInput=0, hours: _IntegerInput=0, minutes: _IntegerInput=0, seconds: _IntegerInput=0, milliseconds: _IntegerInput=0, microseconds: _IntegerInput=0, nanoseconds: _IntegerInput=0) -> _PldtT:
        """Combine integer calendar increments before final precision/capacity checks.
        
        Parameters
        ----------
        years : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        quarters : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        months : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weeks : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        days : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        hours : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        minutes : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        seconds : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        milliseconds : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        microseconds : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        nanoseconds : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar.
        
        Examples
        --------
        >>> Pldt([1], unit="us").add(microseconds=1, nanoseconds=-1000).to_physical().to_list()
        [1]"""
        ...

    def sub(self, years: _IntegerInput=0, quarters: _IntegerInput=0, months: _IntegerInput=0, weeks: _IntegerInput=0, days: _IntegerInput=0, hours: _IntegerInput=0, minutes: _IntegerInput=0, seconds: _IntegerInput=0, milliseconds: _IntegerInput=0, microseconds: _IntegerInput=0, nanoseconds: _IntegerInput=0) -> _PldtT:
        """Combine integer calendar increments before final precision/capacity checks.
        
        Parameters
        ----------
        years : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        quarters : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        months : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weeks : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        days : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        hours : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        minutes : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        seconds : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        milliseconds : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        microseconds : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        nanoseconds : _IntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_first_of(self, unit: str) -> _PldtT:
        """Select a calendar boundary while preserving date unit and timezone.
        
        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.
        
        Returns
        -------
        _PldtT
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

    def is_first_of(self, unit: str) -> pl.Series:
        """Query the actual calendar boundary; missing source dates are False.
        
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_last_of(self, unit: str) -> _PldtT:
        """Select a calendar boundary while preserving date unit and timezone.
        
        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.
        
        Returns
        -------
        _PldtT
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

    def is_last_of(self, unit: str) -> pl.Series:
        """Query the actual calendar boundary; missing source dates are False.
        
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_start_of(self, unit: str) -> _PldtT:
        """Select a calendar boundary while preserving date unit and timezone.
        
        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.
        
        Returns
        -------
        _PldtT
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

    def is_start_of(self, unit: str) -> pl.Series:
        """Query the actual calendar boundary; missing source dates are False.
        
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_end_of(self, unit: str) -> _PldtT:
        """Select a calendar boundary while preserving date unit and timezone.
        
        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.
        
        Returns
        -------
        _PldtT
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

    def is_end_of(self, unit: str) -> pl.Series:
        """Query the actual calendar boundary; missing source dates are False.
        
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def normalize(self) -> _PldtT:
        """Return the real start of this local day, staying within the day.
        
        Returns
        -------
        _PldtT
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

    def snap(self, unit: str='s') -> _PldtT:
        """Select the nearest real period start; equal distances select later.
        
        Parameters
        ----------
        unit : str
            One natural Y/Q/M/W/D/h/m/min/s/ms/us/ns period or an exact saved month/weekday name; no
            arbitrary multi-step frequency or numeric weekday.
        
        Returns
        -------
        _PldtT
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
        >>> Pldt(["1970-01-01 12:00:00"], unit="us").snap("D").to_physical().to_list()
        [86400000000]"""
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
        _PldtT
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
        """Additional nanosecond tail, 0 through999, as nullable Int64.
        
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
    def weekday(self) -> pl.Series:
        """Weekday with Monday0, as nullable Int64.
        
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
        """Millisecond within the second, from0 through999.
        
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
        """ISO weekday with Monday1.
        
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
        """Days before this calendar year, relative to0001-01-01.
        
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
        year : _IntegerInput
            Required scalar or equal-length target; legal nonmatching numeric values return False. Missing
            targets fail even for source null; unknown/empty saved month names fail instead of silently
            returning False.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def is_quarter(self, quarter: _IntegerInput) -> pl.Series:
        """Match scalar or equal-length integer quarter targets.
        
        Parameters
        ----------
        quarter : _IntegerInput
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_month(self, month: _QuerySelection) -> pl.Series:
        """Match integer or saved month names, by position; null is False.
        
        Parameters
        ----------
        month : _QuerySelection
            Required scalar or equal-length target; legal nonmatching numeric values return False. Missing
            targets fail even for source null; unknown/empty saved month names fail instead of silently
            returning False.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def is_weekday(self, weekday: _QuerySelection) -> pl.Series:
        """Match integer or saved weekday names, with Monday0.
        
        Parameters
        ----------
        weekday : _QuerySelection
            Required scalar or equal-length integer/saved-name target, Monday 0. Legal nonmatching
            integers return False; missing/unknown/empty targets fail even for source null.
        
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

    def is_day(self, day: _IntegerInput) -> pl.Series:
        """Match scalar or equal-length integer day targets.
        
        Parameters
        ----------
        day : _IntegerInput
            Required scalar or equal-length target; legal nonmatching numeric values return False. Missing
            targets fail even for source null; unknown/empty saved month names fail instead of silently
            returning False.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def is_long_year(self) -> pl.Series:
        """Whether the calendar year has53 ISO weeks; null is False.
        
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
        year : _IntegerInput
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
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
        """Return year/week/day as a native Struct with UInt32 fields.
        
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
        >>> Pldt(["2021-01-01"]).isocalendar().to_list()
        [{'year': 2020, 'week': 53, 'day': 5}]"""
        ...

    def timedf(self) -> pl.DataFrame:
        """Return local time fields as an eager DataFrame or native Struct Expr.
        
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
        utc : _Boolean
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
        >>> x = Pldt(["1970-01-01 08:00:00"], tz="Asia/Shanghai", unit="us")
        >>> x.toseconds().to_list()
        [28800.0]
        >>> x.toseconds(utc=True).to_list()
        [0.0]"""
        ...

    def tomicroseconds(self, utc: _Boolean=False) -> pl.Series:
        """Return Int64 microseconds, flooring only at this explicit output.
        
        Parameters
        ----------
        utc : _Boolean
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
        >>> Pldt(["1970-01-01 00:00:00.000001"], unit="ns").tomicroseconds().to_list()
        [1]"""
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
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity.
        
        Examples
        --------
        >>> Pldt(["1970-01-01 08:00:00"], tz="Asia/Shanghai").timestamp().to_list()
        [0.0]"""
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
            The true final result exceeds the current unit/target capacity."""
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
            The true final result exceeds the current unit/target capacity."""
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
            H/M/s/ms/us/ns aliases.
        
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
        >>> Pldt([123456789], unit="ns").strftime("%f|%.3f|%.0f").to_list()
        ['123456789|.123|']"""
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
        locale : str | None
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
            The true final result exceeds the current unit/target capacity."""
        ...

    def weekday_name(self, locale: str | None=None) -> pl.Series:
        """Return compiled CLDR weekday names; the default language is English.
        
        Parameters
        ----------
        locale : str | None
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
            The true final result exceeds the current unit/target capacity."""
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
        >>> type(Pldt([0], unit="ns").datetime()[0]).__name__
        'Pydt'"""
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
        dtobj : _DiffInput
            Source/target in this factory's stated role. Actual dtype/unit/zone and independent validity
            are preserved; a scalar broadcasts only where the named factory permits it.
        unit : str
            Boundary bucket Y/Q/M/W/D/h/m/min/s/ms/us/ns; it is not a storage-unit conversion.
        absolute : _Boolean
            Original protocol argument, forwarded without inventing another interpretation.
        inclusive : str
            For diff: 'one' (ordinary signed difference), 'both' or 'neither'. For date_range: 'both',
            'left', 'right' or 'neither' endpoint inclusion.
        
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
        >>> Pldt(["2024-01-03"]).pldt.diff("2024-01-01", "D").to_list()
        [2]"""
        ...

    def round(self, freq: str='s') -> _PldtT:
        """Date rounding on a positive fixed grid; preserves current storage unit.
        
        Parameters
        ----------
        freq : str
            Positive fixed rounding grid, for example 15min, or this range factory's approved native
            calendar/special delegated rule. A single value, never a row-wise column.
        
        Returns
        -------
        _PldtT
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

    def ceil(self, freq: str='s') -> _PldtT:
        """Date rounding on a positive fixed grid; preserves current storage unit.
        
        Parameters
        ----------
        freq : str
            Positive fixed rounding grid, for example 15min, or this range factory's approved native
            calendar/special delegated rule. A single value, never a row-wise column.
        
        Returns
        -------
        _PldtT
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

    def floor(self, freq: str='s') -> _PldtT:
        """Date rounding on a positive fixed grid; preserves current storage unit.
        
        Parameters
        ----------
        freq : str
            Positive fixed rounding grid, for example 15min, or this range factory's approved native
            calendar/special delegated rule. A single value, never a row-wise column.
        
        Returns
        -------
        _PldtT
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

    def add_delta(self, delta: _DeltaInput) -> _PldtT:
        """Apply actual Delta rules and return one final Pldt column.
        
        Parameters
        ----------
        delta : _DeltaInput
            Actual Delta scalar or equal-length Delta values. All absolute fields and relative nanoseconds
            remain intact; source data is not modified.
        
        Returns
        -------
        _PldtT
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

    def sub_delta(self, delta: _DeltaInput) -> _PldtT:
        """Reverse relative Delta quantities while retaining absolute fields.
        
        Parameters
        ----------
        delta : _DeltaInput
            Actual Delta scalar or equal-length Delta values. All absolute fields and relative nanoseconds
            remain intact; source data is not modified.
        
        Returns
        -------
        _PldtT
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

    def replace(self, year: _OptionalField=None, month: _OptionalField=None, day: _OptionalField=None, hour: _OptionalField=None, minute: _OptionalField=None, second: _OptionalField=None, microsecond: _OptionalField=None, nanosecond: _OptionalField=None, tzinfo: _Zone= ..., *, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Strictly merge date fields; omitted tzinfo retains, None removes the zone.
        
        Parameters
        ----------
        year : _OptionalField
            Optional integer field/selector. None retains the source. Year may be zero/negative/wide
            within the native unit and regional backend capacity. Strict replace requires a real resulting
            date; calendar conveniences keep their separate valid upper-selection/month-end rules.
        month : _OptionalField
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _OptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        hour : _OptionalField
            Optional integer field/selector. None retains the source. Hour is 0-23. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        minute : _OptionalField
            Optional integer field/selector. None retains the source. Minute is 0-59. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        second : _OptionalField
            Optional integer field/selector. None retains the source. Second is 0-59. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        microsecond : _OptionalField
            Optional integer field/selector. None retains the source. Microsecond is 0-999999; setting it
            clears the old ns tail unless nanosecond is supplied. Strict replace requires a real resulting
            date; calendar conveniences keep their separate valid upper-selection/month-end rules.
        nanosecond : _OptionalField
            Optional integer field/selector. None retains the source. Nanosecond is the additional 0-999
            tail; zero explicitly clears it. Strict replace requires a real resulting date; calendar
            conveniences keep their separate valid upper-selection/month-end rules.
        tzinfo : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        _PldtT
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar.
        
        Examples
        --------
        >>> Pldt(["2024-01-31"]).pldt.replace(day=28, month=2).day.to_list()
        [28]"""
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
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        _PldtT
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

    def combine(self, time: _CombineTime=None, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Use this Series for dates and compose one final native Pldt.
        
        Parameters
        ----------
        time : _CombineTime
            Source/target in this factory's stated role. Actual dtype/unit/zone and independent validity
            are preserved; a scalar broadcasts only where the named factory permits it.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        _PldtT
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

    def fromordinal(self, *, tz: _Zone=None, unit: _Unit | None='us', name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Resolve positional calendar components with a fixed output schema.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        _PldtT
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

    def fromisocalendar(self, week: _CalendarInput, weekday: _CalendarInput, *, tz: _Zone=None, unit: _Unit | None='us', name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Resolve positional calendar components with a fixed output schema.
        
        Parameters
        ----------
        week : _CalendarInput
            Integer day-of-year/ISO-week component, scalar or equal-length column. Values below 1 fail;
            approved upper convenience selection is retained. An explicit missing component makes a
            missing row.
        weekday : _CalendarInput
            ISO weekday: Monday 1 through Sunday 7. Values below 1 fail, values above 7 select Sunday; an
            explicit missing component makes a missing row.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        _PldtT
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

    def fromdayofyear(self, doy: _CalendarInput, *, tz: _Zone=None, unit: _Unit | None='us', name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Resolve positional calendar components with a fixed output schema.
        
        Parameters
        ----------
        doy : _CalendarInput
            Integer day-of-year/ISO-week component, scalar or equal-length column. Values below 1 fail;
            approved upper convenience selection is retained. An explicit missing component makes a
            missing row.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        _PldtT
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

    def parse(self, *, unit: _Unit | None=None, name: str | None=None, copy: _Boolean=False, tz: _Zone=None, default: _DateValue=None, yearfirst: _Boolean | None=None, dayfirst: _Boolean | None=None, isoformat: _Boolean=True, strict: _Boolean=False, cfg: Configs | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Parse supported native data into a Pldt without a Python row UDF.
        
        Parameters
        ----------
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        copy : _Boolean
            True isolates source date buffers; False permits safe sharing but does not promise zero-copy
            or an independent snapshot.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        default : _DateValue
            An independently complete fallback date, read only when needed to fill text YMD/two-digit-year
            reference. It does not supply the column clock, zone or fold.
        yearfirst : _Boolean | None
            Explicit non-None boolean wins over Configs. Without either, yearfirst=True/dayfirst=False;
            False is an explicit preference.
        dayfirst : _Boolean | None
            Explicit non-None boolean wins over Configs. Without either, yearfirst=True/dayfirst=False;
            False is an explicit preference.
        isoformat : _Boolean
            Try ISO first and then shared ordinary parsing when needed; this is not ISO-only validation.
        strict : _Boolean
            Validate explicit parsed date/clock fields and conflicts; it does not replace the regional DST
            policies.
        cfg : Configs | None
            Shared Configs word/region rules. None uses the existing defaults; Expr freezes effective
            rules when it is created.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        _PldtT
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
        >>> Pldt.parse(["1970-01-01T00:00:00.000000001"]).to_physical().to_list()
        [1]"""
        ...

    def strptime(self, fmt: str, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, cfg: Configs | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Match text using the shared format language and final output unit.
        
        Parameters
        ----------
        fmt : str
            Explicit parsing format. %f reads fractional seconds through ns; excess digits and a
            deliberately requested coarser unit truncate at this format-parse exit. %Z uses explicit
            Configs rules. Expr formats with %f require unit; timezone directives require tz.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        cfg : Configs | None
            Shared Configs word/region rules. None uses the existing defaults; Expr freezes effective
            rules when it is created.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        _PldtT
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
        >>> Pldt.strptime(["1970-01-01 00:00:00.123456789"], "%Y-%m-%d %H:%M:%S.%f", unit="ns").nanosecond.to_list()
        [789]"""
        ...

    def fromseconds(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Read the numeric column using fixed quantity and timezone semantics.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Eager default is at least us, selecting ns for a real nonzero tail. Expr integer seconds
            default to us; floating seconds require explicit ms/us/ns in schema preparation. An explicit
            output unit must be lossless.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        _PldtT
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
        >>> Pldt.fromseconds([1e-9], unit="ns").to_physical().to_list()
        [1]"""
        ...

    def frommicroseconds(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Read the numeric column using fixed quantity and timezone semantics.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Output storage ms/us/ns; None selects us. Input always means integer microseconds, including
            on Expr; explicit conversion must be lossless.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        _PldtT
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
        >>> Pldt.frommicroseconds([1], unit="ns").to_physical().to_list()
        [1000]"""
        ...

    def fromtimestamp(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None) -> _PldtT:
        """Read the numeric column using fixed quantity and timezone semantics.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Eager default is at least us, selecting ns for a real nonzero tail. Expr integer seconds
            default to us; floating seconds require explicit ms/us/ns in schema preparation. An explicit
            output unit must be lossless.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        
        Returns
        -------
        _PldtT
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
        >>> Pldt.fromtimestamp([0], tz="UTC", unit="us").to_physical().to_list()
        [0]"""
        ...

    def utcfromtimestamp(self, *, unit: _Unit | None=None, name: str | None=None) -> _PldtT:
        """Read the numeric column using fixed quantity and timezone semantics.
        
        Parameters
        ----------
        unit : _Unit | None
            Eager default is at least us, selecting ns for a real nonzero tail. Expr integer seconds
            default to us; floating seconds require explicit ms/us/ns in schema preparation. An explicit
            output unit must be lossless.
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        
        Returns
        -------
        _PldtT
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

    def fromdate(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Use the real native date schema, without parsing text or numeric data.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        _PldtT
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

    def fromdatetime(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Use the real native date schema, without parsing text or numeric data.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        name : str | None
            Optional string column name. None preserves a usable source/current name; a custom copy
            returning the original cannot rename it to a different name.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        _PldtT
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

    def as_unit(self, unit: _Unit, round_ok: _Boolean=True) -> _PldtT:
        """Convert Date/Datetime storage with explicit loss permission.
        
        Parameters
        ----------
        unit : _Unit
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        round_ok : _Boolean
            True allows this explicit rescale to floor discarded precision toward earlier ticks; False
            requires an exact conversion.
        
        Returns
        -------
        _PldtT
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
        >>> Pldt([-1500], unit="ns").as_unit("us").to_physical().to_list()
        [-2]"""
        ...

    def tz_localize(self, tz: _Zone, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Interpret naive clocks, or remove a timezone while keeping clocks.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        _PldtT
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

    def tz_convert(self, tz: _Zone) -> _PldtT:
        """Preserve actual instants; None removes the UTC timezone metadata.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        
        Returns
        -------
        _PldtT
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

    def astimezone(self, tz: _Zone=None, *, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Convert to the target; naive input uses the process-local timezone.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        _PldtT
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

    def tz_switch(self, targ_tz: _Zone, base_tz: _Zone=None, naive: _Boolean=False, *, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
        """Convert with an explicit naive source zone, optionally removing target metadata.
        
        Parameters
        ----------
        targ_tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        base_tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        naive : _Boolean
            Remove target timezone metadata after the requested conversion when True.
        ambiguous : _Ambiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        _PldtT
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

class _ExprNamespace:
    """Registered native Expr date namespace; no implicit collection.
    
    Parameters
    ----------
    expr : pl.Expr
        Native expression receiver.
    
    Returns
    -------
    _ExprNamespace
        Operations return native pl.Expr, with schema fixed before execution."""
    def to_datetime(self, year: _ExprOptionalField=None, month: _ExprOptionalField=None, day: _ExprOptionalField=None, hour: _ExprOptionalField=None, minute: _ExprOptionalField=None, second: _ExprOptionalField=None, microsecond: _ExprOptionalField=None, nanosecond: _ExprOptionalField=None) -> pl.Expr:
        """Merge legal fields once; fit a legal day intent to the final month.
        
        Parameters
        ----------
        year : _ExprOptionalField
            Optional integer field/selector. None retains the source. Year may be zero/negative/wide
            within the native unit and regional backend capacity. Strict replace requires a real resulting
            date; calendar conveniences keep their separate valid upper-selection/month-end rules.
        month : _ExprOptionalField
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _ExprOptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        hour : _ExprOptionalField
            Optional integer field/selector. None retains the source. Hour is 0-23. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        minute : _ExprOptionalField
            Optional integer field/selector. None retains the source. Minute is 0-59. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        second : _ExprOptionalField
            Optional integer field/selector. None retains the source. Second is 0-59. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        microsecond : _ExprOptionalField
            Optional integer field/selector. None retains the source. Microsecond is 0-999999; setting it
            clears the old ns tail unless nanosecond is supplied. Strict replace requires a real resulting
            date; calendar conveniences keep their separate valid upper-selection/month-end rules.
        nanosecond : _ExprOptionalField
            Optional integer field/selector. None retains the source. Nanosecond is the additional 0-999
            tail; zero explicitly clears it. Strict replace requires a real resulting date; calendar
            conveniences keep their separate valid upper-selection/month-end rules.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_date(self, year: _ExprOptionalField=None, month: _ExprOptionalField=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Merge legal fields once; fit a legal day intent to the final month.
        
        Parameters
        ----------
        year : _ExprOptionalField
            Optional integer field/selector. None retains the source. Year may be zero/negative/wide
            within the native unit and regional backend capacity. Strict replace requires a real resulting
            date; calendar conveniences keep their separate valid upper-selection/month-end rules.
        month : _ExprOptionalField
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _ExprOptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_time(self, hour: _ExprOptionalField=None, minute: _ExprOptionalField=None, second: _ExprOptionalField=None, microsecond: _ExprOptionalField=None, nanosecond: _ExprOptionalField=None) -> pl.Expr:
        """Merge legal fields once; fit a legal day intent to the final month.
        
        Parameters
        ----------
        hour : _ExprOptionalField
            Optional integer field/selector. None retains the source. Hour is 0-23. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        minute : _ExprOptionalField
            Optional integer field/selector. None retains the source. Minute is 0-59. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        second : _ExprOptionalField
            Optional integer field/selector. None retains the source. Second is 0-59. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        microsecond : _ExprOptionalField
            Optional integer field/selector. None retains the source. Microsecond is 0-999999; setting it
            clears the old ns tail unless nanosecond is supplied. Strict replace requires a real resulting
            date; calendar conveniences keep their separate valid upper-selection/month-end rules.
        nanosecond : _ExprOptionalField
            Optional integer field/selector. None retains the source. Nanosecond is the additional 0-999
            tail; zero explicitly clears it. Strict replace requires a real resulting date; calendar
            conveniences keep their separate valid upper-selection/month-end rules.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_year(self, offset: _ExprIntegerInput, month: _ExprSelection=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Move local calendar periods, retaining precision and fitting month end.
        
        Parameters
        ----------
        offset : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        month : _ExprSelection
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _ExprOptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_quarter(self, offset: _ExprIntegerInput, month: _ExprOptionalField=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Move local calendar periods, retaining precision and fitting month end.
        
        Parameters
        ----------
        offset : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        month : _ExprOptionalField
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : _ExprOptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_month(self, offset: _ExprIntegerInput, day: _ExprOptionalField=None) -> pl.Expr:
        """Move local calendar periods, retaining precision and fitting month end.
        
        Parameters
        ----------
        offset : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        day : _ExprOptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_weekday(self, offset: _ExprIntegerInput, weekday: _ExprSelection=None) -> pl.Expr:
        """Move local calendar periods, retaining precision and fitting month end.
        
        Parameters
        ----------
        offset : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weekday : _ExprSelection
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_day(self, offset: _ExprIntegerInput) -> pl.Expr:
        """Move local calendar periods, retaining precision and fitting month end.
        
        Parameters
        ----------
        offset : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_curr_year(self, month: _ExprSelection=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _ExprSelection
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _ExprOptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_prev_year(self, month: _ExprSelection=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _ExprSelection
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _ExprOptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_next_year(self, month: _ExprSelection=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _ExprSelection
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _ExprOptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_curr_quarter(self, month: _ExprOptionalField=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _ExprOptionalField
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : _ExprOptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_prev_quarter(self, month: _ExprOptionalField=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _ExprOptionalField
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : _ExprOptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_next_quarter(self, month: _ExprOptionalField=None, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        month : _ExprOptionalField
            Optional integer field/selector. None retains the source. Month is the 1-3 position inside the
            chosen quarter; it is not a month name. Strict replace requires a real resulting date;
            calendar conveniences keep their separate valid upper-selection/month-end rules.
        day : _ExprOptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_curr_month(self, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        day : _ExprOptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_prev_month(self, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        day : _ExprOptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_next_month(self, day: _ExprOptionalField=None) -> pl.Expr:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        day : _ExprOptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_curr_weekday(self, weekday: _ExprSelection=None) -> pl.Expr:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        weekday : _ExprSelection
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_prev_weekday(self, weekday: _ExprSelection=None) -> pl.Expr:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        weekday : _ExprSelection
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_next_weekday(self, weekday: _ExprSelection=None) -> pl.Expr:
        """Select the calendar period directly through the shared native kernel.
        
        Parameters
        ----------
        weekday : _ExprSelection
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_monday(self) -> pl.Expr:
        """Select this week's monday, using Monday as day zero.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_tuesday(self) -> pl.Expr:
        """Select this week's tuesday, using Monday as day zero.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_wednesday(self) -> pl.Expr:
        """Select this week's wednesday, using Monday as day zero.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_thursday(self) -> pl.Expr:
        """Select this week's thursday, using Monday as day zero.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_friday(self) -> pl.Expr:
        """Select this week's friday, using Monday as day zero.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_saturday(self) -> pl.Expr:
        """Select this week's saturday, using Monday as day zero.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_sunday(self) -> pl.Expr:
        """Select this week's sunday, using Monday as day zero.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_yesterday(self) -> pl.Expr:
        """Move one local calendar day, retaining clock and nanoseconds.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_tomorrow(self) -> pl.Expr:
        """Move one local calendar day, retaining clock and nanoseconds.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def add(self, years: _ExprIntegerInput=0, quarters: _ExprIntegerInput=0, months: _ExprIntegerInput=0, weeks: _ExprIntegerInput=0, days: _ExprIntegerInput=0, hours: _ExprIntegerInput=0, minutes: _ExprIntegerInput=0, seconds: _ExprIntegerInput=0, milliseconds: _ExprIntegerInput=0, microseconds: _ExprIntegerInput=0, nanoseconds: _ExprIntegerInput=0) -> pl.Expr:
        """Combine integer calendar increments before final precision/capacity checks.
        
        Parameters
        ----------
        years : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        quarters : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        months : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weeks : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        days : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        hours : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        minutes : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        seconds : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        milliseconds : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        microseconds : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        nanoseconds : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar.
        
        Examples
        --------
        >>> Pldt([1], unit="us").add(microseconds=1, nanoseconds=-1000).to_physical().to_list()
        [1]"""
        ...

    def sub(self, years: _ExprIntegerInput=0, quarters: _ExprIntegerInput=0, months: _ExprIntegerInput=0, weeks: _ExprIntegerInput=0, days: _ExprIntegerInput=0, hours: _ExprIntegerInput=0, minutes: _ExprIntegerInput=0, seconds: _ExprIntegerInput=0, milliseconds: _ExprIntegerInput=0, microseconds: _ExprIntegerInput=0, nanoseconds: _ExprIntegerInput=0) -> pl.Expr:
        """Combine integer calendar increments before final precision/capacity checks.
        
        Parameters
        ----------
        years : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        quarters : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        months : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        weeks : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        days : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        hours : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        minutes : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        seconds : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        milliseconds : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        microseconds : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        nanoseconds : _ExprIntegerInput
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def to_first_of(self, unit: str) -> pl.Expr:
        """Select a calendar boundary while preserving date unit and timezone.
        
        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_first_of(self, unit: str) -> pl.Expr:
        """Query the actual calendar boundary; missing source dates are False.
        
        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_last_of(self, unit: str) -> pl.Expr:
        """Select a calendar boundary while preserving date unit and timezone.
        
        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_last_of(self, unit: str) -> pl.Expr:
        """Query the actual calendar boundary; missing source dates are False.
        
        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_start_of(self, unit: str) -> pl.Expr:
        """Select a calendar boundary while preserving date unit and timezone.
        
        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_start_of(self, unit: str) -> pl.Expr:
        """Query the actual calendar boundary; missing source dates are False.
        
        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def to_end_of(self, unit: str) -> pl.Expr:
        """Select a calendar boundary while preserving date unit and timezone.
        
        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_end_of(self, unit: str) -> pl.Expr:
        """Query the actual calendar boundary; missing source dates are False.
        
        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def normalize(self) -> pl.Expr:
        """Return the real start of this local day, staying within the day.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
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
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        >>> Pldt(["1970-01-01 12:00:00"], unit="us").snap("D").to_physical().to_list()
        [86400000000]"""
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
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
    def year(self) -> pl.Expr:
        """Signed calendar year as a nullable Int64 column.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
    def month(self) -> pl.Expr:
        """One-based month as a nullable Int64 column.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
    def day(self) -> pl.Expr:
        """One-based day as a nullable Int64 column.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
    def hour(self) -> pl.Expr:
        """Hour within the local day as nullable Int64.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
    def minute(self) -> pl.Expr:
        """Minute within the hour as nullable Int64.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
    def second(self) -> pl.Expr:
        """Second within the minute as nullable Int64.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
    def microsecond(self) -> pl.Expr:
        """Microsecond within the second as nullable Int64.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
    def nanosecond(self) -> pl.Expr:
        """Additional nanosecond tail, 0 through999, as nullable Int64.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
    def weekday(self) -> pl.Expr:
        """Weekday with Monday0, as nullable Int64.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
    def day_of_year(self) -> pl.Expr:
        """One-based day within the local calendar year.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
    def days_in_month(self) -> pl.Expr:
        """Number of days in the local calendar month.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
    def quarter(self) -> pl.Expr:
        """One-based calendar quarter as nullable Int64.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
    def millisecond(self) -> pl.Expr:
        """Millisecond within the second, from0 through999.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
    def is_leap_year(self) -> pl.Expr:
        """Whether the local year is leap; source null is False.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def isoyear(self) -> pl.Expr:
        """Signed ISO week year, independently of UInt32 table capacity.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def isoweek(self) -> pl.Expr:
        """One-based ISO week number.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def isoweekday(self) -> pl.Expr:
        """ISO weekday with Monday1.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def days_in_year(self) -> pl.Expr:
        """Number of days in the local calendar year.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def days_bf_year(self) -> pl.Expr:
        """Days before this calendar year, relative to0001-01-01.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def days_in_quarter(self) -> pl.Expr:
        """Number of calendar days in this quarter.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def days_bf_quarter(self) -> pl.Expr:
        """Days in this year before the current quarter.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def day_of_quarter(self) -> pl.Expr:
        """One-based day in this calendar quarter.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def days_bf_month(self) -> pl.Expr:
        """Days in this year before the current month.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def day_of_month(self) -> pl.Expr:
        """One-based local day of month.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_year(self, year: _ExprIntegerInput) -> pl.Expr:
        """Match scalar or equal-length integer year targets.
        
        Parameters
        ----------
        year : _ExprIntegerInput
            Required scalar or equal-length target; legal nonmatching numeric values return False. Missing
            targets fail even for source null; unknown/empty saved month names fail instead of silently
            returning False.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def is_quarter(self, quarter: _ExprIntegerInput) -> pl.Expr:
        """Match scalar or equal-length integer quarter targets.
        
        Parameters
        ----------
        quarter : _ExprIntegerInput
            Required scalar or equal-length integer quarter target. Legal nonmatches return False; missing
            targets fail even for source null.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_month(self, month: _ExprQuerySelection) -> pl.Expr:
        """Match integer or saved month names, by position; null is False.
        
        Parameters
        ----------
        month : _ExprQuerySelection
            Required scalar or equal-length target; legal nonmatching numeric values return False. Missing
            targets fail even for source null; unknown/empty saved month names fail instead of silently
            returning False.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def is_weekday(self, weekday: _ExprQuerySelection) -> pl.Expr:
        """Match integer or saved weekday names, with Monday0.
        
        Parameters
        ----------
        weekday : _ExprQuerySelection
            Required scalar or equal-length integer/saved-name target, Monday 0. Legal nonmatching
            integers return False; missing/unknown/empty targets fail even for source null.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_day(self, day: _ExprIntegerInput) -> pl.Expr:
        """Match scalar or equal-length integer day targets.
        
        Parameters
        ----------
        day : _ExprIntegerInput
            Required scalar or equal-length target; legal nonmatching numeric values return False. Missing
            targets fail even for source null; unknown/empty saved month names fail instead of silently
            returning False.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def is_long_year(self) -> pl.Expr:
        """Whether the calendar year has53 ISO weeks; null is False.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def leap_bt_year(self, year: _ExprIntegerInput) -> pl.Expr:
        """Count leap years between row years and targets, lower inclusive.
        
        Parameters
        ----------
        year : _ExprIntegerInput
            Required signed integer target year or exactly equal-length targets. Count leap years between
            the two years, lower inclusive and upper exclusive; missing targets fail even for null source
            dates.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar."""
        ...

    def is_dst(self) -> pl.Expr:
        """Whether the native zone has nonzero DST; naive/null is False.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def utcoffset_seconds(self) -> pl.Expr:
        """Actual integer UTC offset; naive and missing rows are null.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_past(self) -> pl.Expr:
        """Strictly before one captured reference; Expr captures on creation.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def is_future(self) -> pl.Expr:
        """Strictly after one captured reference; Expr captures on creation.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def isocalendar(self) -> pl.Expr:
        """Return year/week/day as a native Struct with UInt32 fields.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        >>> Pldt(["2021-01-01"]).isocalendar().to_list()
        [{'year': 2020, 'week': 53, 'day': 5}]"""
        ...

    def timedf(self) -> pl.Expr:
        """Return local time fields as an eager DataFrame or native Struct Expr.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def utctimedf(self) -> pl.Expr:
        """Return UTC time fields; naive fields do not move and DST is zero.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def toseconds(self, utc: _Boolean=False) -> pl.Expr:
        """Return Float64 seconds in local coordinates, or UTC when requested.
        
        Parameters
        ----------
        utc : _Boolean
            Use UTC coordinates when True; otherwise use local clock coordinates. A naive datetime remains
            timezone-naive.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        >>> x = Pldt(["1970-01-01 08:00:00"], tz="Asia/Shanghai", unit="us")
        >>> x.toseconds().to_list()
        [28800.0]
        >>> x.toseconds(utc=True).to_list()
        [0.0]"""
        ...

    def tomicroseconds(self, utc: _Boolean=False) -> pl.Expr:
        """Return Int64 microseconds, flooring only at this explicit output.
        
        Parameters
        ----------
        utc : _Boolean
            Use UTC coordinates when True; otherwise use local clock coordinates. A naive datetime remains
            timezone-naive.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        >>> Pldt(["1970-01-01 00:00:00.000001"], unit="ns").tomicroseconds().to_list()
        [1]"""
        ...

    def toordinal(self) -> pl.Expr:
        """Return Int64 proleptic Gregorian day ordinals; missing stays null.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def timestamp(self) -> pl.Expr:
        """Return Float64 UTC seconds; naive dates use the process local zone.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        >>> Pldt(["1970-01-01 08:00:00"], tz="Asia/Shanghai").timestamp().to_list()
        [0.0]"""
        ...

    @property
    def values_naive(self) -> pl.Expr:
        """Return a plain native Datetime column of local wall coordinates.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
    def date(self) -> pl.Expr:
        """Return a native Date column, checked against its signed32-day range.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
    def time(self) -> pl.Expr:
        """Return a native Time column retaining the full time-of-day nanoseconds.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def isoformat(self, sep: str='T', timespec: str='auto') -> pl.Expr:
        """Return ISO strings with explicit precision and colon-separated offsets.
        
        Parameters
        ----------
        sep : str
            Separator between ISO date and time, normally T.
        timespec : str
            auto/hours/minutes/seconds/milliseconds/microseconds/nanoseconds, including the approved
            H/M/s/ms/us/ns aliases.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
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
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        >>> Pldt([123456789], unit="ns").strftime("%f|%.3f|%.0f").to_list()
        ['123456789|.123|']"""
        ...

    def ctime(self) -> pl.Expr:
        """Return English ctime strings, independent of the process locale.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def month_name(self, locale: str | None=None) -> pl.Expr:
        """Return compiled CLDR month names; the default language is English.
        
        Parameters
        ----------
        locale : str | None
            Supported CLDR locale such as en_US or zh_CN; None uses English. This does not change parser
            Configs.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def weekday_name(self, locale: str | None=None) -> pl.Expr:
        """Return compiled CLDR weekday names; the default language is English.
        
        Parameters
        ----------
        locale : str | None
            Supported CLDR locale such as en_US or zh_CN; None uses English. This does not change parser
            Configs.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def tzname(self) -> pl.Expr:
        """Return the native zone abbreviation at each instant, or null if naive.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def diff(self, dtobj: _DiffInput | pl.Expr, unit: str, absolute: _Boolean=False, inclusive: str='one') -> pl.Expr:
        """Return native Int64 boundary counts in the logical row domain.
        
        Parameters
        ----------
        dtobj : _DiffInput | pl.Expr
            Source/target in this factory's stated role. Actual dtype/unit/zone and independent validity
            are preserved; a scalar broadcasts only where the named factory permits it.
        unit : str
            Boundary bucket Y/Q/M/W/D/h/m/min/s/ms/us/ns; it is not a storage-unit conversion.
        absolute : _Boolean
            Original protocol argument, forwarded without inventing another interpretation.
        inclusive : str
            For diff: 'one' (ordinary signed difference), 'both' or 'neither'. For date_range: 'both',
            'left', 'right' or 'neither' endpoint inclusion.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        >>> Pldt(["2024-01-03"]).pldt.diff("2024-01-01", "D").to_list()
        [2]"""
        ...

    def round(self, freq: str='s') -> pl.Expr:
        """Date rounding on a positive fixed grid; preserves current storage unit.
        
        Parameters
        ----------
        freq : str
            Positive fixed rounding grid, for example 15min, or this range factory's approved native
            calendar/special delegated rule. A single value, never a row-wise column.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def ceil(self, freq: str='s') -> pl.Expr:
        """Date rounding on a positive fixed grid; preserves current storage unit.
        
        Parameters
        ----------
        freq : str
            Positive fixed rounding grid, for example 15min, or this range factory's approved native
            calendar/special delegated rule. A single value, never a row-wise column.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def floor(self, freq: str='s') -> pl.Expr:
        """Date rounding on a positive fixed grid; preserves current storage unit.
        
        Parameters
        ----------
        freq : str
            Positive fixed rounding grid, for example 15min, or this range factory's approved native
            calendar/special delegated rule. A single value, never a row-wise column.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def add_delta(self, delta: _DeltaInput) -> pl.Expr:
        """Build a native Expr from concrete ordinary Delta snapshots.
        
        Parameters
        ----------
        delta : _DeltaInput
            Actual Delta scalar or equal-length Delta values. All absolute fields and relative nanoseconds
            remain intact; source data is not modified.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def sub_delta(self, delta: _DeltaInput) -> pl.Expr:
        """Build a native Expr reversing only relative Delta quantities.
        
        Parameters
        ----------
        delta : _DeltaInput
            Actual Delta scalar or equal-length Delta values. All absolute fields and relative nanoseconds
            remain intact; source data is not modified.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def replace(self, year: _ExprOptionalField=None, month: _ExprOptionalField=None, day: _ExprOptionalField=None, hour: _ExprOptionalField=None, minute: _ExprOptionalField=None, second: _ExprOptionalField=None, microsecond: _ExprOptionalField=None, nanosecond: _ExprOptionalField=None, tzinfo: _Zone= ..., *, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Strictly merge date fields; omitted tzinfo retains, None removes the zone.
        
        Parameters
        ----------
        year : _ExprOptionalField
            Optional integer field/selector. None retains the source. Year may be zero/negative/wide
            within the native unit and regional backend capacity. Strict replace requires a real resulting
            date; calendar conveniences keep their separate valid upper-selection/month-end rules.
        month : _ExprOptionalField
            Optional integer field/selector. None retains the source. Month is 1-12. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        day : _ExprOptionalField
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.
        hour : _ExprOptionalField
            Optional integer field/selector. None retains the source. Hour is 0-23. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        minute : _ExprOptionalField
            Optional integer field/selector. None retains the source. Minute is 0-59. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        second : _ExprOptionalField
            Optional integer field/selector. None retains the source. Second is 0-59. Strict replace
            requires a real resulting date; calendar conveniences keep their separate valid upper-
            selection/month-end rules.
        microsecond : _ExprOptionalField
            Optional integer field/selector. None retains the source. Microsecond is 0-999999; setting it
            clears the old ns tail unless nanosecond is supplied. Strict replace requires a real resulting
            date; calendar conveniences keep their separate valid upper-selection/month-end rules.
        nanosecond : _ExprOptionalField
            Optional integer field/selector. None retains the source. Nanosecond is the additional 0-999
            tail; zero explicitly clears it. Strict replace requires a real resulting date; calendar
            conveniences keep their separate valid upper-selection/month-end rules.
        tzinfo : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        ambiguous : _ExprAmbiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        None retains an optional field; zero is real. Integer fields reject bool and floats. A scalar broadcasts; a collection must have exactly the source length, including null rows. A length-one collection is not a scalar.
        
        Examples
        --------
        >>> Pldt(["2024-01-31"]).pldt.replace(day=28, month=2).day.to_list()
        [28]"""
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
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        ambiguous : _ExprAmbiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def combine(self, time: _CombineTime | pl.Expr=None, *, tz: _Zone=None, unit: _Unit | None=None, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Compose a date Expr with a native clock, keeping a fixed schema.
        
        Parameters
        ----------
        time : _CombineTime | pl.Expr
            Source/target in this factory's stated role. Actual dtype/unit/zone and independent validity
            are preserved; a scalar broadcasts only where the named factory permits it.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        ambiguous : _ExprAmbiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def fromordinal(self, *, tz: _Zone=None, unit: _Unit | None='us', ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Resolve positional calendar components with a fixed output schema.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback.
        ambiguous : _ExprAmbiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def fromisocalendar(self, week: _ExprCalendarInput, weekday: _ExprCalendarInput, *, tz: _Zone=None, unit: _Unit | None='us', ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Resolve positional calendar components with a fixed output schema.
        
        Parameters
        ----------
        week : _ExprCalendarInput
            Integer day-of-year/ISO-week component, scalar or equal-length column. Values below 1 fail;
            approved upper convenience selection is retained. An explicit missing component makes a
            missing row.
        weekday : _ExprCalendarInput
            ISO weekday: Monday 1 through Sunday 7. Values below 1 fail, values above 7 select Sunday; an
            explicit missing component makes a missing row.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback.
        ambiguous : _ExprAmbiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def fromdayofyear(self, doy: _ExprCalendarInput, *, tz: _Zone=None, unit: _Unit | None='us', ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Resolve positional calendar components with a fixed output schema.
        
        Parameters
        ----------
        doy : _ExprCalendarInput
            Integer day-of-year/ISO-week component, scalar or equal-length column. Values below 1 fail;
            approved upper convenience selection is retained. An explicit missing component makes a
            missing row.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Output ms/us/ns, normally the us default shown in the signature. Unit capacity limits the true
            final date; no automatic fallback.
        ambiguous : _ExprAmbiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def parse(self, *, unit: _Unit | None=None, tz: _Zone=None, default: _DateValue=None, yearfirst: _Boolean | None=None, dayfirst: _Boolean | None=None, isoformat: _Boolean=True, strict: _Boolean=False, cfg: Configs | None=None, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Freeze shared String parsing rules and a static output schema.
        
        Parameters
        ----------
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        default : _DateValue
            An independently complete fallback date, read only when needed to fill text YMD/two-digit-year
            reference. It does not supply the column clock, zone or fold.
        yearfirst : _Boolean | None
            Explicit non-None boolean wins over Configs. Without either, yearfirst=True/dayfirst=False;
            False is an explicit preference.
        dayfirst : _Boolean | None
            Explicit non-None boolean wins over Configs. Without either, yearfirst=True/dayfirst=False;
            False is an explicit preference.
        isoformat : _Boolean
            Try ISO first and then shared ordinary parsing when needed; this is not ISO-only validation.
        strict : _Boolean
            Validate explicit parsed date/clock fields and conflicts; it does not replace the regional DST
            policies.
        cfg : Configs | None
            Shared Configs word/region rules. None uses the existing defaults; Expr freezes effective
            rules when it is created.
        ambiguous : _ExprAmbiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        >>> Pldt.parse(["1970-01-01T00:00:00.000000001"]).to_physical().to_list()
        [1]"""
        ...

    def strptime(self, fmt: str, *, tz: _Zone=None, unit: _Unit | None=None, cfg: Configs | None=None, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Freeze an explicit format; %f needs unit and timezone steps need tz.
        
        Parameters
        ----------
        fmt : str
            Explicit parsing format. %f reads fractional seconds through ns; excess digits and a
            deliberately requested coarser unit truncate at this format-parse exit. %Z uses explicit
            Configs rules. Expr formats with %f require unit; timezone directives require tz.
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        cfg : Configs | None
            Shared Configs word/region rules. None uses the existing defaults; Expr freezes effective
            rules when it is created.
        ambiguous : _ExprAmbiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        >>> Pldt.strptime(["1970-01-01 00:00:00.123456789"], "%Y-%m-%d %H:%M:%S.%f", unit="ns").nanosecond.to_list()
        [789]"""
        ...

    def fromseconds(self, *, tz: _Zone=None, unit: _Unit | None=None, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Read the numeric column using fixed quantity and timezone semantics.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Eager default is at least us, selecting ns for a real nonzero tail. Expr integer seconds
            default to us; floating seconds require explicit ms/us/ns in schema preparation. An explicit
            output unit must be lossless.
        ambiguous : _ExprAmbiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        >>> Pldt.fromseconds([1e-9], unit="ns").to_physical().to_list()
        [1]"""
        ...

    def frommicroseconds(self, *, tz: _Zone=None, unit: _Unit | None=None, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Read the numeric column using fixed quantity and timezone semantics.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Output storage ms/us/ns; None selects us. Input always means integer microseconds, including
            on Expr; explicit conversion must be lossless.
        ambiguous : _ExprAmbiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        >>> Pldt.frommicroseconds([1], unit="ns").to_physical().to_list()
        [1000]"""
        ...

    def fromtimestamp(self, *, tz: _Zone=None, unit: _Unit | None=None) -> pl.Expr:
        """Read the numeric column using fixed quantity and timezone semantics.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Eager default is at least us, selecting ns for a real nonzero tail. Expr integer seconds
            default to us; floating seconds require explicit ms/us/ns in schema preparation. An explicit
            output unit must be lossless.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        >>> Pldt.fromtimestamp([0], tz="UTC", unit="us").to_physical().to_list()
        [0]"""
        ...

    def utcfromtimestamp(self, *, unit: _Unit | None=None) -> pl.Expr:
        """Read the numeric column using fixed quantity and timezone semantics.
        
        Parameters
        ----------
        unit : _Unit | None
            Eager default is at least us, selecting ns for a real nonzero tail. Expr integer seconds
            default to us; floating seconds require explicit ms/us/ns in schema preparation. An explicit
            output unit must be lossless.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def fromdate(self, *, tz: _Zone=None, unit: _Unit | None=None, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Use the real native date schema, without parsing text or numeric data.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        ambiguous : _ExprAmbiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def fromdatetime(self, *, tz: _Zone=None, unit: _Unit | None=None, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Use the real native date schema, without parsing text or numeric data.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        unit : _Unit | None
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        ambiguous : _ExprAmbiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def as_unit(self, unit: _Unit, round_ok: _Boolean=True) -> pl.Expr:
        """Return an Expr with statically selected ms/us/ns resolution.
        
        Parameters
        ----------
        unit : _Unit
            Storage resolution ms/us/ns. None uses this factory's documented source-driven default; Polars
            has no Datetime(s).
        round_ok : _Boolean
            True allows this explicit rescale to floor discarded precision toward earlier ticks; False
            requires an exact conversion.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
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
        >>> Pldt([-1500], unit="ns").as_unit("us").to_physical().to_list()
        [-2]"""
        ...

    def tz_localize(self, tz: _Zone, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Interpret naive clocks, or remove a timezone while keeping clocks.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        ambiguous : _ExprAmbiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def tz_convert(self, tz: _Zone) -> pl.Expr:
        """Preserve actual instants; None removes the UTC timezone metadata.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def astimezone(self, tz: _Zone=None, *, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Convert to the target; naive input uses the process-local timezone.
        
        Parameters
        ----------
        tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        ambiguous : _ExprAmbiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

    def tz_switch(self, targ_tz: _Zone, base_tz: _Zone=None, naive: _Boolean=False, *, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
        """Convert with an explicit naive source zone, optionally removing target metadata.
        
        Parameters
        ----------
        targ_tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        base_tz : _Zone
            Supported IANA name, ZoneInfo or representable standard fixed offset. UTC aliases normalize to
            UTC. Omitted replace tzinfo retains the zone; explicit None removes it. Other None meanings
            follow this operation.
        naive : _Boolean
            Remove target timezone metadata after the requested conversion when True.
        ambiguous : _ExprAmbiguous
            Repeated-local-time policy: 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean
            mask. True/False select the actual ordered candidates; infer preserves logical row order.
        nonexistent : _Nonexistent
            One missing-local-time policy: 'raise', 'NaT', 'shift_forward', 'shift_backward' or a
            timedelta. Nearest-boundary shifts use the current unit; no per-row strategy list.
        
        Returns
        -------
        pl.Expr
            Native expression for Expr receivers, evaluated by Polars at select/collect; eager calls
            return the documented column/table role.
        
        Raises
        ------
        TypeError
            A supplied type, integer/bool protocol or parameter role is unsupported.
        ValueError
            A field, shape, precision reduction or localization rule is invalid.
        OverflowError
            The true final result exceeds the current unit/target capacity."""
        ...

