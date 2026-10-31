"""Public type information for integer-backed Pddt date columns."""
from collections.abc import Iterable
import datetime as _dt
from typing import Generic, TypeVar, Hashable, Literal, SupportsIndex, SupportsFloat, TypeAlias, overload
from types import NotImplementedType
from typing_extensions import Self
import numpy as np
import pandas as pd
from .parser import Configs
from .delta import Delta

_DateValue: TypeAlias = str | _dt.date | _dt.datetime | np.datetime64 | SupportsIndex | float | np.float16 | np.float32 | np.float64 | None
_DateCollection: TypeAlias = Iterable[_DateValue] | np.ndarray | pd.Series | pd.Index | pd.api.extensions.ExtensionArray
_Boolean: TypeAlias = bool | np.bool_
_BoolCollection: TypeAlias = Iterable[_Boolean] | np.ndarray | pd.Series | pd.Index | pd.api.extensions.ExtensionArray
_Ambiguous: TypeAlias = Literal["raise", "NaT", "infer"] | _Boolean | _BoolCollection
_Nonexistent: TypeAlias = Literal["raise", "NaT", "shift_forward", "shift_backward"] | _dt.timedelta

from pandas._libs.missing import NAType as _NAType
from pandas._libs.tslibs.nattype import NaTType as _NaTType
_Missing: TypeAlias = None | _NAType | _NaTType
_Column: TypeAlias = np.ndarray | pd.Series | pd.Index | pd.api.extensions.ExtensionArray
_IntegerInput: TypeAlias = SupportsIndex | _Missing | Iterable[SupportsIndex | _Missing] | _Column
_NumericInput: TypeAlias = SupportsIndex | SupportsFloat | _Missing | Iterable[SupportsIndex | SupportsFloat | _Missing] | _Column
_ActualDateInput: TypeAlias = _dt.date | _Missing | Iterable[_dt.date | _Missing] | _Column
_DatetimeInput: TypeAlias = _dt.datetime | _Missing | Iterable[_dt.datetime | _Missing] | _Column
_NumpyInput: TypeAlias = np.datetime64 | _Missing | Iterable[np.datetime64 | _Missing] | _Column
_IsoInput: TypeAlias = str | _Missing | Iterable[str | _Missing] | _Column
_CombineDate: TypeAlias = str | _dt.date | np.datetime64 | int | float | _Missing | Iterable[str | _dt.date | np.datetime64 | int | float | _Missing] | _Column
_CombineTime: TypeAlias = str | _dt.time | _dt.datetime | np.datetime64 | int | float | _Missing | Iterable[str | _dt.time | _dt.datetime | np.datetime64 | int | float | _Missing] | _Column

_IntegerArgument: TypeAlias = SupportsIndex | Iterable[SupportsIndex] | _Column
_OptionalField: TypeAlias = SupportsIndex | None | Iterable[SupportsIndex | None] | _Column
_StoredSelection: TypeAlias = SupportsIndex | str | None | Iterable[SupportsIndex | str | None] | _Column

