"""Type information for the public Rust parser API."""
import datetime
import numpy as np
from typing import Any, Callable, TypeVar, overload, final, SupportsIndex
from dateutil.parser import parserinfo
_DT = TypeVar('_DT', bound=datetime.datetime)
_MapValue = TypeVar('_MapValue', bound=SupportsIndex)
_Default = str | datetime.date | datetime.datetime | int | float | np.datetime64
# A type-only optional import does not make Polars a runtime dependency.
from polars import Series as _PolarsSeries  # type: ignore[import-not-found]
_EpochInput = _Default | _PolarsSeries

@final
class Configs:
    """Editable token rules and date-order preferences for the parsing functions.

Parameters
----------
yearfirst : bool or numpy.bool_, default True
    Prefer a year in the first position of an ambiguous numeric date. None uses
    Configs when this parser option is optional.
dayfirst : bool or numpy.bool_, default False
    Prefer a day before a month in an ambiguous numeric date. None uses Configs
    when this parser option is optional.

Returns
-------
Configs
    A completed instance of this class.

Notes
-----
Ordering flags accept only Python bool or NumPy boolean scalars; other types raise TypeError.

yearfirst and dayfirst are read-only after construction. Choose them when
creating Configs, or override them for one parse call with its arguments.

Configs cannot be subclassed. Copies and restored snapshots are independently editable. Returned dictionaries and sets are independent snapshots, so edit the configuration with add_*, del_* and set_*.

Words use the stored lowercase, uppercase and titlecase forms; arbitrary mixed case is not inferred. Word namespaces reject conflicting tokens except that jump words may overlap. Region names are exact, case-sensitive ZoneInfo keys validated when registered. Restoring a missing region keeps its key and warns; using an unavailable region raises an error.

Examples
--------
>>> cfg = Configs()
>>> cfg.add_month("harvest", 10)
True
>>> parse_str("7 harvest 2024", cfg=cfg).isoformat()
'2024-10-07T00:00:00'"""

    def __init__(self, yearfirst: bool | np.bool_=True, dayfirst: bool | np.bool_=False) -> None:
        """Initialize multilingual parsing rules and numeric date-order preferences.

Parameters
----------
yearfirst : bool or numpy.bool_, default True
    Prefer a year in the first position of an ambiguous numeric date. None uses
    Configs when this parser option is optional.
dayfirst : bool or numpy.bool_, default False
    Prefer a day before a month in an ambiguous numeric date. None uses Configs
    when this parser option is optional.

Returns
-------
None
    No return value; the configuration is initialized.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    An input is invalid or cannot retain the requested date/time meaning.
OverflowError
    An integer conversion or result exceeds the supported range."""
        ...

    def __copy__(self) -> Configs:
        """Return an independently editable copy of these rules.

Returns
-------
Configs
    An independently editable copy of these rules."""
        ...

    def __deepcopy__(self, memo: dict[int, Any]) -> Configs:
        """Return an independent copy using the deepcopy memo.

Parameters
----------
memo : dict[int, Any]
    The deepcopy memo mapping used to preserve shared references and handle
    cycles.

Returns
-------
Configs
    An independent copy using the deepcopy memo."""
        ...

    def __reduce__(self) -> tuple[Any, ...]:
        """Return the versioned configuration snapshot used by pickle.

Returns
-------
tuple[Any, ...]
    Reconstruction data consumed by pickle; use pickle rather than editing this
    state."""
        ...

    def __reduce_ex__(self, protocol: SupportsIndex) -> tuple[Any, ...]:
        """Return the versioned configuration snapshot for the requested pickle protocol.

Parameters
----------
protocol : int
    Pickle protocol requested by the caller. Reconstruction uses this package's
    validated state format.

Returns
-------
tuple[Any, ...]
    Reconstruction data consumed by pickle; use pickle rather than editing this
    state."""
        ...

    def __setstate__(self, state: tuple[Any, ...]) -> None:
        """Restore a validated configuration snapshot and rebuild its lookup rules.
        
        Parameters
        ----------
        state : tuple[Any, ...]
            A supported versioned state produced by this package. Invalid field values
            or malformed state are rejected; restoring metadata does not mutate an
            existing date/delta value.
        
        Returns
        -------
        None
            No return value; validated rules replace this configuration.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ValueError
            An input is invalid or cannot retain the requested date/time meaning.
        ConfigError
            The snapshot has the right shape but contains invalid token rules.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    @classmethod
    def from_parserinfo(cls, info: parserinfo) -> Configs:
        """Copy vocabulary and calendar-order flags from dateutil parserinfo.
        
        Parameters
        ----------
        info : dateutil.parser.parserinfo
            An instance or real subclass supplying the vocabulary and ordering flags.
            Custom parsing methods and internal parserinfo caches are not copied.
        
        Returns
        -------
        Configs
            An independent configuration using the imported rules.
        
        Raises
        ------
        ImportError
            python-dateutil is not installed. Install rsTimes[dateutil] and
            restart Python before importing a parserinfo instance.
        TypeError
            The source is not a parserinfo instance or a non-None vocabulary table
            has an unsupported outer container. The message identifies the table.
        ConfigError
            A token, mapped value or cross-table combination is invalid.
        OverflowError
            A numeric configuration value exceeds the supported integer range.
        
        Notes
        -----
        JUMP, PERTAIN and UTCZONE accept list, tuple or set; TZOFFSET accepts dict.
        MONTHS, WEEKDAYS, HMS and AMPM accept list or tuple. Real subclasses of these
        containers are accepted. None leaves that table empty; it does not restore
        its default vocabulary. Other outer types, including generators and empty
        containers of the wrong type, raise TypeError before iteration.
        
        Ordering flags accept only Python bool or NumPy boolean scalars. Numeric
        values, None and arbitrary truth-conversion objects raise TypeError.

        Each source table is read once in its established order. A string row is one
        complete alias. Existing alias collections, value ranges, case variants and
        conflict checks apply. The imported configuration does not depend on later
        changes to the source. TZOFFSET values are UTC offsets in seconds.
        
        Examples
        --------
        >>> from dateutil.parser import parserinfo
        >>> from rstimes import Configs
        >>> cfg = Configs.from_parserinfo(parserinfo(dayfirst=True))
        >>> cfg.dayfirst
        True"""
        ...

    @property
    def yearfirst(self) -> bool:
        """Whether ambiguous numeric dates prefer a leading year.

        Returns
        -------
        bool
            The read-only year-order preference chosen for this configuration.

        Notes
        -----
        Set this preference when creating Configs, or pass yearfirst to a parse
        call to override it for that call. Direct assignment is not supported.
        """
        ...

    @property
    def dayfirst(self) -> bool:
        """Whether ambiguous numeric dates prefer a day before the month.

        Returns
        -------
        bool
            The read-only day-order preference chosen for this configuration.

        Notes
        -----
        Set this preference when creating Configs, or pass dayfirst to a parse
        call to override it for that call. Direct assignment is not supported.
        """
        ...

    def order_hint(self) -> str:
        """Describe the current numeric date order.

Returns
-------
str
    One of Y/D/M, Y/M/D, D/M/Y or M/D/Y, reflecting both order flags."""
        ...

    @property
    def jump(self) -> set[str]:
        """Return an independent snapshot of words that may be skipped.

Returns
-------
set[str]
    An independent container. Editing it does not change the Configs instance."""
        ...

    def add_jump(self, token: str) -> bool:
        """Add or update a rule for words that may be skipped.
        
        Parameters
        ----------
        token : str
            Nonempty word token. Exact strings are normalized to lowercase and expanded
            to the stored lowercase, uppercase and titlecase forms. Unrelated word
            namespaces must not conflict after the three forms are generated; jump words may overlap.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def del_jump(self, token: str) -> bool:
        """Delete a rule for words that may be skipped.
        
        Parameters
        ----------
        token : str
            Nonempty word token. Exact strings are normalized to lowercase and expanded
            to the stored lowercase, uppercase and titlecase forms. Unrelated word
            namespaces must not conflict after the three forms are generated; jump words may overlap.
        
        Returns
        -------
        bool
            True when a rule existed and was removed; False when it was absent.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def set_jump(self, tokens: set[str] | None=None) -> bool:
        """Replace the rules for words that may be skipped.
        
        Parameters
        ----------
        tokens : set[str] | None, default None
            Replacement set of strings. None restores this namespace's defaults; an
            empty set removes its rules. Invalid replacements leave the previous rules
            intact.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    @property
    def pertain(self) -> set[str]:
        """Return an independent snapshot of date-joining words such as of.

Returns
-------
set[str]
    An independent container. Editing it does not change the Configs instance."""
        ...

    def add_pertain(self, token: str) -> bool:
        """Add or update a rule for date-joining words such as of.
        
        Parameters
        ----------
        token : str
            Nonempty word token. Exact strings are normalized to lowercase and expanded
            to the stored lowercase, uppercase and titlecase forms. Unrelated word
            namespaces must not conflict after the three forms are generated; jump words may overlap.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def del_pertain(self, token: str) -> bool:
        """Delete a rule for date-joining words such as of.
        
        Parameters
        ----------
        token : str
            Nonempty word token. Exact strings are normalized to lowercase and expanded
            to the stored lowercase, uppercase and titlecase forms. Unrelated word
            namespaces must not conflict after the three forms are generated; jump words may overlap.
        
        Returns
        -------
        bool
            True when a rule existed and was removed; False when it was absent.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def set_pertain(self, tokens: set[str] | None=None) -> bool:
        """Replace the rules for date-joining words such as of.
        
        Parameters
        ----------
        tokens : set[str] | None, default None
            Replacement set of strings. None restores this namespace's defaults; an
            empty set removes its rules. Invalid replacements leave the previous rules
            intact.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    @property
    def utc(self) -> set[str]:
        """Return an independent snapshot of zero-offset timezone aliases.