class Pddt(pd.DatetimeIndex):
    """A date index with explicit resolution and shared Rust calendar rules.

    Parameters
    ----------
    data : one-dimensional collection
        Text, date, datetime, integer ticks or supported native temporal columns.
        Collections may mix supported date values. A scalar belongs in [value].
    unit : {'s', 'ms', 'us', 'ns'}, optional
        Storage resolution. Text and datetime normally start at microseconds;
        nine-digit text preserves nanoseconds. Native dates retain their unit.
        Bare numbers mean ticks in unit, or nanoseconds when unit is omitted.
        Explicit construction must preserve all source precision.
    tz : tzinfo or str, optional
        Target timezone. Naive date fields are localized; aware dates and numeric
        ticks retain their actual instants. No target means no local-zone guess.
    default : date-like scalar, optional
        A complete independent date used only to fill missing text YMD fields.
        It is prepared once when first needed, not for native or empty inputs.
    yearfirst, dayfirst : bool or numpy.bool_ or None, optional
        Explicit preferences override Configs; None uses Configs, then True/False.
    isoformat : bool or numpy.bool_, default True
        Try ISO first; ordinary shared parsing may still follow.
    strict : bool or numpy.bool_, default False
        Reject invalid/conflicting explicit fields when True. This is unrelated
        to the regional daylight-saving policies.
    cfg : Configs, optional
        Shared word and registered-region rules used by the Rust text parser.
    copy : bool or numpy.bool_, default False
        Isolate source data when True. False allows safe ownership sharing.
    name : hashable, optional
        Index name. By default a source Index or Series name is retained.
    freq : frequency, optional
        Frequency metadata validated by the final pandas index constructor.
    ambiguous, nonexistent : policy, default 'raise'
        Policies for interpreting regional local dates. Already-known instants
        do not need another ambiguity decision.

    Notes
    -----
    Numeric date data, integer fields and counts reject boolean values. Integer-only fields use the index protocol and reject floats, including 1.0. Bare input ticks separately allow whole values of the documented floating types. Boolean options accept only bool or numpy.bool_; DST strategy strings and true boolean masks follow their own documented roles.

    Returns
    -------
    Pddt
        A real DatetimeIndex subclass with original order and missing positions.

    Examples
    --------
    >>> Pddt([1], unit="ms").asi8.tolist()
    [1]
    >>> Pddt(["0000-01-01"], unit="us").year.tolist()
    [0]
    """
    def __new__(cls, data: _DateCollection, *, unit: str | None = None, name: Hashable | None = None, copy: _Boolean = False, freq: object = None, tz: _dt.tzinfo | str | None = None, default: str | _dt.date | _dt.datetime | int | float | np.datetime64 | None = None, yearfirst: _Boolean | None = None, dayfirst: _Boolean | None = None, isoformat: _Boolean = True, strict: _Boolean = False, cfg: Configs | None = None, ambiguous: _Ambiguous = "raise", nonexistent: _Nonexistent = "raise") -> Self:
        """A date index with explicit resolution and shared Rust calendar rules.

        Parameters
        ----------
        data : one-dimensional collection
            Text, date, datetime, integer ticks or supported native temporal columns.
            Collections may mix supported date values. A scalar belongs in [value].
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Storage resolution. Text and datetime normally start at microseconds;
            nine-digit text preserves nanoseconds. Native dates retain their unit.
            Bare numbers mean ticks in unit, or nanoseconds when unit is omitted.
            Explicit construction must preserve all source precision.
        tz : tzinfo or str, optional
            Target timezone. Naive date fields are localized; aware dates and numeric
            ticks retain their actual instants. No target means no local-zone guess.
        default : date-like scalar, optional
            A complete independent date used only to fill missing text YMD fields.
            It is prepared once when first needed, not for native or empty inputs.
        yearfirst, dayfirst : bool or numpy.bool_ or None, optional
            Explicit preferences override Configs; None uses Configs, then True/False.
        isoformat : bool or numpy.bool_, default True
            Try ISO first; ordinary shared parsing may still follow.
        strict : bool or numpy.bool_, default False
            Reject invalid/conflicting explicit fields when True. This is unrelated
            to the regional daylight-saving policies.
        cfg : Configs, optional
            Shared word and registered-region rules used by the Rust text parser.
        copy : bool or numpy.bool_, default False
            Isolate source data when True. False allows safe ownership sharing.
        name : hashable, optional
            Index name. By default a source Index or Series name is retained.
        freq : frequency, optional
            Frequency metadata validated by the final pandas index constructor.
        ambiguous, nonexistent : policy, default 'raise'
            Policies for interpreting regional local dates. Already-known instants
            do not need another ambiguity decision.

        Notes
        -----
        Numeric date data, integer fields and counts reject boolean values. Integer-only fields use the index protocol and reject floats, including 1.0. Bare input ticks separately allow whole values of the documented floating types. Boolean options accept only bool or numpy.bool_; DST strategy strings and true boolean masks follow their own documented roles.

        Returns
        -------
        Pddt
            A real DatetimeIndex subclass with original order and missing positions.

        Examples
        --------
        >>> Pddt([1], unit="ms").asi8.tolist()
        [1]
        >>> Pddt(["0000-01-01"], unit="us").year.tolist()
        [0]
        """
        ...

    @classmethod
    def parse(cls, data: _DateCollection, *, unit: str | None = None, name: Hashable | None = None, copy: _Boolean = False, freq: object = None, tz: _dt.tzinfo | str | None = None, default: str | _dt.date | _dt.datetime | int | float | np.datetime64 | None = None, yearfirst: _Boolean | None = None, dayfirst: _Boolean | None = None, isoformat: _Boolean = True, strict: _Boolean = False, cfg: Configs | None = None, ambiguous: _Ambiguous = "raise", nonexistent: _Nonexistent = "raise") -> Self:
        """Parse a collection using the same date, unit and timezone rules as Pddt.

        Parameters
        ----------
        data : one-dimensional collection
            Text, date, datetime, integer ticks or supported native temporal columns.
            Collections may mix supported date values. A scalar belongs in [value].
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Storage resolution. Text and datetime normally start at microseconds;
            nine-digit text preserves nanoseconds. Native dates retain their unit.
            Bare numbers mean ticks in unit, or nanoseconds when unit is omitted.
            Explicit construction must preserve all source precision.
        tz : tzinfo or str, optional
            Target timezone. Naive date fields are localized; aware dates and numeric
            ticks retain their actual instants. No target means no local-zone guess.
        default : date-like scalar, optional
            A complete independent date used only to fill missing text YMD fields.
            It is prepared once when first needed, not for native or empty inputs.
        yearfirst, dayfirst : bool or numpy.bool_ or None, optional
            Explicit preferences override Configs; None uses Configs, then True/False.
        isoformat : bool or numpy.bool_, default True
            Try ISO first; ordinary shared parsing may still follow.
        strict : bool or numpy.bool_, default False
            Reject invalid/conflicting explicit fields when True. This is unrelated
            to the regional daylight-saving policies.
        cfg : Configs, optional
            Shared word and registered-region rules used by the Rust text parser.
        copy : bool or numpy.bool_, default False
            Isolate source data when True. False allows safe ownership sharing.
        name : hashable, optional
            Index name. By default a source Index or Series name is retained.
        freq : frequency, optional
            Frequency metadata validated by the final pandas index constructor.
        ambiguous, nonexistent : policy, default 'raise'
            Policies for interpreting regional local dates. Already-known instants
            do not need another ambiguity decision.

        Notes
        -----
        Numeric date data, integer fields and counts reject boolean values. Integer-only fields use the index protocol and reject floats, including 1.0. Bare input ticks separately allow whole values of the documented floating types. Boolean options accept only bool or numpy.bool_; DST strategy strings and true boolean masks follow their own documented roles.

        Returns
        -------
        Pddt
            A real DatetimeIndex subclass with original order and missing positions.

        Examples
        --------
        >>> Pddt([1], unit="ms").asi8.tolist()
        [1]
        >>> Pddt(["0000-01-01"], unit="us").year.tolist()
        [0]
        """
        ...

    def as_unit(self, unit: str, round_ok: _Boolean = True) -> Self:
        """Return dates at another storage resolution.

        Parameters
        ----------
        unit : {'s', 'ms', 'us', 'ns'}
            Requested resolution. Capacity errors never silently change the unit.
        round_ok : bool or numpy.bool_, default True
            Permit discarding finer digits toward the earlier tick. False
            requires an exact conversion.

        Returns
        -------
        Pddt
            Converted dates preserving the name, timezone and missing positions.

        Examples
        --------
        >>> Pddt(np.array([-1500], dtype='datetime64[ns]')).as_unit('us').asi8.tolist()
        [-2]
        """
        ...

    @property
    def tzinfo(self) -> _dt.tzinfo | None:
        """The timezone shared by this column, or None for naive dates.

        Returns
        -------
        datetime.tzinfo or None
            Actual timezone metadata, independent of any single row's offset.
        """
        ...

    @property
    def tz_available(self) -> set[str]:
        """The region names available to ZoneInfo on this system.

        Returns
        -------
        set[str]
            Available IANA timezone keys. This does not read the local clock.
        """
        ...

    def is_utc(self) -> bool:
        """Return whether this column uses datetime.timezone.utc.

        Returns
        -------
        bool
            One metadata result for the whole column, including an empty one.
        """
        ...

    def is_local(self) -> bool:
        """Return whether the column uses the cached process-local timezone.

        Returns
        -------
        bool
            False for a naive column. The local timezone is loaded only when
            a timezone-bearing column actually needs this query.
        """
        ...

    # P10 accepts named/actual zones, not pandas integer-offset shorthand.
    def tz_convert(self, tz: _dt.tzinfo | str | None) -> Self:  # type: ignore[override]
        """Convert aware dates to another timezone, preserving actual instants.

        Parameters
        ----------
        tz : datetime.tzinfo, str or None
            Target timezone. None converts to UTC and removes timezone metadata.
            A naive source is an error; use tz_localize to interpret its clocks.

        Returns
        -------
        Pddt
            Same instants, unit, name and missing positions in this date class.

        Raises
        ------
        TypeError
            The source is naive or the timezone type is unsupported.

        Examples
        --------
        >>> Pddt([0], unit="s", tz="UTC").tz_convert("Asia/Shanghai").hour.tolist()
        [8]
        """
        ...

    # P10 accepts named/actual zones, not pandas integer-offset shorthand.
    def tz_localize(self, tz: _dt.tzinfo | str | None, ambiguous: _Ambiguous = "raise", nonexistent: _Nonexistent = "raise") -> Self:  # type: ignore[override]
        """Interpret naive clocks in a region, or remove a zone without moving them.

        Parameters
        ----------
        tz : datetime.tzinfo, str or None
            Region or offset to attach to naive local dates. None removes a zone
            and keeps local clock fields. Aware dates cannot receive a new zone.
        ambiguous : bool, numpy.bool_, str or one-dimensional boolean collection
            'raise', 'NaT' or 'infer', or actual candidate choices. A collection
            matches every input position, including ordinary and missing rows.
        nonexistent : str or timedelta, default 'raise'
            'raise', 'NaT', 'shift_forward', 'shift_backward', or one clock shift.
            Boundary shifts select the nearest existing boundary at this unit.

        Returns
        -------
        Pddt
            Localized dates preserving unit, name and original missing positions.

        Raises
        ------
        TypeError
            A policy has an unsupported type, or an aware source is relocalized.
        ValueError
            A local time cannot be resolved or a result loses unit precision.
        OverflowError
            A result exceeds the current unit or dynamic timezone range.
        """
        ...

    def astimezone(self, tz: _dt.tzinfo | str | None = None, *, ambiguous: _Ambiguous = "raise", nonexistent: _Nonexistent = "raise") -> Self:
        """Convert to a zone; a naive source is first interpreted in local time.

        Parameters
        ----------
        tz : datetime.tzinfo, str or None, default None
            Target timezone. None means the process-local timezone.
        ambiguous : bool, numpy.bool_, str or boolean collection, default 'raise'
            Policy used only if the naive source needs regional interpretation.
        nonexistent : str or timedelta, default 'raise'
            Missing-local-time policy used only for that source interpretation.

        Returns
        -------
        Pddt
            The same actual instants displayed in the target zone.

        Raises
        ------
        ValueError
            A required local time cannot be resolved.
        TypeError
            A timezone or policy has an unsupported type.
        """
        ...

    def tz_switch(self, targ_tz: _dt.tzinfo | str | None, base_tz: _dt.tzinfo | str | None = None, naive: _Boolean = False, *, ambiguous: _Ambiguous = "raise", nonexistent: _Nonexistent = "raise") -> Self:
        """Convert between zones, optionally keeping the final clock without a zone.

        Parameters
        ----------
        targ_tz : datetime.tzinfo, str or None
            Target zone. None only removes the current zone, preserving its clock.
        base_tz : datetime.tzinfo, str or None, default None
            Required source interpretation for naive dates and a non-None target.
            An aware source already defines its actual instants and ignores it.
        naive : bool or numpy.bool_, default False
            Remove the target zone after conversion, keeping the target clock.
        ambiguous : bool, numpy.bool_, str or boolean collection, default 'raise'
            Policy for a required naive source interpretation.
        nonexistent : str or timedelta, default 'raise'
            Policy for missing local times in that source interpretation.

        Returns
        -------
        Pddt
            Converted dates of this class, with the same unit and name.

        Raises
        ------
        ValueError
            A naive source has no base_tz or cannot be resolved by the policies.
        TypeError
            A flag, timezone or policy has an unsupported type.
        """
        ...

    @classmethod
    def now(cls, size: SupportsIndex, *, tz: _dt.tzinfo | str | None = None, unit: str | None = None, name: Hashable | None = None) -> Self:
        """Repeat one current system time in this column's chosen resolution.
        
        Parameters
        ----------
        size : integer
            Nonnegative number of identical dates. Uses the index protocol;
            booleans and floats are rejected. Zero does not read the clock.
        tz : datetime.tzinfo, str or None, default None
            Target zone. None returns the complete local naive clock.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Default us. Coarser units take the earlier boundary. Nanoseconds
            retain actual system precision, without inventing finer digits.
        name : hashable, optional
            Name of the index.
        
        Returns
        -------
        Pddt
            size copies of one current value, constructed once as this class.
        
        Examples
        --------
        >>> Pddt.now(0, unit="ns").unit
        'ns'
        """
        ...

    @classmethod
    def today(cls, size: SupportsIndex, *, unit: str | None = None, name: Hashable | None = None) -> Self:
        """Repeat the complete current local time, as datetime.today does.
        
        Parameters
        ----------
        size : integer
            Nonnegative number of repeated dates; zero does not read the clock.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Default us. Coarser units take the earlier boundary.
        name : hashable, optional
            Name of the index.
        
        Returns
        -------
        Pddt
            Local naive dates retaining the clock, microseconds and any supported
            system nanoseconds. This method does not normalize to midnight.
        """
        ...

    @classmethod
    def utcnow(cls, size: SupportsIndex, *, unit: str | None = None, name: Hashable | None = None) -> Self:
        """Repeat one current actual time with datetime.timezone.utc.
        
        Parameters
        ----------
        size : integer
            Nonnegative number of repeated dates; zero does not read the clock.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Default us. Nanoseconds retain the actual system clock's digits.
        name : hashable, optional
            Name of the index.
        
        Returns
        -------
        Pddt
            An aware UTC column. All valid rows contain exactly the same value.
        """
        ...

    @classmethod
    def fromseconds(cls, seconds: _NumericInput, *, size: SupportsIndex | None = None, tz: _dt.tzinfo | str | None = None, unit: str | None = None, name: Hashable | None = None, ambiguous: _Ambiguous = 'raise', nonexistent: _Nonexistent = 'raise') -> Self:
        """Build dates from seconds on the naive epoch clock, optionally attaching tz.
        
        Parameters
        ----------
        seconds : numeric scalar or one-dimensional collection
            Seconds from 1970-01-01 00:00 without a host-local conversion.
            Integers remain exact; fractional seconds retain up to nanoseconds.
            Textual numbers and booleans are rejected. Date missing values stay NaT.
        size : integer, optional
            Required for a scalar; omitted for a collection. Scalars are prepared
            once and repeated. A length-one collection is still a collection.
        tz : datetime.tzinfo, str or None, default None
            Attach this zone to the computed clock fields. None keeps them naive.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Output resolution, independent of the seconds input unit. Defaults
            to us, or ns for a real nonzero nanosecond tail; no automatic fallback.
        name : hashable, optional
            Name of the result; a source Series or Index name is retained by default.
        ambiguous : bool, numpy.bool_, str or boolean collection, default 'raise'
            Repeated-local-time strategy, if attaching a region needs it.
        nonexistent : str or timedelta, default 'raise'
            Missing-local-time strategy for that region.
        
        Returns
        -------
        Pddt
            Dates on the requested clock, unit and timezone.
        
        Examples
        --------
        >>> Pddt.fromseconds(0, size=1, tz="Asia/Shanghai").hour.tolist()
        [0]
        >>> Pddt.fromseconds([1.5], unit="ms").asi8.tolist()
        [1500]
        """
        ...

    @classmethod
    def frommicroseconds(cls, us: _IntegerInput, *, size: SupportsIndex | None = None, tz: _dt.tzinfo | str | None = None, unit: str | None = None, name: Hashable | None = None, ambiguous: _Ambiguous = 'raise', nonexistent: _Nonexistent = 'raise') -> Self:
        """Build dates from integer microseconds on the naive epoch clock.
        
        Parameters
        ----------
        us : integer scalar or one-dimensional collection
            Microseconds from naive 1970-01-01. Integer index values are accepted;
            all finite floats, booleans and textual numbers are rejected.
        size : integer, optional
            Required for a scalar and omitted for a collection.
        tz : datetime.tzinfo, str or None, default None
            Zone to attach to the calculated clock fields, without an instant conversion.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Output resolution, default us. Explicit conversion must be lossless.
        name : hashable, optional
            Name of the result, otherwise inherited from a source column.
        ambiguous : bool, numpy.bool_, str or boolean collection, default 'raise'
            Strategy when the attached region repeats a local time.
        nonexistent : str or timedelta, default 'raise'
            Strategy when that local time does not exist.
        
        Returns
        -------
        Pddt
            Dates of this class, preserving missing input positions.
        
        Examples
        --------
        >>> Pddt.frommicroseconds(0, size=1, tz="Asia/Shanghai").hour.tolist()
        [0]
        """
        ...

    @classmethod
    def fromtimestamp(cls, ts: _NumericInput, *, size: SupportsIndex | None = None, tz: _dt.tzinfo | str | None = None, unit: str | None = None, name: Hashable | None = None) -> Self:
        """Build from real UTC epoch seconds, converting to a zone or local naive time.
        
        Parameters
        ----------
        ts : numeric scalar or one-dimensional collection
            Actual seconds elapsed since 1970-01-01T00:00:00Z. No textual numbers
            or booleans. Missing date values propagate to NaT.
        size : integer, optional
            Required for a scalar; omitted for a collection.
        tz : datetime.tzinfo, str or None, default None
            Display zone. None uses local time and removes its zone metadata.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Output resolution. Defaults to us, or ns for a real nanosecond tail.
        name : hashable, optional
            Name of the result, otherwise inherited from a source column.
        
        Returns
        -------
        Pddt
            Same actual instants in the requested display coordinates.
        
        Examples
        --------
        >>> Pddt.fromtimestamp(0, size=1, tz="Asia/Shanghai").hour.tolist()
        [8]
        """
        ...

    @classmethod
    def utcfromtimestamp(cls, ts: _NumericInput, *, size: SupportsIndex | None = None, unit: str | None = None, name: Hashable | None = None) -> Self:
        """Build aware UTC dates from real POSIX seconds.
        
        Parameters
        ----------
        ts : numeric scalar or one-dimensional collection
            Actual seconds since the UTC epoch; missing date positions stay NaT.
        size : integer, optional
            Required for a scalar and omitted for a collection.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Output resolution, default us or ns for an actual finer tail.
        name : hashable, optional
            Name of the result, otherwise inherited from a source column.
        
        Returns
        -------
        Pddt
            Dates of this class with datetime.timezone.utc metadata.
        """
        ...

    @classmethod
    def fromdate(cls, dt: _ActualDateInput, *, size: SupportsIndex | None = None, tz: _dt.tzinfo | str | None = None, unit: str | None = None, name: Hashable | None = None, ambiguous: _Ambiguous = 'raise', nonexistent: _Nonexistent = 'raise') -> Self:
        """Take the year, month and day from real date values.
        
        Parameters
        ----------
        dt : date, datetime or corresponding native pandas/Polars column
            Clock digits and source timezone are discarded. An explicit tz describes midnight in that zone. Missing positions remain NaT.
        size : integer, optional
            Required for a scalar; omitted for a collection.
        tz : datetime.tzinfo, str or None, default None
            Optional timezone, with the field interpretation described above.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Output resolution. Native precision is retained by default;
            explicitly selected units must preserve the source exactly.
        name : hashable, optional
            Result name, otherwise inherited from a source column.
        ambiguous : bool, numpy.bool_, str or boolean collection, default 'raise'
            Candidate policy when interpreting a regional local clock.
        nonexistent : str or timedelta, default 'raise'
            Policy for a regional local clock that does not exist.
        
        Returns
        -------
        Pddt
            Dates of this class, in original order and with missing positions.
        """
        ...

    @classmethod
    def fromdatetime(cls, dt: _DatetimeInput, *, size: SupportsIndex | None = None, tz: _dt.tzinfo | str | None = None, unit: str | None = None, name: Hashable | None = None, ambiguous: _Ambiguous = 'raise', nonexistent: _Nonexistent = 'raise') -> Self:
        """Keep local fields from real datetime values.
        
        Parameters
        ----------
        dt : datetime, Pydt, pandas Timestamp or native Datetime column
            Without tz, retain source zones and known instants. An explicit tz replaces the zone while keeping clock fields, including nanoseconds. Missing positions remain NaT.
        size : integer, optional
            Required for a scalar; omitted for a collection.
        tz : datetime.tzinfo, str or None, default None
            Optional timezone, with the field interpretation described above.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Output resolution. Native precision is retained by default;
            explicitly selected units must preserve the source exactly.
        name : hashable, optional
            Result name, otherwise inherited from a source column.
        ambiguous : bool, numpy.bool_, str or boolean collection, default 'raise'
            Candidate policy when interpreting a regional local clock.
        nonexistent : str or timedelta, default 'raise'
            Policy for a regional local clock that does not exist.
        
        Returns
        -------
        Pddt
            Dates of this class, in original order and with missing positions.
        """
        ...

    @classmethod
    def fromdatetime64(cls, dt64: _NumpyInput, *, size: SupportsIndex | None = None, tz: _dt.tzinfo | str | None = None, unit: str | None = None, name: Hashable | None = None, ambiguous: _Ambiguous = 'raise', nonexistent: _Nonexistent = 'raise') -> Self:
        """Decode real NumPy datetime64 values and their native units.
        
        Parameters
        ----------
        dt64 : NumPy datetime64 scalar or one-dimensional collection
            An explicit tz is attached to decoded local fields; it does not reinterpret the source as UTC. Missing positions remain NaT.
        size : integer, optional
            Required for a scalar; omitted for a collection.
        tz : datetime.tzinfo, str or None, default None
            Optional timezone, with the field interpretation described above.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Output resolution. Native precision is retained by default;
            explicitly selected units must preserve the source exactly.
        name : hashable, optional
            Result name, otherwise inherited from a source column.
        ambiguous : bool, numpy.bool_, str or boolean collection, default 'raise'
            Candidate policy when interpreting a regional local clock.
        nonexistent : str or timedelta, default 'raise'
            Policy for a regional local clock that does not exist.
        
        Returns
        -------
        Pddt
            Dates of this class, in original order and with missing positions.
        """
        ...

    @classmethod
    def fromordinal(cls, ordinal: _IntegerInput, *, size: SupportsIndex | None = None, tz: _dt.tzinfo | str | None = None, unit: str | None = None, name: Hashable | None = None, ambiguous: _Ambiguous = 'raise', nonexistent: _Nonexistent = 'raise') -> Self:
        """Build midnights from continuous Gregorian day numbers.
        
        Day 1 is 0001-01-01; zero and negative days are real earlier dates.
        
        Parameters
        ----------
        ordinal : integer or one-dimensional integer collection
            Calendar component. Missing column elements propagate to NaT.
        size : integer, optional
            Required when all components are scalars. With any collection,
            scalars broadcast and all collections must have the same length.
        tz : datetime.tzinfo, str or None, default None
            Optional timezone attached to the resulting local midnights.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Output resolution, default us. Capacity errors never change the unit.
        name : hashable, optional
            Result name, otherwise inherited from a source column.
        ambiguous : bool, numpy.bool_, str or boolean collection, default 'raise'
            Candidate policy for a repeated regional midnight.
        nonexistent : str or timedelta, default 'raise'
            Policy for a missing regional midnight.
        
        Returns
        -------
        Pddt
            Native calendar results, including representable zero or negative years.
        """
        ...

    @classmethod
    def fromisocalendar(cls, year: _IntegerInput, week: _IntegerInput, weekday: _IntegerInput, *, size: SupportsIndex | None = None, tz: _dt.tzinfo | str | None = None, unit: str | None = None, name: Hashable | None = None, ambiguous: _Ambiguous = 'raise', nonexistent: _Nonexistent = 'raise') -> Self:
        """Build midnights from ISO year, week and weekday.
        
        Week and weekday must be positive. High week values select the year's last actual ISO week; high weekdays select Sunday.
        
        Parameters
        ----------
        year : integer or one-dimensional integer collection
            Calendar component. Missing column elements propagate to NaT.
        week : integer or one-dimensional integer collection
            Calendar component. Missing column elements propagate to NaT.
        weekday : integer or one-dimensional integer collection
            Calendar component. Missing column elements propagate to NaT.
        size : integer, optional
            Required when all components are scalars. With any collection,
            scalars broadcast and all collections must have the same length.
        tz : datetime.tzinfo, str or None, default None
            Optional timezone attached to the resulting local midnights.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Output resolution, default us. Capacity errors never change the unit.
        name : hashable, optional
            Result name, otherwise inherited from a source column.
        ambiguous : bool, numpy.bool_, str or boolean collection, default 'raise'
            Candidate policy for a repeated regional midnight.
        nonexistent : str or timedelta, default 'raise'
            Policy for a missing regional midnight.
        
        Returns
        -------
        Pddt
            Native calendar results, including representable zero or negative years.
        """
        ...

    @classmethod
    def fromdayofyear(cls, year: _IntegerInput, doy: _IntegerInput, *, size: SupportsIndex | None = None, tz: _dt.tzinfo | str | None = None, unit: str | None = None, name: Hashable | None = None, ambiguous: _Ambiguous = 'raise', nonexistent: _Nonexistent = 'raise') -> Self:
        """Build midnights from year and day of year.
        
        Day of year must be positive; high values select that year's final day.
        
        Parameters
        ----------
        year : integer or one-dimensional integer collection
            Calendar component. Missing column elements propagate to NaT.
        doy : integer or one-dimensional integer collection
            Calendar component. Missing column elements propagate to NaT.
        size : integer, optional
            Required when all components are scalars. With any collection,
            scalars broadcast and all collections must have the same length.
        tz : datetime.tzinfo, str or None, default None
            Optional timezone attached to the resulting local midnights.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Output resolution, default us. Capacity errors never change the unit.
        name : hashable, optional
            Result name, otherwise inherited from a source column.
        ambiguous : bool, numpy.bool_, str or boolean collection, default 'raise'
            Candidate policy for a repeated regional midnight.
        nonexistent : str or timedelta, default 'raise'
            Policy for a missing regional midnight.
        
        Returns
        -------
        Pddt
            Native calendar results, including representable zero or negative years.
        """
        ...

    @classmethod
    def fromisoformat(cls, dtstr: _IsoInput, *, size: SupportsIndex | None = None, tz: _dt.tzinfo | str | None = None, unit: str | None = None, name: Hashable | None = None, ambiguous: _Ambiguous = 'raise', nonexistent: _Nonexistent = 'raise') -> Self:
        """Build from complete ISO text, without ordinary-text fallback.

        Parameters
        ----------
        dtstr : str or one-dimensional text collection
            Strict ISO calendar, compact, week or day-of-year dates. A single
            date/time separator character is accepted. Real nanoseconds and
            numeric timezone offsets are preserved. Explicit dates must be valid.
        size : integer, optional
            Required for a scalar and omitted for a collection.
        tz : datetime.tzinfo, str or None, default None
            Optional common target. Naive fields are localized in this zone;
            aware values retain their instant and convert to it. None preserves
            a common source zone and rejects incompatible mixed sources.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Output resolution. Defaults to us, or ns for text beyond six digits;
            an explicitly selected resolution must retain the parsed value.
        name : hashable, optional
            Name of the resulting date column.

        ambiguous : bool, numpy.bool_, str or boolean collection, default 'raise'
            Candidate policy when naive fields fall in a repeated local time.
        nonexistent : str or timedelta, default 'raise'
            Missing-local-time policy when naive fields are attached to tz.

        Returns
        -------
        Pddt
            ISO dates of this class, retaining order and date-missing positions.

        Examples
        --------
        >>> Pddt.fromisoformat("2024-002", size=1).day.tolist()
        [2]
        >>> Pddt.fromisoformat("2024-01-02x12:30.5", size=1).microsecond.tolist()
        [500000]
        >>> Pddt.fromisoformat(["2024-01-02T12:30+08:00", "2024-01-02T04:30Z"], tz="UTC").hour.tolist()
        [4, 4]
        """
        ...

    @classmethod
    def combine(cls, date: _CombineDate = None, time: _CombineTime = None, *, size: SupportsIndex | None = None, tz: _dt.tzinfo | str | None = None, unit: str | None = None, name: Hashable | None = None, ambiguous: _Ambiguous = 'raise', nonexistent: _Nonexistent = 'raise') -> Self:
        """Combine date fields with clocks, preserving real clock precision.
        
        Parameters
        ----------
        date : date-like scalar or one-dimensional collection, optional
            Source of year, month and day. A scalar None uses local today;
            missing collection elements remain NaT. Source timezone is ignored.
        time : time-like scalar or one-dimensional collection, optional
            Source of clock fields and timezone. None means midnight. Datetime
            and Timestamp supply their clocks, including nanoseconds. Native
            Polars Time columns are supported here; source fold is not a policy.
        size : integer, optional
            Required if both components are scalars. Otherwise scalar components
            broadcast, collections must be equal length, and size is omitted.
        tz : datetime.tzinfo, str or None, default None
            Replace the time source zone while preserving clock fields. None
            keeps that source zone. The date source zone is never inherited.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Output resolution, default us or ns for actual submicrosecond data.
            Explicit units must preserve the complete combined result.
        name : hashable, optional
            Result name, otherwise inherited from the first named source.
        ambiguous : bool, numpy.bool_, str or boolean collection, default 'raise'
            Candidate selection for repeated local clocks, independent of fold.
        nonexistent : str or timedelta, default 'raise'
            Missing-local-time policy for the newly combined date and clock.
        
        Returns
        -------
        Pddt
            One combined date column with original row order and missing values.
        
        Examples
        --------
        >>> Pddt.combine(["2024-01-02", "2024-01-03"], "12:30").hour.tolist()
        [12, 12]
        """
        ...

    @classmethod
    def strptime(cls, dtstr: _IsoInput, fmt: str, *, size: SupportsIndex | None = None, tz: _dt.tzinfo | str | None = None, unit: str | None = None, name: Hashable | None = None, cfg: Configs | None = None, ambiguous: _Ambiguous = "raise", nonexistent: _Nonexistent = "raise") -> Self:
        """Read dates from a format using current Configs words and native fields.

        Parameters
        ----------
        dtstr : str or one-dimensional text collection
            Text to match completely. Missing date values propagate to NaT.
        fmt : str
            Date/time directives, literals and whitespace. Numeric dates and
            week calendars are read directly. Missing fields use 1900-01-01
            and zero clock fields. Names use the effective Configs word rules.
        size : integer, optional
            Required for a scalar; omitted for a collection.
        tz : datetime.tzinfo, str or None, default None
            Optional common target. Naive fields are localized in this zone;
            aware values retain their instant and convert to it. None preserves
            a common source zone and rejects incompatible mixed sources.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Output resolution, default us or ns for an actual nanosecond tail.
            Fractional digits are read fully and truncated to this resolution
            only after the timezone and complete date have been interpreted.
        name : hashable, optional
            Name of the result, otherwise inherited from a source column.
        cfg : Configs or None, default None
            Current month, weekday, AM/PM and explicitly registered timezone
            names. None uses the library's default words. No local-zone guess.
        ambiguous : bool, numpy.bool_, str or boolean collection, default 'raise'
            Candidate policy for a repeated local regional time.
        nonexistent : str or timedelta, default 'raise'
            Missing-local-time policy for the parsed regional fields.

        Returns
        -------
        Pddt
            Formatted dates with original order, precision and missing positions.

        Examples
        --------
        >>> Pddt.strptime("2024-05-07", "%Y-%m-%d", size=1).day.tolist()
        [7]
        >>> Pddt.strptime("1970-01-01 00:00:00.123456789", "%Y-%m-%d %H:%M:%S.%f", size=1, unit="us").asi8.tolist()
        [123456]
        >>> Pddt.strptime(["2024-01-02 12:00+0800", "2024-01-02 12:00+0900"], "%Y-%m-%d %H:%M%z", tz="UTC").hour.tolist()
        [4, 3]
        """
        ...

    @classmethod
    def date_range(cls, start: _DateValue = None, *, end: _DateValue = None, periods: SupportsIndex | None = None, freq: object = None, tz: _dt.tzinfo | str | None = None, normalize: _Boolean = False, inclusive: Literal["both", "left", "right", "neither"] = "both", unit: str | None = None, name: Hashable | None = None, default: _DateValue = None, yearfirst: _Boolean | None = None, dayfirst: _Boolean | None = None, isoformat: _Boolean = True, strict: _Boolean = False, cfg: Configs | None = None, ambiguous: _Ambiguous = "raise", nonexistent: _Nonexistent = "raise") -> Self:
        """Generate dates at a fixed duration or calendar frequency.
        
        Parameters
        ----------
        start, end : date-like scalar, optional
            Range endpoints. Text uses Configs and the shared parser. Bare
            numbers are ticks at unit, or nanoseconds when unit is omitted.
        periods : integer, optional
            Nonnegative requested number of dates. Omit when both endpoints
            and a frequency are given.
        freq : str, timedelta or pandas DateOffset, optional
            Calendar or elapsed-time step. Defaults to one calendar day unless
            start, end and periods are all supplied; that form is evenly spaced.
        tz : tzinfo or str, optional
            Target timezone; naive endpoints are interpreted in that timezone.
        normalize : bool, default False
            Set local endpoint clock fields to midnight before generation.
        inclusive : {'both', 'left', 'right', 'neither'}, default 'both'
            Which explicitly supplied endpoints can occur in the result.
        unit : {'s', 'ms', 'us', 'ns'}, optional
            Storage resolution. Endpoints and frequency must fit without loss.
        name : hashable, optional
            Name of the resulting index.
        default, yearfirst, dayfirst, isoformat, strict, cfg : optional
            The same text parsing settings as Pddt construction.
        ambiguous, nonexistent : policy, default 'raise'
            Regional local-time policies. A boolean collection corresponds to
            the full generated sequence before inclusive endpoints are removed.
        
        Returns
        -------
        Pddt
            The generated date index at the requested resolution.
        
        Examples
        --------
        >>> Pddt.date_range("2024-01-01", periods=3).day.tolist()
        [1, 2, 3]
        """
        ...

    @property
    def pddt(self) -> _PddtNamespace[Self]:
        """Return this index's date-field namespace; native value replace is inherited.

        Returns
        -------
        _PddtNamespace[Self]
            Date-field replace preserves the corresponding owning Pddt class.
        """
        ...

    def to_datetime(self, year: _OptionalField = None, month: _OptionalField = None, day: _OptionalField = None, hour: _OptionalField = None, minute: _OptionalField = None, second: _OptionalField = None, microsecond: _OptionalField = None, nanosecond: _OptionalField = None) -> Self:
        """Select date and clock fields, fitting a legal day intent to month end.
        
        Parameters
        ----------
        year, month, day, hour, minute, second, microsecond, nanosecond : integer or equal-length integer collection, optional
            None preserves that field. Field ranges match replace. Only a legal
            day intent is adjusted to its target month's last day; invalid
            numbers such as month=13 or hour=25 are rejected. Regional dates
            use the automatic calendar rule and must remain in the target day.
        
        Returns
        -------
        Pddt
            Selected dates with original unit, name and missing positions.
        
        Examples
        --------
        >>> Pddt(["2024-01-31"]).to_datetime(month=2).day.tolist()
        [29]
        """
        ...

    def to_date(self, year: _OptionalField = None, month: _OptionalField = None, day: _OptionalField = None) -> Self:
        """Select calendar fields while retaining the clock and subsecond tail.
        
        Parameters
        ----------
        year, month, day : integer or equal-length integer collection, optional
            None retains the original field. Month is 1–12 and day is 1–31;
            a legal day intent is fitted to the destination month's last day.
        
        Returns
        -------
        Pddt
            New dates, or the original object if no value changes.
        
        Examples
        --------
        >>> Pddt(["2024-01-31 12:00"]).to_date(month=2).day.tolist()
        [29]
        """
        ...

    def to_time(self, hour: _OptionalField = None, minute: _OptionalField = None, second: _OptionalField = None, microsecond: _OptionalField = None, nanosecond: _OptionalField = None) -> Self:
        """Select clock fields while retaining each calendar date.
        
        Parameters
        ----------
        hour, minute, second, microsecond, nanosecond : integer or equal-length integer collection, optional
            None retains the field. Ranges are 0–23, 0–59, 0–59, 0–999999
            and 0–999. Replacing microsecond clears an omitted nanosecond tail.
        
        Returns
        -------
        Pddt
            Dates with selected clocks at the existing storage resolution.
        
        Examples
        --------
        >>> Pddt(["2024-01-01"]).to_time(hour=9).hour.tolist()
        [9]
        """
        ...

    def add(self, years: _IntegerArgument = 0, quarters: _IntegerArgument = 0, months: _IntegerArgument = 0, weeks: _IntegerArgument = 0, days: _IntegerArgument = 0, hours: _IntegerArgument = 0, minutes: _IntegerArgument = 0, seconds: _IntegerArgument = 0, milliseconds: _IntegerArgument = 0, microseconds: _IntegerArgument = 0, nanoseconds: _IntegerArgument = 0) -> Self:
        """Add calendar and clock increments in one operation.
        
        Parameters
        ----------
        years, quarters, months, weeks, days, hours, minutes, seconds, milliseconds, microseconds, nanoseconds : integer or equal-length integer collection, default 0
            Calendar months are combined before selecting the destination month;
            the original day is fitted once, then days and clocks are applied.
            Negative increments are supported. Floats, booleans and missing
            increments are rejected. A day is a calendar move, not UTC 24 hours.
        
        Returns
        -------
        Pddt
            Dates with the same unit, name and NaT positions. A finer result
            requires an explicit as_unit conversion before this operation.
        
        Examples
        --------
        >>> Pddt(["2024-01-31"]).add(months=1).day.tolist()
        [29]
        """
        ...

    def sub(self, years: _IntegerArgument = 0, quarters: _IntegerArgument = 0, months: _IntegerArgument = 0, weeks: _IntegerArgument = 0, days: _IntegerArgument = 0, hours: _IntegerArgument = 0, minutes: _IntegerArgument = 0, seconds: _IntegerArgument = 0, milliseconds: _IntegerArgument = 0, microseconds: _IntegerArgument = 0, nanoseconds: _IntegerArgument = 0) -> Self:
        """Subtract calendar and clock increments in one operation.
        
        Parameters
        ----------
        years, quarters, months, weeks, days, hours, minutes, seconds, milliseconds, microseconds, nanoseconds : integer or equal-length integer collection, default 0
            Calendar months are combined before selecting the destination month;
            the original day is fitted once, then days and clocks are applied.
            Negative increments are supported. Floats, booleans and missing
            increments are rejected. A day is a calendar move, not UTC 24 hours.
        
        Returns
        -------
        Pddt
            Dates with the same unit, name and NaT positions. A finer result
            requires an explicit as_unit conversion before this operation.
        
        Examples
        --------
        >>> Pddt(["2024-01-31"]).sub(months=1).day.tolist()
        [31]
        """
        ...

    def to_year(self, offset: _IntegerArgument, month: _StoredSelection = None, day: _OptionalField = None) -> Self:
        """Move by calendar year periods and apply the optional field choice.
        
        Parameters
        ----------
        offset : integer or equal-length integer collection
            Positive moves forward, negative backward; zero selects this period.
        month : integer or equal-length collection or stored month name, optional
            Month 1–12; None preserves the month.
        day : integer or equal-length integer collection, optional
            Day intent 1–31, fitted to the destination month's last day.
        
        Returns
        -------
        Pddt
            Dates with the original clock, unit, name and missing positions.
        """
        ...

    def to_quarter(self, offset: _IntegerArgument, month: _OptionalField = None, day: _OptionalField = None) -> Self:
        """Move by calendar quarter periods and apply the optional field choice.
        
        Parameters
        ----------
        offset : integer or equal-length integer collection
            Positive moves forward, negative backward; zero selects this period.
        month : integer or equal-length collection, optional
            Position 1–3 within a quarter; None preserves the position.
        day : integer or equal-length integer collection, optional
            Day intent 1–31, fitted to the destination month's last day.
        
        Returns
        -------
        Pddt
            Dates with the original clock, unit, name and missing positions.
        """
        ...

    def to_month(self, offset: _IntegerArgument, day: _OptionalField = None) -> Self:
        """Move by calendar month periods and apply the optional field choice.
        
        Parameters
        ----------
        offset : integer or equal-length integer collection
            Positive moves forward, negative backward; zero selects this period.
        day : integer or equal-length integer collection, optional
            Day intent 1–31, fitted to the destination month's last day.
        
        Returns
        -------
        Pddt
            Dates with the original clock, unit, name and missing positions.
        """
        ...

    def to_weekday(self, offset: _IntegerArgument, weekday: _StoredSelection = None) -> Self:
        """Move by calendar weekday periods and apply the optional field choice.
        
        Parameters
        ----------
        offset : integer or equal-length integer collection
            Positive moves forward, negative backward; zero selects this period.
        weekday : integer, stored weekday name or equal-length collection, optional
            Monday is 0 and Sunday is 6. None preserves each original weekday.
        
        Returns
        -------
        Pddt
            Dates with the original clock, unit, name and missing positions.
        """
        ...

    def to_day(self, offset: _IntegerArgument) -> Self:
        """Move by calendar day periods and apply the optional field choice.
        
        Parameters
        ----------
        offset : integer or equal-length integer collection
            Positive moves forward, negative backward; zero selects this period.
        
        Returns
        -------
        Pddt
            Dates with the original clock, unit, name and missing positions.
        """
        ...

    def to_curr_year(self, month: _StoredSelection = None, day: _OptionalField = None) -> Self:
        """Select fields in the curr calendar year.
        
        Parameters
        ----------
        month : integer or equal-length collection or stored name, optional
            Month 1–12, or None to keep the month.
        day : integer or equal-length integer collection, optional
            Legal day intent 1–31, fitted to the destination month end.
        
        Returns
        -------
        Pddt
            Selected dates preserving clock, resolution, name and NaT positions.
        """
        ...

    def to_prev_year(self, month: _StoredSelection = None, day: _OptionalField = None) -> Self:
        """Select fields in the prev calendar year.
        
        Parameters
        ----------
        month : integer or equal-length collection or stored name, optional
            Month 1–12, or None to keep the month.
        day : integer or equal-length integer collection, optional
            Legal day intent 1–31, fitted to the destination month end.
        
        Returns
        -------
        Pddt
            Selected dates preserving clock, resolution, name and NaT positions.
        """
        ...

    def to_next_year(self, month: _StoredSelection = None, day: _OptionalField = None) -> Self:
        """Select fields in the next calendar year.
        
        Parameters
        ----------
        month : integer or equal-length collection or stored name, optional
            Month 1–12, or None to keep the month.
        day : integer or equal-length integer collection, optional
            Legal day intent 1–31, fitted to the destination month end.
        
        Returns
        -------
        Pddt
            Selected dates preserving clock, resolution, name and NaT positions.
        """
        ...

    def to_curr_quarter(self, month: _OptionalField = None, day: _OptionalField = None) -> Self:
        """Select fields in the curr calendar quarter.
        
        Parameters
        ----------
        month : integer or equal-length collection, optional
            Quarter position 1–3, or None to keep the position.
        day : integer or equal-length integer collection, optional
            Legal day intent 1–31, fitted to the destination month end.
        
        Returns
        -------
        Pddt
            Selected dates preserving clock, resolution, name and NaT positions.
        """
        ...

    def to_prev_quarter(self, month: _OptionalField = None, day: _OptionalField = None) -> Self:
        """Select fields in the prev calendar quarter.
        
        Parameters
        ----------
        month : integer or equal-length collection, optional
            Quarter position 1–3, or None to keep the position.
        day : integer or equal-length integer collection, optional
            Legal day intent 1–31, fitted to the destination month end.
        
        Returns
        -------
        Pddt
            Selected dates preserving clock, resolution, name and NaT positions.
        """
        ...

    def to_next_quarter(self, month: _OptionalField = None, day: _OptionalField = None) -> Self:
        """Select fields in the next calendar quarter.
        
        Parameters
        ----------
        month : integer or equal-length collection, optional
            Quarter position 1–3, or None to keep the position.
        day : integer or equal-length integer collection, optional
            Legal day intent 1–31, fitted to the destination month end.
        
        Returns
        -------
        Pddt
            Selected dates preserving clock, resolution, name and NaT positions.
        """
        ...

    def to_curr_month(self, day: _OptionalField = None) -> Self:
        """Select fields in the curr calendar month.
        
        Parameters
        ----------
        day : integer or equal-length integer collection, optional
            Legal day intent 1–31, fitted to the destination month end.
        
        Returns
        -------
        Pddt
            Selected dates preserving clock, resolution, name and NaT positions.
        """
        ...

    def to_prev_month(self, day: _OptionalField = None) -> Self:
        """Select fields in the prev calendar month.
        
        Parameters
        ----------
        day : integer or equal-length integer collection, optional
            Legal day intent 1–31, fitted to the destination month end.
        
        Returns
        -------
        Pddt
            Selected dates preserving clock, resolution, name and NaT positions.
        """
        ...

    def to_next_month(self, day: _OptionalField = None) -> Self:
        """Select fields in the next calendar month.
        
        Parameters
        ----------
        day : integer or equal-length integer collection, optional
            Legal day intent 1–31, fitted to the destination month end.
        
        Returns
        -------
        Pddt
            Selected dates preserving clock, resolution, name and NaT positions.
        """
        ...

    def to_curr_weekday(self, weekday: _StoredSelection = None) -> Self:
        """Select fields in the curr calendar weekday.
        
        Parameters
        ----------
        weekday : integer, stored name or equal-length collection, optional
            Monday is 0; Sunday is 6. None retains the original weekday.
        
        Returns
        -------
        Pddt
            Selected dates preserving clock, resolution, name and NaT positions.
        """
        ...

    def to_prev_weekday(self, weekday: _StoredSelection = None) -> Self:
        """Select fields in the prev calendar weekday.
        
        Parameters
        ----------
        weekday : integer, stored name or equal-length collection, optional
            Monday is 0; Sunday is 6. None retains the original weekday.
        
        Returns
        -------
        Pddt
            Selected dates preserving clock, resolution, name and NaT positions.
        """
        ...

    def to_next_weekday(self, weekday: _StoredSelection = None) -> Self:
        """Select fields in the next calendar weekday.
        
        Parameters
        ----------
        weekday : integer, stored name or equal-length collection, optional
            Monday is 0; Sunday is 6. None retains the original weekday.
        
        Returns
        -------
        Pddt
            Selected dates preserving clock, resolution, name and NaT positions.
        """
        ...

    def to_monday(self) -> Self:
        """Select this week's monday while keeping each clock.
        
        Returns
        -------
        Pddt
            Selected weekday dates with original resolution and missing values.
        """
        ...

    def to_tuesday(self) -> Self:
        """Select this week's tuesday while keeping each clock.
        
        Returns
        -------
        Pddt
            Selected weekday dates with original resolution and missing values.
        """
        ...

    def to_wednesday(self) -> Self:
        """Select this week's wednesday while keeping each clock.
        
        Returns
        -------
        Pddt
            Selected weekday dates with original resolution and missing values.
        """
        ...

    def to_thursday(self) -> Self:
        """Select this week's thursday while keeping each clock.
        
        Returns
        -------
        Pddt
            Selected weekday dates with original resolution and missing values.
        """
        ...

    def to_friday(self) -> Self:
        """Select this week's friday while keeping each clock.
        
        Returns
        -------
        Pddt
            Selected weekday dates with original resolution and missing values.
        """
        ...

    def to_saturday(self) -> Self:
        """Select this week's saturday while keeping each clock.
        
        Returns
        -------
        Pddt
            Selected weekday dates with original resolution and missing values.
        """
        ...

    def to_sunday(self) -> Self:
        """Select this week's sunday while keeping each clock.
        
        Returns
        -------
        Pddt
            Selected weekday dates with original resolution and missing values.
        """
        ...

    def to_yesterday(self) -> Self:
        """Move one calendar day backward, keeping the clock.
        
        Returns
        -------
        Pddt
            New dates with original resolution, name and missing positions.
        """
        ...

    def to_tomorrow(self) -> Self:
        """Move one calendar day forward, keeping the clock.
        
        Returns
        -------
        Pddt
            New dates with original resolution, name and missing positions.
        """
        ...

    @overload  # type: ignore[override]
    def __add__(self, other: _dt.timedelta | np.timedelta64 | Delta) -> Self:
        """Add a fixed elapsed duration or a calendar Delta.
        
        Parameters
        ----------
        other : timedelta, pandas Timedelta, numpy.timedelta64, Delta or equal-length temporal collection
            Fixed durations move actual instants. Delta applies calendar fields;
            Delta collections contain one real Delta per date, without missing
            increments. Existing pandas DateOffset protocols remain delegated.
        
        Returns
        -------
        Pddt or NotImplemented
            Dates at this index's resolution, preserving name and NaT positions.
        """
        ...

    @overload
    def __add__(self, other: object) -> Self | pd.DatetimeIndex | NotImplementedType:
        """Add a fixed elapsed duration or a calendar Delta.
        
        Parameters
        ----------
        other : timedelta, pandas Timedelta, numpy.timedelta64, Delta or equal-length temporal collection
            Fixed durations move actual instants. Delta applies calendar fields;
            Delta collections contain one real Delta per date, without missing
            increments. Existing pandas DateOffset protocols remain delegated.
        
        Returns
        -------
        Pddt or NotImplemented
            Dates at this index's resolution, preserving name and NaT positions.
        """
        ...

    @overload  # type: ignore[override]
    def __radd__(self, other: _dt.timedelta | np.timedelta64 | Delta) -> Self:
        """Add a duration or Delta on the left with the same date semantics.
        
        Parameters
        ----------
        other : timedelta, pandas Timedelta, numpy.timedelta64, Delta or equal-length temporal collection
            The elapsed duration or calendar increment to apply.
        
        Returns
        -------
        Pddt or NotImplemented
            Adjusted dates at the original storage resolution.
        """
        ...

    @overload
    def __radd__(self, other: object) -> Self | pd.DatetimeIndex | NotImplementedType:
        """Add a duration or Delta on the left with the same date semantics.
        
        Parameters
        ----------
        other : timedelta, pandas Timedelta, numpy.timedelta64, Delta or equal-length temporal collection
            The elapsed duration or calendar increment to apply.
        
        Returns
        -------
        Pddt or NotImplemented
            Adjusted dates at the original storage resolution.
        """
        ...

    @overload  # type: ignore[override]
    def __sub__(self, other: _dt.timedelta | np.timedelta64 | Delta) -> Self:
        """Subtract a duration, calendar Delta or matching date values.
        
        Parameters
        ----------
        other : timedelta, pandas Timedelta, numpy.timedelta64, Delta, date-like scalar or equal-length temporal collection
            Durations move actual instants; Delta reverses calendar increments.
            Date values produce elapsed differences. Aware and naive valid
            dates cannot be mixed. Date strings are not guessed here.
        
        Returns
        -------
        Pddt or pandas.TimedeltaIndex or NotImplemented
            Adjusted dates retain this index's unit. Date differences use the
            finer source date resolution without discarding a nonzero tail.
        """
        ...

    @overload
    def __sub__(self, other: _dt.date | np.datetime64 | pd.DatetimeIndex) -> pd.TimedeltaIndex:
        """Subtract a duration, calendar Delta or matching date values.
        
        Parameters
        ----------
        other : timedelta, pandas Timedelta, numpy.timedelta64, Delta, date-like scalar or equal-length temporal collection
            Durations move actual instants; Delta reverses calendar increments.
            Date values produce elapsed differences. Aware and naive valid
            dates cannot be mixed. Date strings are not guessed here.
        
        Returns
        -------
        Pddt or pandas.TimedeltaIndex or NotImplemented
            Adjusted dates retain this index's unit. Date differences use the
            finer source date resolution without discarding a nonzero tail.
        """
        ...

    @overload
    def __sub__(self, other: object) -> Self | pd.DatetimeIndex | pd.TimedeltaIndex | NotImplementedType:
        """Subtract a duration, calendar Delta or matching date values.
        
        Parameters
        ----------
        other : timedelta, pandas Timedelta, numpy.timedelta64, Delta, date-like scalar or equal-length temporal collection
            Durations move actual instants; Delta reverses calendar increments.
            Date values produce elapsed differences. Aware and naive valid
            dates cannot be mixed. Date strings are not guessed here.
        
        Returns
        -------
        Pddt or pandas.TimedeltaIndex or NotImplemented
            Adjusted dates retain this index's unit. Date differences use the
            finer source date resolution without discarding a nonzero tail.
        """
        ...

    def to_first_of(self, unit: str) -> Self:
        """Select a period's first day.
        
        Parameters
        ----------
        unit : str
            Y, Q, M, W or a saved month name. The clock is retained.
            Unknown or empty names raise ValueError. Regional boundaries stay
            inside the selected period; a wholly missing period is invalid.
        
        Returns
        -------
        Pddt
            Selected dates at the original resolution, timezone and name.
        """
        ...

    def is_first_of(self, unit: str) -> pd.Index:
        """Test for a period's first day.
        
        Parameters
        ----------
        unit : str
            Y, Q, M, W or a saved month name. The clock is retained.
            Unknown or empty names raise ValueError. Regional boundaries stay
            inside the selected period; a wholly missing period is invalid.
        
        Returns
        -------
        pandas.Index
            Boolean results; original NaT positions are False.
        """
        ...

    def to_last_of(self, unit: str) -> Self:
        """Select a period's last day.
        
        Parameters
        ----------
        unit : str
            Y, Q, M, W or a saved month name. The clock is retained.
            Unknown or empty names raise ValueError. Regional boundaries stay
            inside the selected period; a wholly missing period is invalid.
        
        Returns
        -------
        Pddt
            Selected dates at the original resolution, timezone and name.
        """
        ...

    def is_last_of(self, unit: str) -> pd.Index:
        """Test for a period's last day.
        
        Parameters
        ----------
        unit : str
            Y, Q, M, W or a saved month name. The clock is retained.
            Unknown or empty names raise ValueError. Regional boundaries stay
            inside the selected period; a wholly missing period is invalid.
        
        Returns
        -------
        pandas.Index
            Boolean results; original NaT positions are False.
        """
        ...

    def to_start_of(self, unit: str) -> Self:
        """Select a period's start representable instant.
        
        Parameters
        ----------
        unit : str
            Y, Q, M, W, D, h, m/min, s, ms, us, ns or a saved month/weekday name.
            Unknown or empty names raise ValueError. Regional boundaries stay
            inside the selected period; a wholly missing period is invalid.
        
        Returns
        -------
        Pddt
            Selected dates at the original resolution, timezone and name.
        """
        ...

    def is_start_of(self, unit: str) -> pd.Index:
        """Test for a period's start representable instant.
        
        Parameters
        ----------
        unit : str
            Y, Q, M, W, D, h, m/min, s, ms, us, ns or a saved month/weekday name.
            Unknown or empty names raise ValueError. Regional boundaries stay
            inside the selected period; a wholly missing period is invalid.
        
        Returns
        -------
        pandas.Index
            Boolean results; original NaT positions are False.
        """
        ...

    def to_end_of(self, unit: str) -> Self:
        """Select a period's end representable instant.
        
        Parameters
        ----------
        unit : str
            Y, Q, M, W, D, h, m/min, s, ms, us, ns or a saved month/weekday name.
            Unknown or empty names raise ValueError. Regional boundaries stay
            inside the selected period; a wholly missing period is invalid.
        
        Returns
        -------
        Pddt
            Selected dates at the original resolution, timezone and name.
        """
        ...

    def is_end_of(self, unit: str) -> pd.Index:
        """Test for a period's end representable instant.
        
        Parameters
        ----------
        unit : str
            Y, Q, M, W, D, h, m/min, s, ms, us, ns or a saved month/weekday name.
            Unknown or empty names raise ValueError. Regional boundaries stay
            inside the selected period; a wholly missing period is invalid.
        
        Returns
        -------
        pandas.Index
            Boolean results; original NaT positions are False.
        """
        ...

    def normalize(self) -> Self:
        """Select the first valid representable local instant of each day.
        
        Returns
        -------
        Pddt
            Normalized dates in the same day, unit and timezone; NaT remains NaT.
        
        Examples
        --------
        >>> Pddt(["2024-01-02 12:30"]).normalize().hour.tolist()
        [0]
        """
        ...

    def fsp(self, precision: SupportsIndex) -> Self:
        """Truncate fractional second digits without rounding or changing unit.
        
        Parameters
        ----------
        precision : integer
            Nonnegative number of decimal places, up to nine. Larger values
            retain existing precision. Booleans, floats and collections fail.
        
        Returns
        -------
        Pddt
            Dates with trimmed fractional digits, or the unchanged original.
        
        Examples
        --------
        >>> Pddt(["2024-01-01 00:00:00.123456789"]).fsp(3)[0].microsecond
        123000
        """
        ...

    # P13 uses automatic DST rules without pandas per-call policy arguments.
    def round(self, freq: str | _dt.timedelta | pd.DateOffset = 's') -> Self:  # type: ignore[override]
        """Round to the nearest grid, with ties to even.
        
        Parameters
        ----------
        freq : str, timedelta or fixed pandas DateOffset, default 's'
            Positive fixed frequency, such as '15min', 'h', 'D' or '500ns'.
            Calendar offsets are not rounding grids. Regional times use the
            automatic valid-boundary rule while retaining the rounding meaning.
        
        Returns
        -------
        Pddt
            Rounded dates at the existing unit, timezone and name, with NaT
            positions retained. The old unit and DST policy keywords are absent.
        """
        ...

    # P13 uses automatic DST rules without pandas per-call policy arguments.
    def ceil(self, freq: str | _dt.timedelta | pd.DateOffset = 's') -> Self:  # type: ignore[override]
        """Round upward without moving earlier.
        
        Parameters
        ----------
        freq : str, timedelta or fixed pandas DateOffset, default 's'
            Positive fixed frequency, such as '15min', 'h', 'D' or '500ns'.
            Calendar offsets are not rounding grids. Regional times use the
            automatic valid-boundary rule while retaining the rounding meaning.
        
        Returns
        -------
        Pddt
            Rounded dates at the existing unit, timezone and name, with NaT
            positions retained. The old unit and DST policy keywords are absent.
        """
        ...

    # P13 uses automatic DST rules without pandas per-call policy arguments.
    def floor(self, freq: str | _dt.timedelta | pd.DateOffset = 's') -> Self:  # type: ignore[override]
        """Round downward without moving later.
        
        Parameters
        ----------
        freq : str, timedelta or fixed pandas DateOffset, default 's'
            Positive fixed frequency, such as '15min', 'h', 'D' or '500ns'.
            Calendar offsets are not rounding grids. Regional times use the
            automatic valid-boundary rule while retaining the rounding meaning.
        
        Returns
        -------
        Pddt
            Rounded dates at the existing unit, timezone and name, with NaT
            positions retained. The old unit and DST policy keywords are absent.
        """
        ...

    # P13 has the shared single-period/name interface, not arbitrary offsets.
    def snap(self, unit: str = 's') -> Self:  # type: ignore[override]
        """Select the nearest valid period start; an equal distance goes later.
        
        Parameters
        ----------
        unit : str, default 's'
            One Y, Q, M, W, D, h, m/min, s, ms, us or ns period, or a stored
            month/weekday name. Weeks start Monday. A weekday repeats weekly;
            a month name repeats annually. Arbitrary multiple frequencies and
            DateOffset objects are not accepted. Names use the unchanged
            default words and are independent of an edited Configs instance.
        
        Returns
        -------
        Pddt
            Nearest starts measured in actual elapsed time for aware dates,
            or wall-clock distance for naive dates. Missing periods are skipped;
            a partly missing period uses its first valid representable start.
            Original unit, name, timezone and NaT positions are preserved.
        
        Examples
        --------
        >>> Pddt(["2024-01-02 12:00"]).snap("D").day.tolist()
        [3]
        """
        ...

    def isoyear(self) -> pd.Index:
        """Return the signed ISO week year.
        
        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        ...

    def isoweek(self) -> pd.Index:
        """Return the ISO week number, starting at one.
        
        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        ...

    def isoweekday(self) -> pd.Index:
        """Return the ISO weekday, Monday one through Sunday seven.
        
        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        ...

    def days_in_year(self) -> pd.Index:
        """Return the number of days in the calendar year.
        
        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        ...

    def days_bf_year(self) -> pd.Index:
        """Count days before this year, relative to 0001-01-01.
        
        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        ...

    def days_in_quarter(self) -> pd.Index:
        """Return the number of days in the calendar quarter.
        
        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        ...

    def days_bf_quarter(self) -> pd.Index:
        """Count calendar-year days preceding this quarter.
        
        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        ...

    def day_of_quarter(self) -> pd.Index:
        """Return the one-based day position within the quarter.
        
        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        ...

    def days_bf_month(self) -> pd.Index:
        """Count calendar-year days preceding this month.
        
        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        ...

    def day_of_month(self) -> pd.Index:
        """Return the one-based day position within the month.
        
        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        ...

    @property
    def millisecond(self) -> pd.Index:
        """Return the 0–999 millisecond part within each second.
        
        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        ...

    def is_long_year(self) -> pd.Index:
        """Test whether the calendar year has 53 ISO weeks.
        
        Returns
        -------
        pandas.Index
            Boolean values, with False at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        ...

    def is_year(self, year: _IntegerArgument) -> pd.Index:
        """Compare each local calendar value with a scalar or row target.
        
        Parameters
        ----------
        year : integer or equal-length collection
            A scalar applies to all rows; collections match by position, without
            pandas label alignment. Booleans, floats and missing targets fail.
            Every target must implement the integer protocol.
            A legal integer that does not match returns False.
        
        Returns
        -------
        pandas.Index
            Boolean matches, with False for original NaT dates.
        """
        ...

    def is_quarter(self, quarter: _IntegerArgument) -> pd.Index:
        """Compare each local calendar value with a scalar or row target.
        
        Parameters
        ----------
        quarter : integer or equal-length collection
            A scalar applies to all rows; collections match by position, without
            pandas label alignment. Booleans, floats and missing targets fail.
            Every target must implement the integer protocol.
            A legal integer that does not match returns False.
        
        Returns
        -------
        pandas.Index
            Boolean matches, with False for original NaT dates.
        """
        ...

    def is_month(self, month: SupportsIndex | str | Iterable[SupportsIndex | str] | _Column) -> pd.Index:
        """Compare each local calendar value with a scalar or row target.
        
        Parameters
        ----------
        month : integer or stored name or equal-length collection
            A scalar applies to all rows; collections match by position, without
            pandas label alignment. Booleans, floats and missing targets fail.
            Unknown or empty names raise ValueError.
            A legal integer that does not match returns False.
        
        Returns
        -------
        pandas.Index
            Boolean matches, with False for original NaT dates.
        """
        ...

    def is_weekday(self, weekday: SupportsIndex | str | Iterable[SupportsIndex | str] | _Column) -> pd.Index:
        """Compare each local calendar value with a scalar or row target.
        
        Parameters
        ----------
        weekday : integer or stored name or equal-length collection
            A scalar applies to all rows; collections match by position, without
            pandas label alignment. Booleans, floats and missing targets fail.
            Unknown or empty names raise ValueError.
            A legal integer that does not match returns False.
        
        Returns
        -------
        pandas.Index
            Boolean matches, with False for original NaT dates.
        """
        ...

    def is_day(self, day: _IntegerArgument) -> pd.Index:
        """Compare each local calendar value with a scalar or row target.
        
        Parameters
        ----------
        day : integer or equal-length collection
            A scalar applies to all rows; collections match by position, without
            pandas label alignment. Booleans, floats and missing targets fail.
            Every target must implement the integer protocol.
            A legal integer that does not match returns False.
        
        Returns
        -------
        pandas.Index
            Boolean matches, with False for original NaT dates.
        """
        ...

    def leap_bt_year(self, year: _IntegerArgument) -> pd.Index:
        """Count leap years between two years, including the smaller only.
        
        Parameters
        ----------
        year : integer or equal-length collection
            A scalar applies to all rows; collections match by position, without
            pandas label alignment. Booleans, floats and missing targets fail.
            Every target must implement the integer protocol.
            Both directions return the same nonnegative count.
        
        Returns
        -------
        pandas.Index
            Nullable Int64 leap counts, with pd.NA for original NaT dates.
        """
        ...

    @property

    def year(self) -> pd.Index:
        """Calendar years, preserving signed wide years and pandas missing values.
        
        Returns
        -------
        pandas.Index
            Standard int32 years when representable, int64 for wider years,
            or float64 with NaN at missing positions. The source name is retained.
        """
        ...

    def isocalendar(self) -> pd.DataFrame:
        """Return standard ISO year, week and weekday columns.
        
        Returns
        -------
        pandas.DataFrame
            Three nullable UInt32 columns, indexed by this date index. Missing
            dates give three missing cells. Negative ISO years, and ISO years
            beyond UInt32, raise OverflowError; isoyear() supports signed years.
        
        Examples
        --------
        >>> Pddt(["2021-01-01"]).isocalendar()["week"].tolist()
        [53]
        """
        ...

    def is_dst(self) -> pd.Index:
        """Test whether each local date has a nonzero daylight-saving offset.
        
        Returns
        -------
        pandas.Index
            A bool index of the same length. Naive and missing dates return False; negative DST also counts as DST.
        """
        ...

    def utcoffset_seconds(self) -> pd.Index:
        """Return each actual UTC offset, rounded down to whole seconds.
        
        Returns
        -------
        pandas.Index
            A Int64 index of the same length. Naive and missing dates return pd.NA. Fractional negative offsets round toward the earlier second.
        """
        ...

    def is_past(self) -> pd.Index:
        """Test whether dates precede one current clock reading.
        
        Returns
        -------
        pandas.Index
            A bool index of the same length. Aware dates compare actual instants; naive dates compare local wall clocks. Equal and missing dates return False.
        """
        ...

    def is_future(self) -> pd.Index:
        """Test whether dates follow one current clock reading.
        
        Returns
        -------
        pandas.Index
            A bool index of the same length. Aware dates compare actual instants; naive dates compare local wall clocks. Equal and missing dates return False.
        """
        ...

    def diff(self, dtobj: _DateValue | _DateCollection, unit: str, absolute: _Boolean = False, inclusive: Literal["one", "both", "neither"] = "one") -> pd.Index:
        """Count unit boundaries between dates and scalar or positional targets.
        
        Parameters
        ----------
        dtobj : date-like scalar or equal-length one-dimensional collection
            Text, dates, datetimes, native dates or numeric epoch seconds.
            Numeric inputs always mean seconds, including a numeric collection.
            Aware and naive values cannot be mixed. Missing dates propagate.
        unit : {'Y', 'Q', 'M', 'W', 'D', 'h', 'm', 'min', 's', 'ms', 'us', 'ns'}
            Count crossed boundaries, rather than dividing elapsed duration.
            Weeks start on Monday. Aware dates use UTC boundaries.
        absolute : bool or numpy.bool_, default False
            Take the absolute boundary difference before inclusive adjustment.
        inclusive : {'one', 'both', 'neither'}, default 'one'
            Keep the difference, increase its magnitude by one, or decrease it
            by one. A zero difference with 'neither' is -1.
        
        Returns
        -------
        pandas.Index
            An int64 index named 'diff'; nullable Int64 when any date is missing.
            The entire signed int64 range is valid, including -2**63.
            Results outside that range raise OverflowError.
        
        Examples
        --------
        >>> Pddt([np.datetime64(2, "s")]).diff(1, "s").tolist()
        [1]
        >>> Pddt([np.datetime64(1, "ns")]).diff(1e-9, "ns").tolist()
        [0]
        """
        ...

    @property

    def values_naive(self) -> np.ndarray:
        """Return a datetime64 array containing local wall-clock values.
        
        Returns
        -------
        numpy.ndarray
            The current unit and missing positions are retained. Removing a
            timezone preserves the local clock, rather than exposing UTC ticks.
            An unrepresentable local clock requires an explicit as_unit().
        """
        ...

    def toseconds(self, utc: _Boolean = False) -> pd.Index:
        """Return floating seconds from the epoch in wall-clock or UTC coordinates.
        
        Parameters
        ----------
        utc : bool or numpy.bool_, default False
            False measures the local wall clock from naive 1970-01-01.
            True uses actual UTC instants for aware dates; naive dates stay naive.
        
        Returns
        -------
        pandas.Index
            Correctly rounded float64 seconds; missing dates give NaN.
        
        Examples
        --------
        >>> x=Pddt(["1970-01-01 08:00"],tz="Asia/Shanghai")
        >>> x.toseconds().tolist(), x.toseconds(utc=True).tolist()
        ([28800.0], [0.0])
        """
        ...

    def tomicroseconds(self, utc: _Boolean = False) -> pd.Index:
        """Return integer epoch microseconds from local or UTC coordinates.
        
        Parameters
        ----------
        utc : bool or numpy.bool_, default False
            False uses local wall clocks; True uses UTC for aware dates.
            A naive date never gains an assumed local timezone here.
        
        Returns
        -------
        pandas.Index
            Nullable Int64 microseconds. Nanoseconds are floored only at this
            explicit export, and missing dates remain pd.NA.
        
        Examples
        --------
        >>> x=Pddt(["1970-01-01 08:00"],tz="Asia/Shanghai")
        >>> x.tomicroseconds().tolist(), x.tomicroseconds(utc=True).tolist()
        ([28800000000], [0])
        """
        ...

    def toordinal(self) -> pd.Index:
        """Return local Gregorian day numbers, with 0001-01-01 as day one.
        
        Returns
        -------
        pandas.Index
            Nullable Int64 ordinals, retaining missing dates and wide years.
        """
        ...

    def timestamp(self) -> pd.Index:
        """Return actual UTC epoch seconds, interpreting naive dates locally.
        
        Returns
        -------
        pandas.Index
            Float64 seconds with NaN for missing dates. Naive repeated or
            nonexistent local times require tz_localize() with explicit policies
            before this conversion. Already-aware dates keep their instants.
        """
        ...

    def timedf(self) -> pd.DataFrame:
        """Return nine local calendar/clock fields in struct_time order.
        
        Returns
        -------
        pandas.DataFrame
            A positional table with nullable Int64 year, Int16 day-of-year and
            seven Int8 columns. tm_isdst is -1 when DST is unspecified, otherwise
            zero or one. A missing date fills all nine cells with pd.NA.
        """
        ...

    def utctimedf(self) -> pd.DataFrame:
        """Return nine UTC calendar/clock fields, with tm_isdst equal to zero.
        
        Returns
        -------
        pandas.DataFrame
            The same nullable columns and positional index as timedf(). Aware
            dates use UTC; naive dates retain their clock without guessing local
            timezone. Missing dates fill all nine cells with pd.NA.
        """
        ...

    def isoformat(self, sep: str = "T", timespec: str = "auto") -> pd.Index:
        """Return ISO date strings with chosen display precision.
        
        Parameters
        ----------
        sep : str, default 'T'
            Exactly one Unicode character between the date and clock.
        timespec : str, default 'auto'
            auto, hours, minutes, seconds, milliseconds, microseconds or
            nanoseconds; exact aliases h, m/min, s, ms, us and ns also work.
            Coarser display precision truncates text without changing the dates.
        
        Returns
        -------
        pandas.Index
            Date strings retaining nanoseconds and complete colon-separated
            timezone offsets. Missing dates give missing strings.
        
        Examples
        --------
        >>> Pddt(["2024-01-01 12:30:45.123456789"]).isoformat(timespec="ns").tolist()
        ['2024-01-01T12:30:45.123456789']
        """
        ...

    def strftime(self, format: str) -> pd.Index:
        """Format with complete system rules and exact fractional directives.
        
        Parameters
        ----------
        format : str
            An empty string is valid. %f emits nine digits for ns and six for
            s/ms/us; %.1f through %.9f emit a dot and a truncated/padded fraction,
            and %.0f emits nothing. Other system rules remain delegated.
        
        Returns
        -------
        pandas.Index
            Formatted strings with source name/missing positions. Supported
            system directives and wide-year limits depend on the platform.

        Examples
        --------
        >>> Pddt([123456789], unit="ns").strftime("%f|%.3f|%.0f").tolist()
        ['123456789|.123|']
        """
        ...

    def datetime(self) -> np.ndarray:
        """Return an object array of Pydt dates.
        
        Returns
        -------
        numpy.ndarray
            Each valid date becomes a Pydt with actual timezone and fold; missing dates are pd.NaT. Nanoseconds are floored to microseconds only at this output. Dates outside years 1 through 9999 raise the target error.
        """
        ...

    @property

    def date(self) -> np.ndarray:
        """Return an object array of Python dates.
        
        Returns
        -------
        numpy.ndarray
            Local calendar dates are exported; missing dates are pd.NaT. Python date capacity is checked at this output.
        """
        ...

    @property

    def time(self) -> np.ndarray:
        """Return local Python times without attached timezone.
        
        Returns
        -------
        numpy.ndarray
            Clock fields and fold are retained, with microsecond precision. Missing dates are pd.NaT.
        """
        ...

    @property

    def timetz(self) -> np.ndarray:
        """Return local Python times retaining timezone and fold.
        
        Returns
        -------
        numpy.ndarray
            The actual clock, timezone and fold are retained at microsecond precision. Missing dates are pd.NaT.
        """
        ...

    def tzname(self) -> pd.Index:
        """Return actual timezone names for each represented date.
        
        Returns
        -------
        pandas.Index
            Winter and summer names may differ. Naive or missing dates return None.
        """
        ...

    def ctime(self) -> pd.Index:
        """Return standard English ctime strings.
        
        Returns
        -------
        pandas.Index
            Day numbers are space-padded, for example Tue Oct  1 08:19:05 2024. Fractions and timezone text are omitted; dates are unchanged.
        """
        ...

    def month_name(self, locale: str | None = None) -> pd.Index:
        """Return localized full month names from the shared CLDR rules.
        
        Parameters
        ----------
        locale : str or None, default None
            A supported CLDR locale such as en_US or zh_CN. None uses English.
        
        Returns
        -------
        pandas.Index
            Local calendar names, retaining missing dates and the index name.
            Parsing Configs do not change these language names.
        """
        ...

    def weekday_name(self, locale: str | None = None) -> pd.Index:
        """Return localized full weekday names from the shared CLDR rules.
        
        Parameters
        ----------
        locale : str or None, default None
            A supported CLDR locale such as en_US or zh_CN. None uses English.
        
        Returns
        -------
        pandas.Index
            Local calendar names, retaining missing dates and the index name.
            Parsing Configs do not change these language names.
        """
        ...

    def copy(self, name: Hashable | None = None, deep: _Boolean = False) -> Self:
        """Copy dates and business state without rerunning business initialization.
        
        Parameters
        ----------
        name : hashable or None, default None
            A replacement index name. None retains the current name.
        deep : bool or numpy.bool_, default False
            False shares safe date storage and business references. True copies
            date storage and business values together with one shared memo.
        
        Returns
        -------
        Pddt
            A new shell of the same class under the default protocol. Custom
            reduction hooks keep their normal Python choices and exceptions.
        """
        ...

    def __copy__(self) -> Self:
        """Make a shallow copy using the actual Python state/reduction hooks.
        
        Returns
        -------
        Pddt
            A fresh shell with shared business references under the default
            protocol; business constructors are not rerun.
        """
        ...

    def __deepcopy__(self, memo: dict[int, object]) -> Self:
        """Deep-copy dates and business state with Python's existing memo.
        
        Parameters
        ----------
        memo : dict
            The memo supplied by copy.deepcopy, preserving aliases and cycles.
        
        Returns
        -------
        Pddt
            An independent date buffer and deeply copied business state under
            the default protocol, without business initialization.
        """
        ...

    def __getstate__(self) -> object:
        """Return an independent snapshot of business dictionary and slots.
        
        Returns
        -------
        object
            Ordinary business state only; the date core is saved separately.
            User-defined state hooks retain their normal Python meaning.
        """
        ...

    def __setstate__(self, state: object) -> None:
        """Restore ordinary business state without replacing date internals.
        
        Parameters
        ----------
        state : object
            Business dictionary, dictionary/slots pair, or None from the state
            protocol. Internal date/cache fields cannot be overwritten here.
        
        Returns
        -------
        None
            State is applied to the already-restored object. Custom setters and
            state hooks preserve their original exceptions.
        """
        ...

    def __reduce__(self) -> tuple:
        """Return the new versioned Pddt pickle recipe and business state.
        
        Returns
        -------
        tuple
            A trusted-data reconstruction recipe. Legacy Pddt pickle formats
            are not imported or automatically migrated.
        """
        ...

    def __reduce_ex__(self, protocol: SupportsIndex) -> str | tuple:
        """Return the pickle recipe, respecting a live custom reduce hook.
        
        Parameters
        ----------
        protocol : int
            The protocol requested by Python's copy or pickle machinery.
        
        Returns
        -------
        str or tuple
            A valid pickle recipe, including the result of a real user hook.
        """
        ...


_PddtT = TypeVar("_PddtT", bound=Pddt)

class _PddtNamespace(Generic[_PddtT]):
    """Date-field namespace owned by a Pddt; no global pandas registration.

    Parameters
    ----------
    index : _PddtT
        Owning Pddt object whose date fields are replaced atomically.
    """
    def __init__(self, index: _PddtT) -> None:
        """Retain the owning Pddt without constructing another date index.

        Parameters
        ----------
        index : _PddtT
            Immutable source date index.

        Returns
        -------
        None
            The namespace is ready for field operations.
        """
        ...

    def replace(self, year: _OptionalField = None, month: _OptionalField = None, day: _OptionalField = None, hour: _OptionalField = None, minute: _OptionalField = None, second: _OptionalField = None, microsecond: _OptionalField = None, nanosecond: _OptionalField = None, tzinfo: _dt.tzinfo | str | None = ..., *, ambiguous: _Ambiguous = 'raise', nonexistent: _Nonexistent = 'raise') -> _PddtT:
        """Replace selected fields exactly; every resulting date must be valid.
        
        Parameters
        ----------
        year, month, day, hour, minute, second, microsecond, nanosecond : integer or equal-length integer collection, optional
            None retains each original field. Months are 1–12, days 1–31,
            hours 0–23, minutes/seconds 0–59, microseconds 0–999999 and
            nanosecond tails 0–999. Years may include zero and negative years.
            Each combination must be a real date. Replacing microsecond clears
            the old nanosecond tail unless nanosecond is also supplied.
        tzinfo : tzinfo or str, optional
            Omit to retain the zone; None removes it while keeping local fields.
            A new zone reinterprets the local fields in that zone.
        ambiguous, nonexistent : policy, default 'raise'
            Policies for repeated or missing regional local times.
        
        Returns
        -------
        Pddt
            Updated dates with the same storage unit and name. Unchanged values
            retain the original object. The source is never modified.
        
        Examples
        --------
        >>> Pddt(["2024-01-02"]).pddt.replace(day=3).day.tolist()
        [3]
        """
        ...