Returns
-------
set[str]
    An independent container. Editing it does not change the Configs instance."""
        ...

    def add_utc(self, token: str) -> bool:
        """Add or update a rule for zero-offset timezone aliases.
        
        Parameters
        ----------
        token : str
            Nonempty word token. Exact strings are normalized to lowercase and expanded
            to the stored lowercase, uppercase and titlecase forms. Unrelated word
            namespaces must not conflict after the three forms are generated; jump words may overlap.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def del_utc(self, token: str) -> bool:
        """Delete a rule for zero-offset timezone aliases.
        
        Parameters
        ----------
        token : str
            Nonempty word token. Exact strings are normalized to lowercase and expanded
            to the stored lowercase, uppercase and titlecase forms. Unrelated word
            namespaces must not conflict after the three forms are generated; jump words may overlap.
        
        Returns
        -------
        bool
            True when a rule existed and was removed; False when it was absent.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def set_utc(self, tokens: set[str] | None=None) -> bool:
        """Replace the rules for zero-offset timezone aliases.
        
        Parameters
        ----------
        tokens : set[str] | None, default None
            Replacement set of strings. None restores this namespace's defaults; an
            empty set removes its rules. Invalid replacements leave the previous rules
            intact.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    @property
    def tzoffset(self) -> dict[str, int]:
        """Return an independent snapshot of timezone aliases and fixed offsets in seconds.

Returns
-------
dict[str, int]
    An independent container. Editing it does not change the Configs instance."""
        ...

    def add_tzoffset(self, token: str, hours: SupportsIndex=0, minutes: SupportsIndex=0, seconds: SupportsIndex=0) -> bool:
        """Add or update a rule for timezone aliases and fixed offsets in seconds.
        
        Parameters
        ----------
        token : str
            Nonempty word token. Exact strings are normalized to lowercase and expanded
            to the stored lowercase, uppercase and titlecase forms. Unrelated word
            namespaces must not conflict after the three forms are generated; jump words may overlap.
        hours : int, default 0
            Signed hours contributing to the fixed UTC offset. The combined offset must
            be strictly between -24 and +24 hours; only integers are accepted.
        minutes : int, default 0
            Signed minutes contributing to the fixed UTC offset. The combined offset
            must be strictly between -24 and +24 hours; only integers are accepted.
        seconds : int, default 0
            Signed seconds contributing to the fixed UTC offset. The combined offset
            must be strictly between -24 and +24 hours; only integers are accepted.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def del_tzoffset(self, token: str) -> bool:
        """Delete a rule for timezone aliases and fixed offsets in seconds.
        
        Parameters
        ----------
        token : str
            Nonempty word token. Exact strings are normalized to lowercase and expanded
            to the stored lowercase, uppercase and titlecase forms. Unrelated word
            namespaces must not conflict after the three forms are generated; jump words may overlap.
        
        Returns
        -------
        bool
            True when a rule existed and was removed; False when it was absent.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def set_tzoffset(self, mapping: dict[str, _MapValue] | None=None) -> bool:
        """Replace the rules for timezone aliases and fixed offsets in seconds.
        
        Parameters
        ----------
        mapping : dict[str, SupportsIndex] | None, default None
            Replacement dictionary from words to this namespace's integer values. None
            restores its defaults; an empty dictionary clears it. Values follow the same
            bounds as add_*. Python and NumPy integers and valid __index__ objects
            are accepted; bool, numpy.bool_, floats and numeric text are rejected.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    @property
    def tzone(self) -> set[str]:
        """Return an independent snapshot of registered case-sensitive ZoneInfo names.

Returns
-------
set[str]
    An independent container. Editing it does not change the Configs instance."""
        ...

    def add_tzone(self, key: str) -> bool:
        """Add or update a rule for registered case-sensitive ZoneInfo names.
        
        Parameters
        ----------
        key : str
            Case-sensitive ZoneInfo key, for example Asia/Shanghai. It is loaded and
            validated when registered, not on every parse.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def del_tzone(self, key: str) -> bool:
        """Delete a rule for registered case-sensitive ZoneInfo names.
        
        Parameters
        ----------
        key : str
            Case-sensitive ZoneInfo key, for example Asia/Shanghai. It is loaded and
            validated when registered, not on every parse.
        
        Returns
        -------
        bool
            True when a rule existed and was removed; False when it was absent.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def set_tzone(self, keys: set[str] | None=None) -> bool:
        """Replace the rules for registered case-sensitive ZoneInfo names.
        
        Parameters
        ----------
        keys : set[str] | None, default None
            Replacement set of case-sensitive ZoneInfo keys. None or an empty set clears
            all regional registrations. Names are fixed and validated before loading.
            The whole replacement is applied only after all names load successfully.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    @property
    def month(self) -> dict[str, int]:
        """Return an independent snapshot of month names and numbers from 1 through 12.

Returns
-------
dict[str, int]
    An independent container. Editing it does not change the Configs instance."""
        ...

    def add_month(self, token: str, month: SupportsIndex) -> bool:
        """Add or update a rule for month names and numbers from 1 through 12.
        
        Parameters
        ----------
        token : str
            Nonempty word token. Exact strings are normalized to lowercase and expanded
            to the stored lowercase, uppercase and titlecase forms. Unrelated word
            namespaces must not conflict after the three forms are generated; jump words may overlap.
        month : int
            1 through 12. Values must implement the integer index protocol; floats are
            rejected.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def del_month(self, token: str) -> bool:
        """Delete a rule for month names and numbers from 1 through 12.
        
        Parameters
        ----------
        token : str
            Nonempty word token. Exact strings are normalized to lowercase and expanded
            to the stored lowercase, uppercase and titlecase forms. Unrelated word
            namespaces must not conflict after the three forms are generated; jump words may overlap.
        
        Returns
        -------
        bool
            True when a rule existed and was removed; False when it was absent.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def set_month(self, mapping: dict[str, _MapValue] | None=None) -> bool:
        """Replace the rules for month names and numbers from 1 through 12.
        
        Parameters
        ----------
        mapping : dict[str, SupportsIndex] | None, default None
            Replacement dictionary from words to this namespace's integer values. None
            restores its defaults; an empty dictionary clears it. Values follow the same
            bounds as add_*. Python and NumPy integers and valid __index__ objects
            are accepted; bool, numpy.bool_, floats and numeric text are rejected.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    @property
    def weekday(self) -> dict[str, int]:
        """Return an independent snapshot of weekday names and numbers, Monday=0 through Sunday=6.

Returns
-------
dict[str, int]
    An independent container. Editing it does not change the Configs instance."""
        ...

    def add_weekday(self, token: str, weekday: SupportsIndex) -> bool:
        """Add or update a rule for weekday names and numbers, Monday=0 through Sunday=6.
        
        Parameters
        ----------
        token : str
            Nonempty word token. Exact strings are normalized to lowercase and expanded
            to the stored lowercase, uppercase and titlecase forms. Unrelated word
            namespaces must not conflict after the three forms are generated; jump words may overlap.
        weekday : int
            0 (Monday) through 6 (Sunday). Values must implement the integer index
            protocol; floats are rejected.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def del_weekday(self, token: str) -> bool:
        """Delete a rule for weekday names and numbers, Monday=0 through Sunday=6.
        
        Parameters
        ----------
        token : str
            Nonempty word token. Exact strings are normalized to lowercase and expanded
            to the stored lowercase, uppercase and titlecase forms. Unrelated word
            namespaces must not conflict after the three forms are generated; jump words may overlap.
        
        Returns
        -------
        bool
            True when a rule existed and was removed; False when it was absent.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def set_weekday(self, mapping: dict[str, _MapValue] | None=None) -> bool:
        """Replace the rules for weekday names and numbers, Monday=0 through Sunday=6.
        
        Parameters
        ----------
        mapping : dict[str, SupportsIndex] | None, default None
            Replacement dictionary from words to this namespace's integer values. None
            restores its defaults; an empty dictionary clears it. Values follow the same
            bounds as add_*. Python and NumPy integers and valid __index__ objects
            are accepted; bool, numpy.bool_, floats and numeric text are rejected.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    @property
    def hms(self) -> dict[str, int]:
        """Return an independent snapshot of clock-unit names: 0 for hours, 1 for minutes and 2 for seconds.

Returns
-------
dict[str, int]
    An independent container. Editing it does not change the Configs instance."""
        ...

    def add_hms(self, token: str, flag: SupportsIndex) -> bool:
        """Add or update a rule for clock-unit names: 0 for hours, 1 for minutes and 2 for seconds.
        
        Parameters
        ----------
        token : str
            Nonempty word token. Exact strings are normalized to lowercase and expanded
            to the stored lowercase, uppercase and titlecase forms. Unrelated word
            namespaces must not conflict after the three forms are generated; jump words may overlap.
        flag : int
            0 for hours, 1 for minutes, 2 for seconds.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def del_hms(self, token: str) -> bool:
        """Delete a rule for clock-unit names: 0 for hours, 1 for minutes and 2 for seconds.
        
        Parameters
        ----------
        token : str
            Nonempty word token. Exact strings are normalized to lowercase and expanded
            to the stored lowercase, uppercase and titlecase forms. Unrelated word
            namespaces must not conflict after the three forms are generated; jump words may overlap.
        
        Returns
        -------
        bool
            True when a rule existed and was removed; False when it was absent.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def set_hms(self, mapping: dict[str, _MapValue] | None=None) -> bool:
        """Replace the rules for clock-unit names: 0 for hours, 1 for minutes and 2 for seconds.
        
        Parameters
        ----------
        mapping : dict[str, SupportsIndex] | None, default None
            Replacement dictionary from words to this namespace's integer values. None
            restores its defaults; an empty dictionary clears it. Values follow the same
            bounds as add_*. Python and NumPy integers and valid __index__ objects
            are accepted; bool, numpy.bool_, floats and numeric text are rejected.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    @property
    def ampm(self) -> dict[str, int]:
        """Return an independent snapshot of AM/PM names: 0 for AM and 1 for PM.

Returns
-------
dict[str, int]
    An independent container. Editing it does not change the Configs instance."""
        ...

    def add_ampm(self, token: str, flag: SupportsIndex) -> bool:
        """Add or update a rule for AM/PM names: 0 for AM and 1 for PM.
        
        Parameters
        ----------
        token : str
            Nonempty word token. Exact strings are normalized to lowercase and expanded
            to the stored lowercase, uppercase and titlecase forms. Unrelated word
            namespaces must not conflict after the three forms are generated; jump words may overlap.
        flag : int
            0 for AM or 1 for PM.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def del_ampm(self, token: str) -> bool:
        """Delete a rule for AM/PM names: 0 for AM and 1 for PM.
        
        Parameters
        ----------
        token : str
            Nonempty word token. Exact strings are normalized to lowercase and expanded
            to the stored lowercase, uppercase and titlecase forms. Unrelated word
            namespaces must not conflict after the three forms are generated; jump words may overlap.
        
        Returns
        -------
        bool
            True when a rule existed and was removed; False when it was absent.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def set_ampm(self, mapping: dict[str, _MapValue] | None=None) -> bool:
        """Replace the rules for AM/PM names: 0 for AM and 1 for PM.
        
        Parameters
        ----------
        mapping : dict[str, SupportsIndex] | None, default None
            Replacement dictionary from words to this namespace's integer values. None
            restores its defaults; an empty dictionary clears it. Values follow the same
            bounds as add_*. Python and NumPy integers and valid __index__ objects
            are accepted; bool, numpy.bool_, floats and numeric text are rejected.
        
        Returns
        -------
        bool
            True after the validated edit succeeds. A failed edit raises an error and
            keeps the previous rules.
        
        Raises
        ------
        TypeError
            An argument has an unsupported type.
        ConfigError
            A token, mapped value or combination of rules is invalid.
        OverflowError
            An integer conversion or result exceeds the supported range."""
        ...

    def clear_settings(self) -> bool:
        """Remove all word and region rules while preserving date-order flags.

Returns
-------
bool
    True after the validated edit succeeds. A failed edit raises an error and
    keeps the previous rules."""
        ...

    def reset_settings(self) -> bool:
        """Restore default word rules and clear registered regions; preserve date-order flags.

Returns
-------
bool
    True after the validated edit succeeds. A failed edit raises an error and
    keeps the previous rules."""
        ...

    def __repr__(self) -> str:
        """Return a readable summary of this configuration.

Returns
-------
str
    The value described above, in the stated type and units; None represents an
    absent optional field or offset where indicated."""
        ...

@overload
def parse_str(dtstr: str, default: _Default | None=None, yearfirst: bool | np.bool_ | None=None, dayfirst: bool | np.bool_ | None=None, ignoretz: bool | np.bool_=True, isoformat: bool | np.bool_=True, strict: bool | np.bool_=False, cfg: Configs | None=None, dtclass: None=None) -> datetime.datetime:
    """Parse date/time text into the requested datetime class.
    
    The parser recognizes fields and forwards timezone and fold to the output constructor. It does not repair or reject missing regional times itself. A default datetime supplies fold; otherwise fold=0. Explicit invalid fields follow strict, and the chosen output type decides its representable date range.
    
    Parameters
    ----------
    dtstr : str
        Date/time text to parse. This argument must be a string.
    default : date-like input | None, default None
        An independently complete date used to fill missing year, month and day
        only. Date/datetime subclasses, complete date text, numeric epoch seconds
        and NumPy datetime64 are supported. A datetime also supplies its stored
        fold; its clock and timezone are not defaults. Pandas NaT is rejected.
        The fallback date does not impose the output datetime's year range.
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
        With AM/PM, strict mode requires hours 1 through 12. Non-strict mode limits
        the original hour to 1 through 12 before applying AM/PM. True also rejects
        explicit invalid fields, conflicting repeated fields and a
        weekday inconsistent with a full written date. False clips invalid fields
        without carrying and allows later conflicting fields to win. A two-digit
        year requires False and a complete default date.
    cfg : Configs | None, default None
        Optional Configs vocabulary and ordering rules for text. None uses the
        library defaults.
    dtclass : None, default None
        Constructor for the completed datetime fields. None selects
        datetime.datetime. Regional existence and repeated-time policy belong to
        this constructor; Pydt rejects missing local times.
    
    Returns
    -------
    datetime.datetime
        The requested datetime result. A custom constructor may return None when
        permitted by its overload.
    
    Raises
    ------
    TypeError
        An argument has an unsupported type.
    ParseError
        Text cannot be interpreted, a strict field is invalid or conflicts with another,
        or a required date field is missing.
    ValueError
        A numeric scalar is NaN, a date value is missing, or the chosen output
        constructor rejects the completed fields. Callback errors propagate unchanged.
    OverflowError
        An integer conversion or result exceeds the supported range.
    
    Examples
    --------
    >>> parse_str("2024-01-02 12:99").minute
    59
    >>> parse_str("2024-05-07T15:30+08:00", ignoretz=False).isoformat()
    '2024-05-07T15:30:00+08:00'

    Boolean options accept only bool or numpy.bool_. Other values raise TypeError
    without calling their truth-conversion methods. yearfirst and dayfirst also
    accept None to use the corresponding Configs preference."""
    ...

@overload
def parse_str(dtstr: str, default: _Default | None=None, yearfirst: bool | np.bool_ | None=None, dayfirst: bool | np.bool_ | None=None, ignoretz: bool | np.bool_=True, isoformat: bool | np.bool_=True, strict: bool | np.bool_=False, cfg: Configs | None=None, dtclass: type[_DT]=...) -> _DT:
    """Parse date/time text into the requested datetime class.
    
    The parser recognizes fields and forwards timezone and fold to the output constructor. It does not repair or reject missing regional times itself. A default datetime supplies fold; otherwise fold=0. Explicit invalid fields follow strict, and the chosen output type decides its representable date range.
    
    Parameters
    ----------
    dtstr : str
        Date/time text to parse. This argument must be a string.
    default : date-like input | None, default None
        An independently complete date used to fill missing year, month and day
        only. Date/datetime subclasses, complete date text, numeric epoch seconds
        and NumPy datetime64 are supported. A datetime also supplies its stored
        fold; its clock and timezone are not defaults. Pandas NaT is rejected.
        The fallback date does not impose the output datetime's year range.
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
        With AM/PM, strict mode requires hours 1 through 12. Non-strict mode limits
        the original hour to 1 through 12 before applying AM/PM. True also rejects
        explicit invalid fields, conflicting repeated fields and a
        weekday inconsistent with a full written date. False clips invalid fields
        without carrying and allows later conflicting fields to win. A two-digit
        year requires False and a complete default date.
    cfg : Configs | None, default None
        Optional Configs vocabulary and ordering rules for text. None uses the
        library defaults.
    dtclass : Callable[..., datetime subclass], optional
        Constructor for the completed datetime fields. None selects
        datetime.datetime. Regional existence and repeated-time policy belong to
        this constructor; Pydt rejects missing local times.
    
    Returns
    -------
    datetime subclass
        The requested datetime result. A custom constructor may return None when
        permitted by its overload.
    
    Raises
    ------
    TypeError
        An argument has an unsupported type.
    ParseError
        Text cannot be interpreted, a strict field is invalid or conflicts with another,
        or a required date field is missing.
    ValueError
        A numeric scalar is NaN, a date value is missing, or the chosen output
        constructor rejects the completed fields. Callback errors propagate unchanged.
    OverflowError
        An integer conversion or result exceeds the supported range.

    Boolean options accept only bool or numpy.bool_. Other values raise TypeError
    without calling their truth-conversion methods. yearfirst and dayfirst also
    accept None to use the corresponding Configs preference."""
    ...

@overload
def parse_str(dtstr: str, default: _Default | None=None, yearfirst: bool | np.bool_ | None=None, dayfirst: bool | np.bool_ | None=None, ignoretz: bool | np.bool_=True, isoformat: bool | np.bool_=True, strict: bool | np.bool_=False, cfg: Configs | None=None, dtclass: Callable[..., _DT | None]=...) -> _DT | None:
    """Parse date/time text into the requested datetime class.
    
    The parser recognizes fields and forwards timezone and fold to the output constructor. It does not repair or reject missing regional times itself. A default datetime supplies fold; otherwise fold=0. Explicit invalid fields follow strict, and the chosen output type decides its representable date range.
    
    Parameters
    ----------
    dtstr : str
        Date/time text to parse. This argument must be a string.
    default : date-like input | None, default None
        An independently complete date used to fill missing year, month and day
        only. Date/datetime subclasses, complete date text, numeric epoch seconds
        and NumPy datetime64 are supported. A datetime also supplies its stored
        fold; its clock and timezone are not defaults. Pandas NaT is rejected.
        The fallback date does not impose the output datetime's year range.
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
        With AM/PM, strict mode requires hours 1 through 12. Non-strict mode limits
        the original hour to 1 through 12 before applying AM/PM. True also rejects
        explicit invalid fields, conflicting repeated fields and a
        weekday inconsistent with a full written date. False clips invalid fields
        without carrying and allows later conflicting fields to win. A two-digit
        year requires False and a complete default date.
    cfg : Configs | None, default None
        Optional Configs vocabulary and ordering rules for text. None uses the
        library defaults.
    dtclass : Callable[..., datetime subclass | None], optional
        Constructor for the completed datetime fields. None selects
        datetime.datetime. Regional existence and repeated-time policy belong to
        this constructor; Pydt rejects missing local times.
    
    Returns
    -------
    datetime subclass | None
        The requested datetime result. A custom constructor may return None when
        permitted by its overload.
    
    Raises
    ------
    TypeError
        An argument has an unsupported type.
    ParseError
        Text cannot be interpreted, a strict field is invalid or conflicts with another,
        or a required date field is missing.
    ValueError
        A numeric scalar is NaN, a date value is missing, or the chosen output
        constructor rejects the completed fields. Callback errors propagate unchanged.
    OverflowError
        An integer conversion or result exceeds the supported range.

    Boolean options accept only bool or numpy.bool_. Other values raise TypeError
    without calling their truth-conversion methods. yearfirst and dayfirst also
    accept None to use the corresponding Configs preference."""
    ...

@overload
def parse(dtobj: str | datetime.datetime | datetime.date | int | float | np.datetime64, default: _Default | None=None, yearfirst: bool | np.bool_ | None=None, dayfirst: bool | np.bool_ | None=None, ignoretz: bool | np.bool_=True, isoformat: bool | np.bool_=True, strict: bool | np.bool_=False, cfg: Configs | None=None, dtclass: None=None) -> datetime.datetime:
    """Convert text or a supported scalar date/time value into the requested datetime class.
    
    The parser recognizes fields and forwards timezone and fold to the output constructor. It does not repair or reject missing regional times itself. A default datetime supplies fold; otherwise fold=0. Explicit invalid fields follow strict, and the chosen output type decides its representable date range.
    
    Parameters
    ----------
    dtobj : str | datetime.datetime | datetime.date | int | float | np.datetime64
        One supported date/time input: text, a Python date/datetime, numeric epoch
        seconds, or a NumPy datetime64 scalar. NaT and unsupported containers are
        rejected.
    default : date-like input | None, default None
        An independently complete date used to fill missing year, month and day
        only. Date/datetime subclasses, complete date text, numeric epoch seconds
        and NumPy datetime64 are supported. A datetime also supplies its stored
        fold; its clock and timezone are not defaults. Pandas NaT is rejected.
        The fallback date does not impose the output datetime's year range.
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
        With AM/PM, strict mode requires hours 1 through 12. Non-strict mode limits
        the original hour to 1 through 12 before applying AM/PM. True also rejects
        explicit invalid fields, conflicting repeated fields and a
        weekday inconsistent with a full written date. False clips invalid fields
        without carrying and allows later conflicting fields to win. A two-digit
        year requires False and a complete default date.
    cfg : Configs | None, default None
        Optional Configs vocabulary and ordering rules for text. None uses the
        library defaults.
    dtclass : None, default None
        Constructor for the completed datetime fields. None selects
        datetime.datetime. Regional existence and repeated-time policy belong to
        this constructor; Pydt rejects missing local times.
    
    Returns
    -------
    datetime.datetime
        The requested datetime result. A custom constructor may return None when
        permitted by its overload.
    
    Raises
    ------
    TypeError
        An argument has an unsupported type.
    ParseError
        Text cannot be interpreted, a strict field is invalid or conflicts with another,
        or a required date field is missing.
    ValueError
        A numeric scalar is NaN, a date value is missing, or the chosen output
        constructor rejects the completed fields. Callback errors propagate unchanged.
    OverflowError
        An integer conversion or result exceeds the supported range.
    
    Examples
    --------
    >>> parse(1.1).isoformat()
    '1970-01-01T00:00:01.100000'

    Boolean options accept only bool or numpy.bool_. Other values raise TypeError
    without calling their truth-conversion methods. yearfirst and dayfirst also
    accept None to use the corresponding Configs preference."""
    ...

@overload
def parse(dtobj: str | datetime.datetime | datetime.date | int | float | np.datetime64, default: _Default | None=None, yearfirst: bool | np.bool_ | None=None, dayfirst: bool | np.bool_ | None=None, ignoretz: bool | np.bool_=True, isoformat: bool | np.bool_=True, strict: bool | np.bool_=False, cfg: Configs | None=None, dtclass: type[_DT]=...) -> _DT:
    """Convert text or a supported scalar date/time value into the requested datetime class.
    
    The parser recognizes fields and forwards timezone and fold to the output constructor. It does not repair or reject missing regional times itself. A default datetime supplies fold; otherwise fold=0. Explicit invalid fields follow strict, and the chosen output type decides its representable date range.
    
    Parameters
    ----------
    dtobj : str | datetime.datetime | datetime.date | int | float | np.datetime64
        One supported date/time input: text, a Python date/datetime, numeric epoch
        seconds, or a NumPy datetime64 scalar. NaT and unsupported containers are
        rejected.
    default : date-like input | None, default None
        An independently complete date used to fill missing year, month and day
        only. Date/datetime subclasses, complete date text, numeric epoch seconds
        and NumPy datetime64 are supported. A datetime also supplies its stored
        fold; its clock and timezone are not defaults. Pandas NaT is rejected.
        The fallback date does not impose the output datetime's year range.
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
        With AM/PM, strict mode requires hours 1 through 12. Non-strict mode limits
        the original hour to 1 through 12 before applying AM/PM. True also rejects
        explicit invalid fields, conflicting repeated fields and a
        weekday inconsistent with a full written date. False clips invalid fields
        without carrying and allows later conflicting fields to win. A two-digit
        year requires False and a complete default date.
    cfg : Configs | None, default None
        Optional Configs vocabulary and ordering rules for text. None uses the
        library defaults.
    dtclass : Callable[..., datetime subclass], optional
        Constructor for the completed datetime fields. None selects
        datetime.datetime. Regional existence and repeated-time policy belong to
        this constructor; Pydt rejects missing local times.
    
    Returns
    -------
    datetime subclass
        The requested datetime result. A custom constructor may return None when
        permitted by its overload.
    
    Raises
    ------
    TypeError
        An argument has an unsupported type.
    ParseError
        Text cannot be interpreted, a strict field is invalid or conflicts with another,
        or a required date field is missing.
    ValueError
        A numeric scalar is NaN, a date value is missing, or the chosen output
        constructor rejects the completed fields. Callback errors propagate unchanged.
    OverflowError
        An integer conversion or result exceeds the supported range.

    Boolean options accept only bool or numpy.bool_. Other values raise TypeError
    without calling their truth-conversion methods. yearfirst and dayfirst also
    accept None to use the corresponding Configs preference."""
    ...

@overload
def parse(dtobj: str | datetime.datetime | datetime.date | int | float | np.datetime64, default: _Default | None=None, yearfirst: bool | np.bool_ | None=None, dayfirst: bool | np.bool_ | None=None, ignoretz: bool | np.bool_=True, isoformat: bool | np.bool_=True, strict: bool | np.bool_=False, cfg: Configs | None=None, dtclass: Callable[..., _DT | None]=...) -> _DT | None:
    """Convert text or a supported scalar date/time value into the requested datetime class.
    
    The parser recognizes fields and forwards timezone and fold to the output constructor. It does not repair or reject missing regional times itself. A default datetime supplies fold; otherwise fold=0. Explicit invalid fields follow strict, and the chosen output type decides its representable date range.
    
    Parameters
    ----------
    dtobj : str | datetime.datetime | datetime.date | int | float | np.datetime64
        One supported date/time input: text, a Python date/datetime, numeric epoch
        seconds, or a NumPy datetime64 scalar. NaT and unsupported containers are
        rejected.
    default : date-like input | None, default None
        An independently complete date used to fill missing year, month and day
        only. Date/datetime subclasses, complete date text, numeric epoch seconds
        and NumPy datetime64 are supported. A datetime also supplies its stored
        fold; its clock and timezone are not defaults. Pandas NaT is rejected.
        The fallback date does not impose the output datetime's year range.
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
        With AM/PM, strict mode requires hours 1 through 12. Non-strict mode limits
        the original hour to 1 through 12 before applying AM/PM. True also rejects
        explicit invalid fields, conflicting repeated fields and a
        weekday inconsistent with a full written date. False clips invalid fields
        without carrying and allows later conflicting fields to win. A two-digit
        year requires False and a complete default date.
    cfg : Configs | None, default None
        Optional Configs vocabulary and ordering rules for text. None uses the
        library defaults.
    dtclass : Callable[..., datetime subclass | None], optional
        Constructor for the completed datetime fields. None selects
        datetime.datetime. Regional existence and repeated-time policy belong to
        this constructor; Pydt rejects missing local times.
    
    Returns
    -------
    datetime subclass | None
        The requested datetime result. A custom constructor may return None when
        permitted by its overload.
    
    Raises
    ------
    TypeError
        An argument has an unsupported type.
    ParseError
        Text cannot be interpreted, a strict field is invalid or conflicts with another,
        or a required date field is missing.
    ValueError
        A numeric scalar is NaN, a date value is missing, or the chosen output
        constructor rejects the completed fields. Callback errors propagate unchanged.
    OverflowError
        An integer conversion or result exceeds the supported range.

    Boolean options accept only bool or numpy.bool_. Other values raise TypeError
    without calling their truth-conversion methods. yearfirst and dayfirst also
    accept None to use the corresponding Configs preference."""
    ...

def parse_to_epoch(dtobj: _EpochInput, unit: str='us', default: _Default | None=None, yearfirst: bool | np.bool_ | None=None, dayfirst: bool | np.bool_ | None=None, ignoretz: bool | np.bool_=False, isoformat: bool | np.bool_=True, strict: bool | np.bool_=False, cfg: Configs | None=None, *, input_unit: str='s') -> int:
    """Convert one supported date/time value to integer epoch ticks.
    
    Returns a Python int directly, without selecting a datetime result class. Regional wall times use their timezone offset and fold without repairing or rejecting missing local times. A datetime default supplies its stored fold; otherwise fold=0. Explicit invalid fields follow strict. The integer result is not limited by datetime years or NumPy integer storage; actual arithmetic and timezone-conversion limits still raise errors.
    
    Parameters
    ----------
    dtobj : date-like or Polars Series
        One supported date/time input: text, a Python date/datetime, numeric epoch
        seconds, or a NumPy datetime64 scalar. With Polars installed, a one-value
        Datetime Series is also accepted. NaT, null values and longer Series are
        rejected. Polars remains an optional dependency.
    unit : str, default 'us'
        Output tick resolution: s, ms, us or ns. A finer remainder is floored,
        including for dates before 1970.
    default : date-like | None, default None
        An independently complete date used to fill missing year, month and day
        only. Date/datetime subclasses, complete date text, numeric epoch seconds
        and NumPy datetime64 are supported. A datetime also supplies its stored
        fold; its clock and timezone are not defaults. Pandas NaT is rejected.
        The fallback date does not impose the output datetime's year range.
    yearfirst : bool | None, default None
        Prefer a year in the first position of an ambiguous numeric date. None uses
        Configs when this parser option is optional.
    dayfirst : bool | None, default None
        Prefer a day before a month in an ambiguous numeric date. None uses Configs
        when this parser option is optional.
    ignoretz : bool, default False
        False applies timezone offsets to obtain UTC epoch ticks. True uses local
        clock fields without their offset, including for aware Python datetime,
        pandas Timestamp and Polars Datetime inputs. Naive values and numeric or
        NumPy ticks have no timezone offset to discard.
    isoformat : bool, default True
        Try ISO date/time forms before the general grammar. This does not restrict
        input to ISO text.
    strict : bool, default False
        With AM/PM, strict mode requires hours 1 through 12. Non-strict mode limits
        the original hour to 1 through 12 before applying AM/PM. True also rejects
        explicit invalid fields, conflicting repeated fields and a
        weekday inconsistent with a full written date. False clips invalid fields
        without carrying and allows later conflicting fields to win. A two-digit
        year requires False and a complete default date.
    cfg : Configs | None, default None
        Optional Configs vocabulary and ordering rules for text. None uses the
        library defaults.
    input_unit : str, default 's'
        Resolution of numeric input ticks only: s, ms, us or ns. The default s means
        a number such as 1 denotes one epoch second; native temporal values keep
        their own unit.
    
    Returns
    -------
    int
        Integer ticks since 1970-01-01T00:00:00. Naive dates use the same epoch
        without a host-local conversion; Python integers are not restricted to int64
        storage.
    
    Raises
    ------
    TypeError
        An argument has an unsupported type.
    ParseError
        Text cannot be interpreted, a strict field is invalid or conflicts with another,
        or a required date field is missing.
    ValueError
        A numeric scalar is NaN, a date value is missing, or the chosen output
        constructor rejects the completed fields. Callback errors propagate unchanged.
    OverflowError
        An integer conversion or result exceeds the supported range.
    
    Notes
    -----
    Native NumPy, pandas and Polars values retain their supported fine precision.
    Numeric input is converted directly at the requested precision; a coarser unit
    selects the earlier boundary. Python datetime retains its microsecond precision.
    Numeric default values keep their established microsecond conversion.
    
    Examples
    --------
    >>> from datetime import datetime, timezone, timedelta
    >>> value = datetime(1970, 1, 1, 8, tzinfo=timezone(timedelta(hours=8)))
    >>> parse_to_epoch(value)
    0
    >>> parse_to_epoch(value, ignoretz=True)
    28800000000
    >>> parse_to_epoch(1, "ms")
    1000
    >>> parse_to_epoch(1, "ms", input_unit="ms")
    1
    >>> parse_to_epoch(1e-9, unit="ns")
    1
    >>> parse_to_epoch("10000-01-02", "ns") > 2**63
    True

    Boolean options accept only bool or numpy.bool_. Other values raise TypeError
    without calling their truth-conversion methods. yearfirst and dayfirst also
    accept None to use the corresponding Configs preference."""
    ...
