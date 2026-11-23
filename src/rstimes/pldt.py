"""Native Polars date columns and expression namespaces.

Column calculations share a Rust kernel. Loading this module explicitly enables
the official Series/Expr namespaces; the base rsTimes import does not require
Polars. The implementation is being expanded under the approved PLDT contract.

Date text inputs and string defaults accept real str subclasses and read
their native stored content, without calling __str__ or overridden sequence
methods. Call str(value) explicitly when conversion is intended.
"""

from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping
from datetime import date, timezone, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from ._optional import POLARS as pl, PANDAS as pd, _warn_dependency_version

if pl is None:
    raise ImportError('Pldt requires Polars; install "rstimes[polars]".')

from polars.plugins import register_plugin_function

_warn_dependency_version("polars", pl.__version__)

from . import _native
from ._native import (_integer_arg, _bool_option, _pldt_native, _pldt_available_zones,
                      _pldt_objects, _pldt_register_missing, _pldt_policies, _pldt_timezone)
from .parser import Configs
from .delta import Delta
from .pydt import Pydt
from ._pldt_state import (register as _state_register, capture as _capture_state,
                          apply as _apply_state, recipe as _state_recipe, copy_value as _state_copy)
from ._class_protocol import definition as _state_definition
from ._polars import plain_series as _plain_series, register as _register_polars_base
from ._formatting import prepare_format as _prepare_format
from ._native import (_pldt_prepare_text, _pldt_prepare_format, _pldt_text,
                      _pldt_text_needed, _pldt_format_objects, _pldt_now,
                      _pldt_number_column, _pldt_number_objects,
                      _pldt_date_column, _pldt_date_objects, _pldt_date_buffer,
                      _pldt_calendar, _pldt_integer_objects, _pldt_integer_column,
                      _pldt_parts_column, _pldt_parts_time, _pldt_parts_objects, _pldt_parts_buffer, _pldt_combine, _pldt_iso_column, _pldt_iso_objects,
                      _pldt_frequency, _pldt_range_endpoints, _pldt_range, _pldt_range_external,
                      _pldt_component_column, _pldt_component_objects, _pldt_transform,
                      _pldt_operand_objects, _pldt_operand_column, _pldt_operand_ticks,
                      _pldt_binary, _pldt_scalar_callback, _pldt_period_prepare, _pldt_period,
                      _pldt_query, _pldt_query_clock, _pldt_diff, _pldt_diff_objects,
                      _pldt_output_prepare, _pldt_output, _pldt_nat_collision, _pldt_python_output,
                      _pldt_check_numpy, _pldt_check_temporal, _strftime_prepare, _pldt_strftime)
from ._pldt_timezone import prepare_timezone as _prepare_zone, prepare_source_timezone as _prepare_source_zone
from ._localization import (local_timezone as _local_zone, resolve_timezone as _resolve_zone,
                            named_timezone as _named_zone, _UTC_ALIASES)
from .errors import _own_error, _raise_argument_context, _external_error

if pd is not None:
    from ._range import frequency as _pandas_frequency, mature_units as _mature_units
else:
    _pandas_frequency = _mature_units = None

from typing import Any, Literal, SupportsIndex, SupportsFloat, Self, TypeAlias, TypeVar, TYPE_CHECKING, cast, overload
from collections.abc import Iterable
from types import MethodType, NotImplementedType
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
_SeriesT = TypeVar("_SeriesT", bound=pl.Series)
_PldtT = TypeVar("_PldtT", bound="Pldt")

if TYPE_CHECKING:
    from ._backend_types import _PandasTicks, _PandasDateTicks

if TYPE_CHECKING or pd is not None:
    from pandas.tseries.offsets import Day, Hour, Micro, Milli, Minute, Nano, Second

    _FixedFrequency: TypeAlias = str | _dt.timedelta | Nano | Micro | Milli | Second | Minute | Hour | Day
else:
    _FixedFrequency = str | _dt.timedelta

_PLUGIN_PATH = Path(_native.__file__)
_UNITS = ("ms", "us", "ns")
_PD_COLUMN = (pd.Series, pd.Index, pd.api.extensions.ExtensionArray) if pd is not None else ()
_PD_TABLE = (pd.DataFrame, pd.MultiIndex) if pd is not None else ()
# One import-time structural description; runtime identities remain pandas' own
# actual classes, without wrappers or per-call casts for their public tick views.
_PD_DATETIME_ARRAY = cast("type[_PandasDateTicks]", pd.arrays.DatetimeArray) if pd is not None else ()
_PD_TIMEDELTA_ARRAY = cast("type[_PandasTicks]", pd.arrays.TimedeltaArray) if pd is not None else ()
_PD_ARROW_ARRAY = pd.arrays.ArrowExtensionArray if pd is not None else ()
_PD_ARROW_DTYPE = pd.ArrowDtype if pd is not None else ()
_PD_TIMESTAMP_SCALARS = (_dt.datetime, pd.Timestamp) if pd is not None else ()
_NUMPY_FLOAT_TYPES = (np.float16, np.float32, np.float64)
_NUMPY_EXPORT_SUBNS = {"ps": -1, "fs": -2, "as": -3}
_NUMPY_DATE_CODES = {"Y": 0, "M": 1, "W": 2, "D": 4, "h": 5, "m": 6, "s": 7, "ms": 8, "us": 9, "ns": 10, "generic": 14}
_pldt_register_missing(pd.NA if pd is not None else None, pd.NaT if pd is not None else None)


@overload
def _unit(value: object, optional: Literal[False] = False) -> _Unit: ...
@overload
def _unit(value: object, optional: Literal[True]) -> _Unit | None: ...
def _unit(value, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise _own_error(TypeError("must be a string: 'ms', 'us' or 'ns'"), "unit", value)
    if type(value) is not str:
        value = str.__str__(value)
    if value not in _UNITS:
        raise _own_error(ValueError("must be 'ms', 'us' or 'ns'; Polars has no Datetime(s)"), "unit", value)
    return value


def _name(value):
    """Prepare stored name text before fallback, comparison or native output."""
    if value is None or type(value) is str:
        return value
    if not issubclass(type(value), str):
        raise _own_error(TypeError("must be a string or None"), "name", value)
    return str.__str__(value)


def _base_array(value, *, own=False):
    """Normalize only layout/byte order; keep date unit and numeric roles."""
    value = np.asarray(value)
    if value.ndim != 1:
        raise ValueError("Pldt: data must be one-dimensional; zero/two-dimensional arrays are not flattened")
    original = value
    if not value.dtype.isnative:
        value = value.astype(value.dtype.newbyteorder("="))
    value = np.ascontiguousarray(value)
    return value.copy() if own and value is original else value


def _pandas_timestamp_column(value) -> pl.Series | None:
    """Borrow a real Arrow timestamp through its public, validity-aware export."""
    if not isinstance(value, _PD_ARROW_ARRAY):
        return None
    dtype = value.dtype
    if (isinstance(dtype, _PD_ARROW_DTYPE) and dtype.kind == "M"
            and dtype.type in _PD_TIMESTAMP_SCALARS):
        # Arrow date32/date64 are also kind M; their scalar role is date,
        # not datetime. Do not route unrelated extension dtypes here.
        arrow_type = dtype.pyarrow_dtype
        exported = value.__arrow_array__()
        if exported.type != arrow_type:
            raise TypeError("Pldt: a pandas timestamp export must preserve its declared dtype")
        if arrow_type.unit == "s":
            # Polars has no Datetime(s); its Arrow import can wrap s -> ms.
            # Let Arrow check each conversion, before Polars receives it.
            try:
                exported = exported.cast("timestamp[ms]", safe=True)
            except ValueError as error:
                raise OverflowError("Pldt: timestamp seconds exceed Datetime(ms) capacity; Polars has no Datetime(s)") from error
            result = pl.from_arrow(exported, rechunk=False)
            if arrow_type.tz is not None:
                result = result.cast(pl.Datetime("ms", arrow_type.tz))
        else:
            result = pl.from_arrow(exported, rechunk=False)
        if not isinstance(result, pl.Series) or result.dtype.base_type() is not pl.Datetime:
            raise TypeError("Pldt: a pandas timestamp export must return a timestamp column")
        return result
    return None


def _numpy_export(source: pl.Series, writable: _Boolean, allow_copy: _Boolean,
                  allow_nat_collision: bool) -> np.ndarray:
    """Export the captured owner, retaining its exact validity/collision rules."""
    result = pl.Series.to_numpy(source, writable=writable, allow_copy=allow_copy)  # pyright: ignore[reportArgumentType] -- TY031; see tests/typing/pyright_exceptions.json.
    if not allow_nat_collision:
        row = _pldt_nat_collision(source)
        if row is not None:
            raise _own_error(OverflowError("valid date collides with the NumPy NaT reserved tick; use Arrow or to_physical with validity, or explicitly set allow_nat_collision=True"), f"data[{row}]", None)
    return result


def _zone_key(zone):
    if zone is None:
        return None
    if isinstance(zone, ZoneInfo):
        return _prepare_zone(zone, "data").key
    if isinstance(zone, timezone):
        seconds = zone.utcoffset(None).total_seconds()
        if seconds == 0:
            return "UTC"
        if seconds % 3600 == 0:
            return "Etc/GMT" + ("-" if seconds > 0 else "+") + str(abs(int(seconds)) // 3600)
    raise TypeError("Pldt: this source timezone cannot be represented by Polars; select a supported target tz")


def _construct(data, *, unit, name, copy: _Boolean, default, yearfirst: _Boolean | None, dayfirst: _Boolean | None, isoformat: _Boolean, strict: _Boolean, cfg, tz, policy):
    """Read source roles once, then produce one native result carrier."""
    source_type = type(data)
    # Built-in sequences can also be registered as virtual Mapping subclasses.
    if (source_type is list or source_type is tuple) and not issubclass(source_type, Mapping):
        return _pldt_objects(
            data, pl.Series, unit, None, "" if name is None else name,
            default, yearfirst, dayfirst, isoformat, strict, cfg, tz, policy,
        )
    if issubclass(source_type, (str, bytes, bytearray, date, Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame, pl.Expr) + _PD_TABLE) or data is None:
        raise TypeError("Pldt: data must be a one-dimensional date collection; use [value] for one date")
    source_name = None
    source_zone = None
    base_unit = None
    if issubclass(source_type, _PD_COLUMN):
        source_name = getattr(data, "name", None)
        selected_name = name if name is not None else _name(source_name) or ""
        if issubclass(source_type, (pd.Series, pd.Index)):
            data = data.array
            source_type = type(data)
        if issubclass(source_type, _PD_DATETIME_ARRAY):
            source_zone = ("UTC" if tz is not None else _zone_key(data.tz)) if data.tz is not None else None
            array = _base_array(data.asi8)
            code = _NUMPY_DATE_CODES[data.unit]
            carrier = pl.Series(selected_name, array)
            return _pldt_native(carrier, pl.Series, unit, copy, False, (code, 1), source_zone, tz, policy)
        arrow = _pandas_timestamp_column(data)
        if arrow is not None:
            data = arrow.rename(selected_name)
        elif getattr(data.dtype, "kind", None) in ("i", "u", "f"):
            if data.dtype.kind == "f" and data.dtype.type not in _NUMPY_FLOAT_TYPES:
                raise TypeError("Pldt: only actual NumPy float16/32/64 dtypes are supported numeric ticks")
            base_unit = "ns"
        elif getattr(data.dtype, "kind", None) in ("b", "m", "V", "c", "S"):
            raise TypeError("Pldt: this declared pandas dtype does not contain dates or supported numeric ticks")
        source_type = type(data)
    if issubclass(source_type, np.ndarray):
        data = _base_array(data)
        if data.dtype.kind in "bmVcS":
            raise TypeError("Pldt: Boolean, Duration, structured and complex arrays are not date inputs")
        if data.dtype.kind == "M":
            source_unit, multiplier = np.datetime_data(data.dtype)
            if source_unit not in _NUMPY_DATE_CODES:
                raise ValueError("Pldt: NumPy date unit must be years through nanoseconds")
            carrier = pl.Series("", data.view(np.int64))
            return _pldt_native(carrier, pl.Series, unit, copy, False, (_NUMPY_DATE_CODES[source_unit], multiplier), None, tz, policy).rename(name or "")
        if data.dtype.kind in "iuf":
            if data.dtype.kind == "f" and data.dtype.type not in _NUMPY_FLOAT_TYPES:
                raise TypeError("Pldt: extended NumPy floating values are not supported date ticks")
            data = pl.Series("", data.astype(np.float32) if data.dtype == np.dtype("float16") else data)
            # Known external NumPy storage must not persist into detached reads.
            # Rust makes the one owned result while the GIL is still held.
            copy = True
        source_type = type(data)
    if issubclass(source_type, pl.Series):
        data = _plain_series(data)  # Independent shell; retain typed native owner/chunks.
        source_name = data.name
        kind = data.dtype.base_type()
        if kind not in (pl.String, pl.Object) and (kind in (pl.Date, pl.Datetime, pl.Null) or data.dtype.is_numeric()):
            return _pldt_native(data, pl.Series, unit, copy, tz=tz, policy=policy).rename(name if name is not None else source_name)
        if kind is pl.String:
            return _text_eager(data, unit, tz, policy, default, yearfirst, dayfirst, isoformat, strict, cfg).rename(name if name is not None else source_name)
        if kind not in (pl.String, pl.Object):
            raise TypeError("Pldt: unsupported date dtype; Time/Duration/List/Struct/Boolean are not dates")
    # Rust obtains the iterator exactly once and preserves user protocol failures.
    return _pldt_objects(data, pl.Series, unit, base_unit, name if name is not None else _name(source_name) or "", default, yearfirst, dayfirst, isoformat, strict, cfg, tz, policy)


def _text_eager(source, unit, tz, policy, default=None, yearfirst: _Boolean | None=None,
                dayfirst: _Boolean | None=None, isoformat: _Boolean=True, strict: _Boolean=False, cfg=None, formatted=None):
    """Prepare live host data once, then parse typed String chunks in Rust."""
    prepared = None
    if formatted is None:
        effective_default = default
        if default is not None and not _pldt_text_needed(source):
            effective_default = None
        prepared = _pldt_prepare_text(cfg=cfg, default=effective_default,
                                     yearfirst=yearfirst, dayfirst=dayfirst,
                                     isoformat=isoformat, strict=strict, expression=False)
    return _pldt_text(source, pl.Series, prepared, formatted, unit, tz, policy)


_NO_FORMAT = object()


def _text_expression(source, *, unit=None, tz=None, default=None, yearfirst: _Boolean | None=None,
                     dayfirst: _Boolean | None=None, isoformat: _Boolean=True, strict: _Boolean=False, cfg=None,
                     ambiguous: _ExprAmbiguous="raise", nonexistent: _Nonexistent="raise", fmt=_NO_FORMAT):
    entry = "Pldt.parse" if fmt is _NO_FORMAT else "Pldt.strptime"
    try:
        target = _prepare_zone(tz)
        policy, mask, scalar = _timezone_policy(ambiguous, nonexistent, expression=True)
        if fmt is _NO_FORMAT:
            unit = _unit(unit, optional=True)
            context = _pldt_prepare_text(cfg=cfg, default=default, yearfirst=yearfirst,
                                         dayfirst=dayfirst, isoformat=isoformat,
                                         strict=strict, expression=True)
            options = {"prepared": context.plugin_kwargs(), "format": b""}
        else:
            context = _pldt_prepare_format(_prepare_format(fmt), cfg)
            if unit is None and context.has_fraction:
                raise _own_error(ValueError("a format containing %f requires an explicit unit for Expr output"), "unit", unit)
            unit = "us" if unit is None else _unit(unit)
            if target is None and context.has_timezone:
                raise _own_error(ValueError("a format containing a timezone directive requires an explicit tz for Expr output"), "tz", tz)
            options = context.plugin_kwargs()
        policy_data = policy.plugin_kwargs()
        kwargs = {"version": 1, "unit": unit, **options,
                  "target": None if target is None else target.plugin_kwargs(),
                  "policy": policy_data, "mask_scalar": scalar}
        ordered = policy_data["ambiguous"] in ("infer", "mask")
        return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_parse",
                                        args=[source] if mask is None else [source, mask],
                                        kwargs=kwargs, is_elementwise=not ordered and mask is None)
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


@overload
def _strptime_eager(cls: type[_PldtT], data: object, fmt: object, *, size: object=None, tz: object=None, unit: object=None, name: object=None, cfg: Configs | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
    ...
@overload
def _strptime_eager(cls: type[pl.Series], data: object, fmt: object, *, size: object=None, tz: object=None, unit: object=None, name: object=None, cfg: Configs | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Series:
    ...
def _strptime_eager(cls: type[_SeriesT], data, fmt, *, size=None, tz=None, unit=None, name=None,
                    cfg=None, ambiguous: _Ambiguous="raise", nonexistent: _Nonexistent="raise"):
    try:
        unit = _unit(unit, optional=True)
        name = _name(name)
        source_type = type(data)
        if name is None and issubclass(source_type, (pl.Series,) + _PD_COLUMN):
            name = _name(getattr(data, "name", None))
        compiled = _prepare_format(fmt)
        target = _prepare_zone(tz)
        policy, _, _ = _timezone_policy(ambiguous, nonexistent, expression=False)
        output = Pldt if cls is Pldt else pl.Series
        scalar = issubclass(source_type, (str, bytes, bytearray, date, int, float, np.generic)) or data is None or (pd is not None and (data is pd.NA or data is pd.NaT))
        if scalar:
            if size is None:
                raise _own_error(ValueError("a scalar strptime input requires size"), "size", size)
            size = _integer_arg(size, "Pldt.strptime", "size")
            if size < 0:
                raise _own_error(ValueError("size must be nonnegative"), "size", size)
        elif size is not None:
            raise _own_error(ValueError("omit size for a collection"), "size", size)
        if issubclass(source_type, pl.Series) and cast(pl.Series, data).dtype.base_type() in (pl.String, pl.Null):
            source = _plain_series(data)
            if source.dtype == pl.Null:
                source = source.cast(pl.String)
            context = _pldt_prepare_format(compiled, cfg)
            result = _pldt_text(source, output, None, context, unit, target, policy, name)
            return result if cls is Pldt else cls(result)
        if issubclass(source_type, (Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame, pl.Expr) + _PD_TABLE):
            raise _own_error(TypeError("strptime requires text or a one-dimensional text collection"), "dtstr", data)
        if issubclass(source_type, pl.Series) and cast(pl.Series, data).dtype.base_type() is not pl.Object:
            raise _own_error(TypeError("strptime requires a String or text Object column"), "dtstr", data)
        if issubclass(source_type, _PD_COLUMN) and getattr(getattr(data, "dtype"), "kind", None) not in ("O", "U"):
            raise _own_error(TypeError("strptime requires text values, not a numeric/date dtype"), "dtstr", data)
        if issubclass(source_type, np.ndarray):
            data = _base_array(data)
            if data.dtype.kind not in ("O", "U"):
                raise _own_error(TypeError("strptime requires text values, not a numeric/date dtype"), "dtstr", data)
        result = _pldt_format_objects(data, output, compiled, unit, target, policy,
                                       cfg, size, name or "")
        return result if cls is Pldt else cls(result)
    except Exception as error:
        _raise_argument_context(error, "Pldt.strptime", "arguments", None)


def _size(value, entry):
    value = _integer_arg(value, entry, "size")
    if value < 0:
        raise _own_error(ValueError("must be nonnegative"), "size", value)
    return value


@overload
def _clock_factory(cls: type[_PldtT], size: object, tz: object, unit: object, name: object, entry: object, naive: bool) -> _PldtT:
    ...
@overload
def _clock_factory(cls: type[pl.Series], size: object, tz: object, unit: object, name: object, entry: object, naive: bool) -> pl.Series:
    ...
def _clock_factory(cls: type[_SeriesT], size, tz, unit, name, entry, naive: bool):
    try:
        size = _size(size, entry)
        unit = "us" if unit is None else _unit(unit)
        name = _name(name)
        zone = _prepare_zone(_local_zone()) if naive and size else _prepare_zone(tz)
        target = Pldt if cls is Pldt else pl.Series
        result = _pldt_now(target, size, unit, name or "", zone, naive)
        return result if cls is Pldt else cls(result)
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


@overload
def _numeric_eager(cls: type[_PldtT], data: object, kind: object, *, size: object=None, tz: object=None, unit: object=None, name: object=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise', entry: object) -> _PldtT:
    ...
@overload
def _numeric_eager(cls: type[pl.Series], data: object, kind: object, *, size: object=None, tz: object=None, unit: object=None, name: object=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise', entry: object) -> pl.Series:
    ...
def _numeric_eager(cls: type[_SeriesT], data, kind, *, size=None, tz=None, unit=None, name=None,
                   ambiguous: _Ambiguous="raise", nonexistent: _Nonexistent="raise", entry):
    try:
        unit = _unit(unit, optional=True)
        name = _name(name)
        size = None if size is None else _size(size, entry)
        target_zone = _prepare_zone(tz)
        policy, _, _ = _timezone_policy(ambiguous, nonexistent, expression=False)
        source_type = type(data)
        if issubclass(source_type, (Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame, pl.Expr) + _PD_TABLE):
            raise _own_error(TypeError("requires a numeric scalar or one-dimensional numeric collection"), "data", data)
        column = False
        source_name = None
        if issubclass(source_type, _PD_COLUMN):
            source_name = getattr(data, "name", None)
            column = True
            if getattr(data.dtype, "kind", None) in ("M", "m", "b", "c", "S", "V"):
                raise _own_error(TypeError("this declared dtype is not numeric epoch input"), "data", data)
            if issubclass(source_type, (pd.Series, pd.Index)):
                data = data.array
                source_type = type(data)
        if issubclass(source_type, np.ndarray):
            data = _base_array(data)
            column = True
            if data.dtype.kind in "MmbcSV":
                raise _own_error(TypeError("this declared dtype is not numeric epoch input"), "data", data)
            if data.dtype.kind in "iufU":
                if data.dtype.kind == "f":
                    if kind == "micros" and data.dtype.type not in _NUMPY_FLOAT_TYPES:
                        raise _own_error(TypeError("integer microseconds reject extended floating types"), "data", data)
                    data = data.astype(np.float64) if data.dtype.type not in (np.float32, np.float64) else data
                data = pl.Series(name or "", data)
            source_type = type(data)
        target = Pldt if cls is Pldt else pl.Series
        local = _local_zone if kind == "local_timestamp" else None
        if issubclass(source_type, pl.Series):
            if size is not None:
                raise _own_error(ValueError("omit size for a collection"), "size", size)
            source = _plain_series(data)
            source_name = source.name
            if source.dtype.base_type() is not pl.Object:
                if name is not None:
                    source = source.rename(name)
                result = _pldt_number_column(source, target, kind, unit, target_zone, policy, local)
                return result if cls is Pldt else cls(result)
            data = source
            column = True
        name = _name(source_name) if name is None else name
        result = _pldt_number_objects(data, target, kind, unit, target_zone, policy,
                                       size, name or "", local, column)
        return result if cls is Pldt else cls(result)
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


def _numeric_expression(source, kind, *, unit=None, tz=None,
                        ambiguous: _ExprAmbiguous="raise", nonexistent: _Nonexistent="raise", entry):
    try:
        unit = _unit(unit, optional=True)
        target = _prepare_zone(tz)
        local = _prepare_zone(_local_zone()) if kind == "local_timestamp" else None
        policy, mask, scalar = _timezone_policy(ambiguous, nonexistent, expression=True)
        data = policy.plugin_kwargs()
        kwargs = {"version": 1, "operation": kind, "unit": unit,
                  "target": None if target is None else target.plugin_kwargs(),
                  "local": None if local is None else local.plugin_kwargs(),
                  "policy": data, "mask_scalar": scalar}
        return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_numbers",
                                        args=[source] if mask is None else [source, mask],
                                        kwargs=kwargs, is_elementwise=data["ambiguous"] not in ("infer", "mask") and mask is None)
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


@overload
def _range_factory(cls: type[_PldtT], start: object=None, *, end: object=None, periods: object=None, freq: object=None, tz: object=None, normalize: _Boolean=False, inclusive: str='both', unit: object=None, name: object=None, default: object=None, yearfirst: _Boolean | None=None, dayfirst: _Boolean | None=None, isoformat: _Boolean=True, strict: _Boolean=False, cfg: object=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
    ...
@overload
def _range_factory(cls: type[pl.Series], start: object=None, *, end: object=None, periods: object=None, freq: object=None, tz: object=None, normalize: _Boolean=False, inclusive: str='both', unit: object=None, name: object=None, default: object=None, yearfirst: _Boolean | None=None, dayfirst: _Boolean | None=None, isoformat: _Boolean=True, strict: _Boolean=False, cfg: object=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Series:
    ...
def _range_factory(cls: type[_SeriesT], start=None, *, end=None, periods=None, freq=None, tz=None,
                   normalize: _Boolean=False, inclusive: str="both", unit=None, name=None, default=None,
                   yearfirst: _Boolean | None=None, dayfirst: _Boolean | None=None, isoformat: _Boolean=True, strict: _Boolean=False, cfg=None,
                   ambiguous: _Ambiguous="raise", nonexistent: _Nonexistent="raise"):
    entry = "Pldt.date_range"
    try:
        unit = _unit(unit, optional=True)
        name = _name(name)
        if periods is not None:
            periods = _integer_arg(periods, entry, "periods")
            if periods < 0:
                raise _own_error(ValueError("must be nonnegative"), "periods", periods)
        normalize = _bool_option(normalize, entry, "normalize")
        isoformat = _bool_option(isoformat, entry, "isoformat")
        strict = _bool_option(strict, entry, "strict")
        yearfirst = None if yearfirst is None else _bool_option(yearfirst, entry, "yearfirst")
        dayfirst = None if dayfirst is None else _bool_option(dayfirst, entry, "dayfirst")
        if cfg is not None and not issubclass(type(cfg), Configs):
            raise _own_error(TypeError("must be Configs or None"), "cfg", cfg)
        if not isinstance(inclusive, str):
            raise _own_error(TypeError("must be both/left/right/neither"), "inclusive", inclusive)
        if type(inclusive) is not str:
            inclusive = str.__str__(inclusive)
        if inclusive not in ("both", "left", "right", "neither"):
            raise _own_error(ValueError("must be both/left/right/neither"), "inclusive", inclusive)
        policy, _, _ = _timezone_policy(ambiguous, nonexistent, expression=False)
        target = _prepare_zone(tz)
        if freq is None and (start is None or end is None or periods is None):
            freq = "D"
        metadata = None
        delegated = False
        frequency_type = type(freq)
        if freq is None:
            plan = None
        elif pd is not None and issubclass(frequency_type, pd.DateOffset) and not issubclass(frequency_type, timedelta):
            plan, metadata, delegated = _pandas_frequency(freq)  # pyright: ignore[reportOptionalCall] -- TY020; see tests/typing/pyright_exceptions.json.
        else:
            plan = _pldt_frequency(freq)
            delegated = plan is None
            if delegated:
                if pd is None:
                    raise ImportError("this special date_range rule requires optional pandas; install rstimes[pandas]")
                plan, metadata, delegated = _pandas_frequency(freq)  # pyright: ignore[reportOptionalCall] -- TY021; see tests/typing/pyright_exceptions.json.
        if delegated and sum(value is not None for value in (start, end, periods)) != 2:
            raise _own_error(ValueError("exactly two of start, end and periods are required with a frequency"), "arguments", None)
        inputs = _pldt_range_endpoints(start, end, policy, plan, unit, target, normalize, default,
                                      yearfirst, dayfirst, isoformat, strict, cfg, delegated)
        output = Pldt if cls is Pldt else pl.Series
        if not delegated:
            result = _pldt_range(output, inputs, periods, plan, policy, inclusive, name or "")
        else:
            first, last, carrier_unit = inputs.carrier()
            first = None if first is None else pd.Timestamp(np.datetime64(first, carrier_unit))
            last = None if last is None else pd.Timestamp(np.datetime64(last, carrier_unit))
            generation_unit, minimum_unit = _mature_units(metadata, inputs.unit, carrier_unit)  # pyright: ignore[reportOptionalCall] -- TY022; see tests/typing/pyright_exceptions.json.
            try:
                external = pd.date_range(start=first, end=last, periods=periods, freq=metadata,  # pyright: ignore[reportCallIssue] -- TY023; see tests/typing/pyright_exceptions.json.
                                         unit=generation_unit, inclusive="both")
            except Exception as error:
                raise _external_error(error)
            carrier = pl.Series("", _base_array(external.asi8))
            result = _pldt_range_external(output, inputs, carrier, external.unit, policy, inclusive,
                                         unit or minimum_unit, unit is None and minimum_unit is not None, name or "")
        return result if cls is Pldt else cls(result)
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


@overload
def _iso_factory(cls: type[_PldtT], data: object, *, size: object=None, tz: object=None, unit: object=None, name: object=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
    ...
@overload
def _iso_factory(cls: type[pl.Series], data: object, *, size: object=None, tz: object=None, unit: object=None, name: object=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Series:
    ...
def _iso_factory(cls: type[_SeriesT], data, *, size=None, tz=None, unit=None, name=None,
                 ambiguous: _Ambiguous="raise", nonexistent: _Nonexistent="raise"):
    try:
        unit = _unit(unit, optional=True)
        size = None if size is None else _size(size, "Pldt.fromisoformat")
        name = _name(name)
        target = _prepare_zone(tz)
        policy, _, _ = _timezone_policy(ambiguous, nonexistent, expression=False)
        source_type = type(data)
        if issubclass(source_type, (Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame, pl.Expr) + _PD_TABLE):
            raise _own_error(TypeError("requires ISO text or a one-dimensional text collection"), "dtstr", data)
        output = Pldt if cls is Pldt else pl.Series
        column = issubclass(source_type, _PD_COLUMN)
        source_name = _name(getattr(data, "name", None)) if column else None
        if issubclass(source_type, np.ndarray):
            data = _base_array(data)
            column = True
            source_type = type(data)
        if issubclass(source_type, pl.Series):
            if size is not None:
                raise _own_error(ValueError("omit size for a collection"), "size", size)
            data = _plain_series(data)
            source_name = data.name
            column = True
            if data.dtype.base_type() is not pl.Object:
                result = _pldt_iso_column(data.rename(name) if name is not None else data, output, unit, target, policy)
                return result if cls is Pldt else cls(result)
        result = _pldt_iso_objects(data, output, unit, target, policy, size,
                                   name if name is not None else source_name or "", column)
        return result if cls is Pldt else cls(result)
    except Exception as error:
        _raise_argument_context(error, "Pldt.fromisoformat", "arguments", None)


def _iso_expression(source, *, tz=None, unit=None, ambiguous: _ExprAmbiguous="raise", nonexistent: _Nonexistent="raise"):
    try:
        unit = _unit(unit, optional=True)
        target = _prepare_zone(tz)
        policy, mask, scalar = _timezone_policy(ambiguous, nonexistent, expression=True)
        data = policy.plugin_kwargs()
        kwargs = {"version": 1, "unit": unit, "target": None if target is None else target.plugin_kwargs(),
                  "policy": data, "mask_scalar": scalar}
        return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_iso",
                                        args=[source] if mask is None else [source, mask], kwargs=kwargs,
                                        is_elementwise=data["ambiguous"] not in ("mask", "infer") and mask is None)
    except Exception as error:
        _raise_argument_context(error, "Pldt.fromisoformat", "arguments", None)


@overload
def _date_factory(cls: type[_PldtT], data: object, kind: object, *, size: object=None, tz: object=None, unit: object=None, name: object=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
    ...
@overload
def _date_factory(cls: type[pl.Series], data: object, kind: object, *, size: object=None, tz: object=None, unit: object=None, name: object=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Series:
    ...
def _date_factory(cls: type[_SeriesT], data, kind, *, size=None, tz=None, unit=None, name=None,
                  ambiguous: _Ambiguous="raise", nonexistent: _Nonexistent="raise"):
    entry = "Pldt." + {"date": "fromdate", "datetime": "fromdatetime", "numpy": "fromdatetime64"}[kind]
    try:
        unit = _unit(unit, optional=True)
        name = _name(name)
        size = None if size is None else _size(size, entry)
        zone = _prepare_zone(tz)
        policy, _, _ = _timezone_policy(ambiguous, nonexistent, expression=False)
        source_type = type(data)
        if issubclass(source_type, (Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame, pl.Expr) + _PD_TABLE):
            raise _own_error(TypeError("requires a real date source or one-dimensional date collection"), "data", data)
        target = Pldt if cls is Pldt else pl.Series
        column = False
        source_name = None
        if issubclass(source_type, _PD_COLUMN):
            if kind == "numpy":
                raise _own_error(TypeError("fromdatetime64 requires real NumPy datetime64 sources"), "dt64", data)
            source_name = getattr(data, "name", None)
            column = True
            if issubclass(source_type, (pd.Series, pd.Index)):
                data = data.array
                source_type = type(data)
            if issubclass(source_type, _PD_DATETIME_ARRAY):
                if size is not None:
                    raise _own_error(ValueError("omit size for a collection"), "size", size)
                source_zone = _resolve_zone(data.tz)
                if source_zone is None or isinstance(source_zone, (timezone, ZoneInfo)):
                    rule = None
                    offset = None
                    if isinstance(source_zone, timezone):
                        delta = source_zone.utcoffset(None)
                        offset = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
                    elif source_zone is not None:
                        rule = _prepare_source_zone(source_zone)
                    if source_zone is None or offset is not None or rule is not None:
                        carrier = pl.Series(name if name is not None else _name(source_name) or "", _base_array(data.asi8))
                        result = _pldt_date_buffer(carrier, target, kind, _NUMPY_DATE_CODES[data.unit], rule,
                                                   offset, unit, zone, policy)
                        return result if cls is Pldt else cls(result)
                    if kind == "datetime" and zone is None:
                        _prepare_zone(source_zone, "data")
                    if unit is None:
                        unit = _unit("ms" if data.unit == "s" else data.unit)
                    data = _real_pandas_source(data, source_zone)
            arrow = _pandas_timestamp_column(data)
            if arrow is not None:
                data = arrow.rename(name if name is not None else _name(source_name) or "")
            source_type = type(data)
        if issubclass(source_type, np.ndarray):
            data = _base_array(data)
            column = True
            if data.dtype.kind == "M":
                if kind != "numpy":
                    raise _own_error(TypeError("use fromdatetime64 for NumPy date sources"), "data", data)
                if size is not None:
                    raise _own_error(ValueError("omit size for a collection"), "size", size)
                source_unit, multiplier = np.datetime_data(data.dtype)
                if source_unit not in _NUMPY_DATE_CODES:
                    raise _own_error(ValueError("NumPy date unit must be years through nanoseconds"), "dt64", data)
                carrier = pl.Series(name or "", data.view(np.int64))
                result = _pldt_native(carrier, target, unit, False, False,
                                      (_NUMPY_DATE_CODES[source_unit], multiplier), None, zone, policy)
                return result if cls is Pldt else cls(result)
            source_type = type(data)
        if issubclass(source_type, pl.Series):
            if kind == "numpy":
                raise _own_error(TypeError("fromdatetime64 requires a real NumPy source, not Polars"), "dt64", data)
            if size is not None:
                raise _own_error(ValueError("omit size for a collection"), "size", size)
            source = _plain_series(data)
            source_name = source.name
            if source.dtype.base_type() is not pl.Object:
                source = source.rename(name) if name is not None else source
                result = _pldt_date_column(source, target, kind, unit, zone, policy)
                return result if cls is Pldt else cls(result)
            data = source
            column = True
        name = _name(source_name) if name is None else name
        result = _pldt_date_objects(data, target, kind, unit, zone, policy, size, name or "", column)
        return result if cls is Pldt else cls(result)
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


def _date_expression(source, kind, *, tz=None, unit=None, ambiguous: _ExprAmbiguous="raise", nonexistent: _Nonexistent="raise"):
    entry = "Pldt.fromdate" if kind == "date" else "Pldt.fromdatetime"
    try:
        unit = _unit(unit, optional=True)
        target = _prepare_zone(tz)
        policy, mask, scalar = _timezone_policy(ambiguous, nonexistent, expression=True)
        data = policy.plugin_kwargs()
        ordered = data["ambiguous"] == "mask" or (data["ambiguous"] == "infer" and target is not None and target.fixed_seconds is None)
        kwargs = {"version": 1, "operation": kind, "unit": unit,
                  "target": None if target is None else target.plugin_kwargs(),
                  "policy": data, "mask_scalar": scalar}
        return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_dates",
                                        args=[source] if mask is None else [source, mask],
                                        kwargs=kwargs, is_elementwise=not ordered and mask is None)
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


def _real_pandas_source(data, zone):
    """Read special aware columns without pandas' key-based scalar rebuilding.

    Ordinary native columns never enter this path. Actual timezone.fromutc
    remains the source authority; nanoseconds and missing positions survive.
    """
    factor = {"s": 1_000_000_000, "ms": 1_000_000, "us": 1_000, "ns": 1}[data.unit]
    ticks = _base_array(data.asi8)
    if ticks.dtype != np.dtype("int64"):
        raise _own_error(TypeError("a pandas datetime source must expose signed int64 ticks"))
    epoch = None
    for tick in ticks:
        if tick == -9223372036854775808:
            yield None
            continue
        seconds, fraction = divmod(int(tick) * factor, 1_000_000_000)
        microsecond, nano = divmod(fraction, 1000)
        # Give the real source protocol the complete datetime precision before
        # converting. Restoring UTC fractions afterward loses fractional-offset
        # carries and can select the wrong local day near midnight.
        if epoch is None:
            epoch = _dt.datetime(1970, 1, 1, tzinfo=_dt.timezone.utc)
        utc = epoch + _dt.timedelta(seconds=seconds, microseconds=microsecond)
        local = utc.astimezone(zone)
        yield pd.Timestamp(year=local.year, month=local.month, day=local.day,
                           hour=local.hour, minute=local.minute, second=local.second,
                           microsecond=local.microsecond, nanosecond=nano, tzinfo=zone,
                           fold=1 if local.fold else 0)


def _part_source(value, clock, keep_zone):
    """Own one date/clock role without constructing an intermediate Pldt."""
    parameter = "time" if clock else "date"
    source_type = type(value)
    if issubclass(source_type, (Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame, pl.Expr) + _PD_TABLE):
        raise _own_error(TypeError("requires a scalar or one-dimensional date/clock collection"), parameter, value)
    column = False
    name = None
    if issubclass(source_type, _PD_COLUMN):
        name = getattr(value, "name", None)
        column = True
        if issubclass(source_type, (pd.Series, pd.Index)):
            value = value.array
            source_type = type(value)
        if issubclass(source_type, _PD_DATETIME_ARRAY):
            source_zone = _resolve_zone(value.tz)
            if source_zone is None or isinstance(source_zone, (timezone, ZoneInfo)):
                rule, offset = None, None
                if isinstance(source_zone, timezone):
                    delta = source_zone.utcoffset(None)
                    offset = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
                elif source_zone is not None:
                    rule = _prepare_source_zone(source_zone)
                if source_zone is None or offset is not None or rule is not None:
                    carrier = pl.Series("", _base_array(value.asi8))
                    return _pldt_parts_buffer(carrier, clock, _NUMPY_DATE_CODES[value.unit], 1,
                                              rule, offset, keep_zone), _name(name)
                if keep_zone:
                    # A real standard ZoneInfo can itself prove a constant
                    # source offset. Preserve it without trusting its key,
                    # including the metadata of empty/all-missing clocks.
                    fixed = source_zone.utcoffset(None) if type(source_zone) is ZoneInfo else None
                    if fixed is not None:
                        offset = (fixed.days * 86400 + fixed.seconds) * 1_000_000 + fixed.microseconds
                        if not -86_400_000_000 < offset < 86_400_000_000:
                            raise _own_error(ValueError("source UTC offset must be strictly within 24 hours"), parameter, value)
                        carrier = pl.Series("", _base_array(value.asi8))
                        return _pldt_parts_buffer(carrier, clock, _NUMPY_DATE_CODES[value.unit], 1,
                                                  None, offset, True), _name(name)
                    _prepare_zone(source_zone, parameter)
                value = _real_pandas_source(value, source_zone)
        arrow = _pandas_timestamp_column(value)
        if arrow is not None:
            value = arrow.rename(_name(name) or "")
        source_type = type(value)
    if issubclass(source_type, np.ndarray):
        value = _base_array(value)
        column = True
        if value.dtype.kind == "M":
            source, multiplier = np.datetime_data(value.dtype)
            if source not in _NUMPY_DATE_CODES:
                raise _own_error(ValueError("NumPy date unit must be years through nanoseconds"), parameter, value)
            carrier = pl.Series("", value.view(np.int64))
            return _pldt_parts_buffer(carrier, clock, _NUMPY_DATE_CODES[source], multiplier,
                                      None, None, keep_zone), None
        if value.dtype.kind in "iufb":
            if value.dtype.kind == "f" and value.dtype.type not in _NUMPY_FLOAT_TYPES:
                raise _own_error(TypeError("extended floating dtypes are not supported date/clock values"), parameter, value)
            value = pl.Series("", value.astype(np.float32) if value.dtype == np.dtype("float16") else value)
        source_type = type(value)
    if issubclass(source_type, pl.Series):
        value = _plain_series(value)
        name = value.name
        column = True
        if value.dtype.base_type() is pl.Time and clock:
            return _pldt_parts_time(value.to_physical()), _name(name)
        if value.dtype.base_type() is not pl.Object:
            return _pldt_parts_column(value, clock, keep_zone), _name(name)
    return _pldt_parts_objects(value, _resolve_zone, clock, column, keep_zone), _name(name)


@overload
def _combine_factory(cls: type[_PldtT], date: object, time: object, *, size: object=None, tz: object=None, unit: object=None, name: object=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
    ...
@overload
def _combine_factory(cls: type[pl.Series], date: object, time: object, *, size: object=None, tz: object=None, unit: object=None, name: object=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Series:
    ...
def _combine_factory(cls: type[_SeriesT], date, time, *, size=None, tz=None, unit=None, name=None,
                     ambiguous: _Ambiguous="raise", nonexistent: _Nonexistent="raise"):
    try:
        unit = _unit(unit, optional=True)
        size = None if size is None else _size(size, "Pldt.combine")
        name = _name(name)
        target = _prepare_zone(tz)
        policy, _, _ = _timezone_policy(ambiguous, nonexistent, expression=False)
        days, date_name = _part_source(date, False, False)
        clocks, clock_name = _part_source(time, True, target is None)
        name = name if name is not None else date_name if date_name is not None else clock_name or ""
        result = _pldt_combine(days, clocks, Pldt if cls is Pldt else pl.Series, _local_zone,
                                size, unit, target, policy, name)
        return result if cls is Pldt else cls(result)
    except Exception as error:
        _raise_argument_context(error, "Pldt.combine", "arguments", None)


def _combine_expression(source, time=None, *, tz=None, unit=None, ambiguous: _ExprAmbiguous="raise", nonexistent: _Nonexistent="raise"):
    try:
        unit = _unit(unit, optional=True)
        target = _prepare_zone(tz)
        policy, mask, mask_scalar = _timezone_policy(ambiguous, nonexistent, expression=True)
        args = [source]
        prepared = None
        if isinstance(time, pl.Expr):
            args.extend([time, time.to_physical()])
            clock_scalar = time.meta.is_scalar()
        else:
            clocks, _ = _part_source(time, True, target is None)
            values, zones, prepared = clocks.expression()
            clock_scalar = prepared["scalar"]
            args.append(pl.lit(values[0], dtype=pl.Int64) if clock_scalar else pl.lit(values))
            args.append(pl.lit(zones[0], dtype=pl.UInt32) if clock_scalar else pl.lit(zones))
        if mask is not None:
            args.append(mask)
        kwargs = {"version": 1, "unit": unit,
                  "target": None if target is None else target.plugin_kwargs(),
                  "policy": policy.plugin_kwargs(), "date_scalar": source.meta.is_scalar(),
                  "clock_scalar": clock_scalar, "mask_scalar": mask_scalar, "prepared": prepared}
        return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_combine",
                                        args=args, kwargs=kwargs, is_elementwise=False)
    except Exception as error:
        _raise_argument_context(error, "Pldt.combine", "arguments", None)


def _integer_operand(value, entry, parameter):
    """Prepare one scalar/positional integer role and own any literal buffer."""
    source_type = type(value)
    if issubclass(source_type, (Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame, pl.Expr) + _PD_TABLE):
        raise _own_error(TypeError("requires an integer scalar or one-dimensional integer collection"), parameter, value)
    column = False
    source_name = None
    if issubclass(source_type, _PD_COLUMN):
        source_name = _name(getattr(value, "name", None))
        column = True
    if issubclass(source_type, np.ndarray):
        value = _base_array(value)
        column = True
        if value.dtype.kind in "iufb":
            if value.dtype.kind == "f" and value.dtype.type not in _NUMPY_FLOAT_TYPES:
                raise _own_error(TypeError("extended floating dtypes are not integer components"), parameter, value)
            value = pl.Series("", value.astype(np.float32) if value.dtype == np.dtype("float16") else value)
        source_type = type(value)
    if issubclass(source_type, pl.Series):
        column = True
        value = _plain_series(value)
        if value.dtype.base_type() is not pl.Object:
            return _pldt_integer_column(value, entry, parameter), False
    source, scalar = _pldt_integer_objects(value, column, entry, parameter)
    return source.rename(source_name or ""), scalar


@overload
def _calendar_factory(cls: type[_PldtT], kind: object, components: object, *, size: object=None, tz: object=None, unit: object='us', name: object=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
    ...
@overload
def _calendar_factory(cls: type[pl.Series], kind: object, components: object, *, size: object=None, tz: object=None, unit: object='us', name: object=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Series:
    ...
def _calendar_factory(cls: type[_SeriesT], kind, components, *, size=None, tz=None, unit: object="us", name=None,
                      ambiguous: _Ambiguous="raise", nonexistent: _Nonexistent="raise"):
    entry = "Pldt." + {"ordinal": "fromordinal", "iso": "fromisocalendar", "doy": "fromdayofyear"}[kind]
    try:
        unit = _unit(unit)
        size = None if size is None else _size(size, entry)
        target = _prepare_zone(tz)
        name = _name(name)
        policy, _, _ = _timezone_policy(ambiguous, nonexistent, expression=False)
        labels = {"ordinal": ("ordinal",), "iso": ("year", "week", "weekday"), "doy": ("year", "doy")}[kind]
        prepared = [_integer_operand(value, entry, label) for value, label in zip(components, labels)]
        sources = [source for source, _ in prepared]
        scalars = [scalar for _, scalar in prepared]
        selected_name = name if name is not None else sources[0].name
        sources[0] = sources[0].rename(selected_name)
        result = _pldt_calendar(sources, scalars, Pldt if cls is Pldt else pl.Series, kind,
                                unit, target, policy, size)
        return result if cls is Pldt else cls(result)
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


def _calendar_expression(kind, components, *, tz=None, unit: object="us", ambiguous: _ExprAmbiguous="raise", nonexistent: _Nonexistent="raise"):
    entry = "Pldt." + {"ordinal": "fromordinal", "iso": "fromisocalendar", "doy": "fromdayofyear"}[kind]
    try:
        unit = _unit(unit)
        target = _prepare_zone(tz)
        policy, mask, mask_scalar = _timezone_policy(ambiguous, nonexistent, expression=True)
        labels = {"ordinal": ("ordinal",), "iso": ("year", "week", "weekday"), "doy": ("year", "doy")}[kind]
        args, scalars = [], []
        for value, label in zip(components, labels):
            if issubclass(type(value), pl.Expr):
                args.append(value)
                scalars.append(value.meta.is_scalar())
            else:
                source, scalar = _integer_operand(value, entry, label)
                args.append(pl.lit(source[0], dtype=pl.Int64) if scalar else pl.lit(source))
                scalars.append(scalar)
        options = policy.plugin_kwargs()
        kwargs = {"version": 1, "operation": kind, "unit": unit,
                  "target": None if target is None else target.plugin_kwargs(),
                  "policy": options, "scalars": scalars, "mask_scalar": mask_scalar}
        if mask is not None:
            args.append(mask)
        return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_calendar",
                                        args=args, kwargs=kwargs, is_elementwise=False)
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


@overload
def _as_unit(source: _PldtT, unit: object, round_ok: _Boolean, *, entry: str) -> _PldtT:
    ...
@overload
def _as_unit(source: pl.Series, unit: object, round_ok: _Boolean, *, entry: str) -> Pldt:
    ...
def _as_unit(source, unit, round_ok: _Boolean, *, entry: str):
    if source.dtype.base_type() not in (pl.Date, pl.Datetime):
        raise _own_error(TypeError("as_unit requires a Date/Datetime source"), "data", source)
    unit = _unit(unit)
    round_ok = _bool_option(round_ok, entry, "round_ok")
    target = type(source) if isinstance(source, Pldt) else Pldt
    if target is Pldt:
        return _pldt_native(source, Pldt, unit, False, round_ok, as_unit_entry=entry)
    return target(_pldt_native(source, pl.Series, unit, False, round_ok, as_unit_entry=entry))



def _timezone_policy(ambiguous: _ExprAmbiguous, nonexistent: _Nonexistent, *, expression):
    kind = type(ambiguous)
    if issubclass(kind, pl.Expr):
        if not expression:
            raise _own_error(TypeError("ambiguous Expr is only valid in an Expr call"), "ambiguous", ambiguous)
        mask = cast(pl.Expr, ambiguous)
        return _pldt_policies("raise", nonexistent, True), mask, mask.meta.is_scalar()
    if issubclass(kind, np.ndarray):
        column = cast(np.ndarray, ambiguous)
        if column.ndim != 1:
            raise _own_error(ValueError("ambiguous must be one-dimensional"), "ambiguous", ambiguous)
        if column.dtype.kind != "b":
            raise _own_error(TypeError("ambiguous array must have Boolean dtype"), "ambiguous", ambiguous)
        return _pldt_policies(ambiguous, nonexistent), None, False
    if isinstance(ambiguous, (pl.DataFrame, pl.LazyFrame, Mapping, set, frozenset) + _PD_TABLE):
        raise _own_error(TypeError("ambiguous must be one boolean policy or a one-dimensional boolean collection"), "ambiguous", ambiguous)
    if isinstance(ambiguous, pl.Series) and ambiguous.dtype != pl.Boolean:
        raise _own_error(TypeError("ambiguous Series must have Boolean dtype"), "ambiguous", ambiguous)
    return _pldt_policies(ambiguous, nonexistent), None, False


@overload
def _tz_eager(source: _PldtT, operation: object, tz: object, base_tz: object=None, naive: _Boolean=False, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
    ...
@overload
def _tz_eager(source: pl.Series, operation: object, tz: object, base_tz: object=None, naive: _Boolean=False, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:
    ...
def _tz_eager(source, operation, tz, base_tz=None, naive: _Boolean=False, ambiguous: _Ambiguous="raise", nonexistent: _Nonexistent="raise"):
    entry = "Pldt." + {"localize": "tz_localize", "convert": "tz_convert", "switch": "tz_switch", "astimezone": "astimezone"}[operation]
    try:
        naive = _bool_option(naive, entry, "naive")
        policy, _, _ = _timezone_policy(ambiguous, nonexistent, expression=False)
        receiver = _plain_series(source)
        dtype = receiver.dtype
        if dtype.base_type() not in (pl.Date, pl.Datetime):
            raise _own_error(TypeError("source must be a Date/Datetime column"), "data", source)
        source_aware = dtype.base_type() == pl.Datetime and cast(pl.Datetime, dtype).time_zone is not None
        target = _prepare_zone(_local_zone() if operation == "astimezone" and tz is None else tz,
                               "targ_tz" if operation == "switch" else "tz")
        base = None
        if operation == "astimezone" and not source_aware:
            base = target if tz is None else _prepare_zone(_local_zone())
        elif operation == "switch" and tz is not None and not source_aware and base_tz is not None:
            base = _prepare_zone(base_tz, "base_tz")
        cls = type(source) if isinstance(source, Pldt) else Pldt
        if cls is Pldt:
            return _pldt_timezone(receiver, Pldt, operation, target, base, policy, naive)
        return cls(_pldt_timezone(receiver, pl.Series, operation, target, base, policy, naive))
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


def _tz_expr(source, operation, tz, base_tz=None, naive: _Boolean=False, ambiguous: _ExprAmbiguous="raise", nonexistent: _Nonexistent="raise"):
    entry = "Pldt." + {"localize": "tz_localize", "convert": "tz_convert", "switch": "tz_switch", "astimezone": "astimezone"}[operation]
    try:
        naive = _bool_option(naive, entry, "naive")
        policy, mask, scalar = _timezone_policy(ambiguous, nonexistent, expression=True)
        target = _prepare_zone(_local_zone() if operation == "astimezone" and tz is None else tz,
                               "targ_tz" if operation == "switch" else "tz")
        # Expr has no input schema yet. Static required fallbacks are frozen now;
        # actual aware execution never reinterprets the source or uses base rules.
        base = None
        if operation == "astimezone":
            base = target if tz is None else _prepare_zone(_local_zone())
        elif operation == "switch" and tz is not None and base_tz is not None:
            base = _prepare_zone(base_tz, "base_tz")
        policy_data = policy.plugin_kwargs()
        kwargs = {"version": 1, "operation": operation,
                  "target": None if target is None else target.plugin_kwargs(),
                  "base": None if base is None else base.plugin_kwargs(),
                  "policy": policy_data, "naive": naive, "mask_scalar": scalar}
        ordered = policy_data["ambiguous"] in ("infer", "mask")
        if policy_data["ambiguous"] == "infer" and operation == "localize" and target is not None and target.fixed_seconds is not None:
            ordered = False
        return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_timezone",
                                        args=[source] if mask is None else [source, mask],
                                        kwargs=kwargs, is_elementwise=not ordered and mask is None)
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)







_UNCHANGED_ZONE = object()
_FIELD_NAMES = ("year", "month", "day", "hour", "minute", "second", "microsecond", "nanosecond")
_INCREMENT_NAMES = ("years", "quarters", "months", "weeks", "days", "hours", "minutes", "seconds", "milliseconds", "microseconds", "nanoseconds")
_FIELD_RANGES: tuple[tuple[int | None, int | None], ...] = ((None, None), (1, 12), (1, 31), (0, 23), (0, 59), (0, 59), (0, 999999), (0, 999))


def _component(value, entry, parameter, optional, names, low, high) -> tuple[pl.Series, bool]:
    """Read a modification parameter once, preserving None and owning literals."""
    source_type = type(value)
    if issubclass(source_type, (Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame, pl.Expr) + _PD_TABLE):
        raise _own_error(TypeError("requires a scalar or one-dimensional field collection"), parameter, value)
    column = issubclass(source_type, _PD_COLUMN)
    if issubclass(source_type, np.ndarray):
        value = _base_array(value)
        column = True
        if value.dtype.kind in "iu":
            value = pl.Series(parameter, value)
        elif value.dtype.kind in "US" and names:
            value = pl.Series(parameter, value)
        elif value.dtype.kind != "O":
            raise _own_error(TypeError("requires integer fields, not Boolean or floating dtype"), parameter, value)
        source_type = type(value)
    if issubclass(source_type, _PD_COLUMN):
        kind = getattr(value.dtype, "kind", None)
        if kind not in ("i", "u", "O", "U", "T"):
            raise _own_error(TypeError("requires integer fields or supported selector names"), parameter, value)
    if issubclass(source_type, pl.Series):
        value = _plain_series(value)
        column = True
        if value.dtype.base_type() is not pl.Object:
            return _pldt_component_column(value, (optional, names, low, high), entry, parameter), False
    return _pldt_component_objects(value, column, (optional, names, low, high), entry, parameter)


def _transform_roles(kind) -> list[tuple[str, bool, int, int | None, int | None]]:
    if kind in ("replace", "adjust"):
        return [(label, True, 0, *bounds) for label, bounds in zip(_FIELD_NAMES, _FIELD_RANGES)]
    if kind in ("add", "sub"):
        return [(label, False, 0, None, None) for label in _INCREMENT_NAMES]
    required = ("offset", False, 0, None, None)
    if kind in ("year", "quarter"):
        return [required, ("month", True, 1 if kind == "year" else 0, 1, 12 if kind == "year" else 3), ("day", True, 0, 1, 31)]
    if kind == "month":
        return [required, ("day", True, 0, 1, 31)]
    if kind == "weekday":
        return [required, ("weekday", True, 2, 0, 6)]
    return [required]


@overload
def _date_operation(owner: _PldtT, kind: object, components: object, method: object, *, tzinfo: object=_UNCHANGED_ZONE, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> _PldtT:
    ...
@overload
def _date_operation(owner: _SeriesNamespace, kind: object, components: object, method: object, *, tzinfo: object=_UNCHANGED_ZONE, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:
    ...
@overload
def _date_operation(owner: _ExprNamespace, kind: object, components: object, method: object, *, tzinfo: object=_UNCHANGED_ZONE, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:
    ...
@overload
def _date_operation(owner: object, kind: object, components: object, method: object, *, tzinfo: object=_UNCHANGED_ZONE, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt | pl.Expr:
    ...
def _date_operation(owner, kind, components, method, *, tzinfo=_UNCHANGED_ZONE,
                    ambiguous: _ExprAmbiguous="raise", nonexistent: _Nonexistent="raise"):
    """Prepare roles once and enter one native Series/Expr calendar kernel."""
    entry = "Pldt." + method
    try:
        expression = isinstance(owner, _ExprNamespace)
        source = owner._expr if expression else _plain_series(owner._series if isinstance(owner, _SeriesNamespace) else owner)
        replace_zone = tzinfo is not _UNCHANGED_ZONE
        target = _prepare_zone(tzinfo, "tzinfo") if replace_zone else None
        if kind == "replace":
            policy, mask, mask_scalar = _timezone_policy(ambiguous, nonexistent, expression=expression)
        else:
            policy, mask, mask_scalar = None, None, False
        args, scalars = [], []
        has_expr_component = False
        for value, role in zip(components, _transform_roles(kind)):
            if issubclass(type(value), pl.Expr):
                has_expr_component = True
                if not expression:
                    raise _own_error(TypeError("Expr fields require the Expr namespace"), role[0], value)
                argument, scalar = value, value.meta.is_scalar()
            else:
                argument, scalar = _component(value, entry, *role)
                if expression:
                    argument = pl.lit(argument[0], dtype=pl.Int64) if scalar else pl.lit(argument)
            args.append(argument)
            scalars.append(scalar)
        if expression:
            options = {"version": 1, "kind": kind, "entry": entry, "scalars": scalars,
                       "target": None if target is None else target.plugin_kwargs(),
                       "replace_zone": replace_zone, "policy": None if policy is None else policy.plugin_kwargs(),
                       "mask_scalar": mask_scalar}
            if mask is not None:
                args.append(mask)
            # Only basic columns prove row-wise input without a schema.
            # Selectors and composed sources retain the general plugin path.
            return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_transform",
                                            args=[source, *args], kwargs=options,
                                            is_elementwise=all(scalars) and not has_expr_component
                                            and mask is None and (options["policy"] is None or options["policy"]["ambiguous"] not in ("infer", "mask"))
                                            and cast(pl.Expr, source).meta.is_column())
        cls = type(owner._series) if isinstance(owner, _SeriesNamespace) and isinstance(owner._series, Pldt) else type(owner) if isinstance(owner, Pldt) else Pldt
        result = _pldt_transform(cast(pl.Series, source), args, scalars, Pldt if cls is Pldt else pl.Series,
                                kind, entry, target, replace_zone, policy)
        return result if cls is Pldt else cls(result)
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


def _prepare_arithmetic(other, entry, subtract, reflected=False, named=False):
    """Read real temporal metadata without extracting Python date scalars."""
    source_type = type(other)
    if issubclass(source_type, (pl.Expr, Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame) + _PD_TABLE):
        if named:
            raise _own_error(TypeError("requires actual Delta values or a one-dimensional Delta collection; dynamic Expr operands are unsupported"), "delta", other)
        return None
    column = False
    if issubclass(source_type, _PD_COLUMN):
        column = True
        array = other.array if issubclass(source_type, (pd.Series, pd.Index)) else other
        array_type = type(array)
        if issubclass(array_type, (_PD_DATETIME_ARRAY, _PD_TIMEDELTA_ARRAY)):
            storage = "M" if issubclass(array_type, _PD_DATETIME_ARRAY) else "m"
            if named:
                raise _own_error(TypeError("requires actual Delta values"), "delta", other)
            # The actual cached class test proves the structural storage API.
            array = cast("_PandasTicks", array)
            unit = array.unit
            data = _base_array(array.asi8)
            return _pldt_operand_ticks(pl.Series("", data), storage, _NUMPY_DATE_CODES[unit], 1,
                                       storage == "M" and cast("_PandasDateTicks", array).tz is not None, True)
        arrow = _pandas_timestamp_column(array)
        other = array if arrow is None else arrow
        source_type = type(other)
    if issubclass(source_type, np.ndarray):
        other = _base_array(other)
        column = True
        if other.dtype.kind in "Mm":
            if named:
                raise _own_error(TypeError("requires actual Delta values"), "delta", other)
            unit, multiplier = np.datetime_data(other.dtype)
            if unit not in _NUMPY_DATE_CODES:
                raise _own_error(ValueError("temporal units must be years through nanoseconds"), "other", other)
            return _pldt_operand_ticks(pl.Series("", other.view(np.int64)), other.dtype.kind,
                                       _NUMPY_DATE_CODES[unit], multiplier, False, True)
        if other.dtype.kind != "O":
            if named:
                raise _own_error(TypeError("requires actual Delta values"), "delta", other)
            return None
        source_type = type(other)
    if issubclass(source_type, pl.Series):
        other = _plain_series(other)
        column = True
        if other.dtype.base_type() in (pl.Date, pl.Datetime, pl.Duration):
            if named:
                raise _own_error(TypeError("requires actual Delta values"), "delta", other)
            return _pldt_operand_column(other)
        if other.dtype.base_type() is not pl.Object:
            if other.dtype.base_type() is pl.Null:
                other = [None] * len(other)
            else:
                raise _own_error(TypeError("arithmetic columns require actual date/duration/Delta values"), "other", other)
    return _pldt_operand_objects(other, column, subtract, reflected, named, entry)


def _callback_arithmetic_result(result, entry):
    """Read only already-supported temporal values; never parse callback text."""
    return _prepare_arithmetic(result, entry, True)


def _binary_eager(owner, other, subtract=False, reflected=False, named=False):
    """Own arithmetic dispatch; external scalar negotiation remains Python's."""
    method = "sub_delta" if named and subtract else "add_delta" if named else "__sub__" if subtract else "__radd__" if reflected else "__add__"
    entry = "Pldt." + method
    actual = owner._series if isinstance(owner, _SeriesNamespace) else owner
    source = _plain_series(actual)
    try:
        operand = _prepare_arithmetic(other, entry, subtract, reflected, named)
        if operand is None:
            if named:
                raise _own_error(TypeError("requires actual Delta values or a strict equal-length Delta collection"), "delta", other)
            return NotImplemented
        if named and operand.kind != 1:
            raise _own_error(TypeError("requires actual Delta values"), "delta", other)
        result_only = False
        if operand.scalar_dynamic:
            if not named:
                return NotImplemented
            result = _pldt_scalar_callback(operand, actual)
            if result is NotImplemented:
                raise TypeError("the actual arithmetic callback returned NotImplemented")
            operand = _prepare_arithmetic(result, entry, True)
            if operand is None or operand.kind != 3 or operand.dynamic:
                raise TypeError("a named arithmetic callback must return an equal-length date collection")
            result_only = True
        if operand.kind == 3 and not subtract and not result_only:
            return NotImplemented
        cls = type(actual) if isinstance(actual, Pldt) else Pldt
        output = pl.Series if operand.kind == 3 and not result_only else Pldt if cls is Pldt else pl.Series
        result = _pldt_binary(source, operand, output, subtract, entry, result_only, pl.Series, _callback_arithmetic_result)
        return result if output is Pldt or operand.kind == 3 and not result_only else cls(result)
    except Exception as error:
        _raise_argument_context(error, entry, "other", other)


def _delta_expression(source, delta, subtract):
    """Snapshot concrete plain Delta fields; never execute Python in a worker."""
    entry = "Pldt.sub_delta" if subtract else "Pldt.add_delta"
    try:
        operand = _prepare_arithmetic(delta, entry, subtract, named=True)
        if operand is None or operand.kind != 1:
            raise _own_error(TypeError("requires actual Delta values"), "delta", delta)
        if operand.dynamic:
            raise _own_error(TypeError("dynamic Python arithmetic is not supported by native Expr"), "delta", delta)
        args = [source] if operand.scalar else [source, pl.lit(operand.plugin_column())]
        return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_delta", args=args,
                                        kwargs={"version": 1, "prepared": operand.plugin_data() if operand.scalar else b"",
                                                "subtract": subtract, "entry": entry, "scalar": operand.scalar},
                                        is_elementwise=operand.scalar and cast(pl.Expr, source).meta.is_column())
    except Exception as error:
        _raise_argument_context(error, entry, "delta", delta)


@overload
def _period_operation(owner: _PldtT, kind: object, token: object, value: object, mode: object, query: Literal[False], method: object) -> _PldtT:
    ...
@overload
def _period_operation(owner: _SeriesNamespace, kind: object, token: object, value: object, mode: object, query: Literal[False], method: object) -> Pldt:
    ...
@overload
def _period_operation(owner: _ExprNamespace, kind: object, token: object, value: object, mode: object, query: bool, method: object) -> pl.Expr:
    ...
@overload
def _period_operation(owner: object, kind: object, token: object, value: object, mode: object, query: Literal[False], method: object) -> Pldt | pl.Expr:
    ...
@overload
def _period_operation(owner: object, kind: object, token: object, value: object, mode: object, query: Literal[True], method: object) -> pl.Series | pl.Expr:
    ...
def _period_operation(owner, kind, token, value, mode, query, method):
    """Prepare a static period/grid once and enter its shared native loop."""
    entry = "Pldt." + method
    try:
        if kind in ("boundary", "snap") and not isinstance(token, str):
            raise _own_error(TypeError("requires a period string or a supported saved name"), "unit", token)
        if kind == "fsp":
            value = _integer_arg(value, entry, "precision")
        elif kind == "round":
            if pd is not None and issubclass(type(value), pd.DateOffset):
                plan, _, delegated = _pandas_frequency(value)  # pyright: ignore[reportOptionalCall] -- TY024; see tests/typing/pyright_exceptions.json.
                if delegated or plan is None:
                    raise _own_error(ValueError("requires a positive fixed frequency"), "freq", value)
            else:
                plan = _pldt_frequency(value)
            step = None if plan is None else plan.rounding_step
            if step is None or step <= 0:
                raise _own_error(ValueError("requires a positive fixed frequency such as '15min', 'h' or 'D'"), "freq", value)
            value = step
        context = _pldt_period_prepare(kind, token, value, mode, query, entry)
        if isinstance(owner, _ExprNamespace):
            return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_period", args=[owner._expr],
                                            kwargs={"prepared": context.plugin_data()}, is_elementwise=True)
        actual = owner._series if isinstance(owner, _SeriesNamespace) else owner
        cls = type(actual) if isinstance(actual, Pldt) else Pldt
        target = pl.Series if query or cls is not Pldt else Pldt
        result = _pldt_period(_plain_series(actual), context, target)
        return result if query or cls is Pldt else cls(result)
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


_NO_QUERY_TARGET = object()


def _diff_target(value, count=None) -> tuple[pl.Series, bool, int, tuple[int, int] | None, bool]:
    """Prepare exact date/seconds coordinates, with native dtype metadata."""
    source_type = type(value)
    if issubclass(source_type, (Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame) + _PD_TABLE):
        raise _own_error(TypeError("requires a scalar or a one-dimensional target collection"), "dtobj", value)
    column = issubclass(source_type, _PD_COLUMN)
    if column and getattr(value.dtype, "kind", None) == "M":
        array = value.array if issubclass(source_type, (pd.Series, pd.Index)) else value
        arrow = _pandas_timestamp_column(array)
        if arrow is not None:
            return arrow, False, 0, None, False
        unit = array.unit
        if unit not in _NUMPY_DATE_CODES:
            raise _own_error(ValueError("unsupported datetime target unit"), "dtobj", value)
        return pl.Series("", _base_array(array.asi8, own=True)), False, 1, (_NUMPY_DATE_CODES[unit], 1), getattr(value.dtype, "tz", None) is not None
    if issubclass(source_type, np.ndarray):
        value = _base_array(value, own=True)
        column = True
        if value.dtype.kind == "M":
            unit, multiplier = np.datetime_data(value.dtype)
            if unit not in _NUMPY_DATE_CODES:
                raise _own_error(ValueError("unsupported NumPy date target unit"), "dtobj", value)
            return pl.Series("", value.view(np.int64)), False, 1, (_NUMPY_DATE_CODES[unit], multiplier), False
        if value.dtype.kind == "f" and value.dtype.type not in _NUMPY_FLOAT_TYPES:
            raise _own_error(TypeError("extended floating targets are not supported"), "dtobj", value)
        if value.dtype.kind in "iufbU":
            value = pl.Series("", value.astype(np.float32) if value.dtype == np.dtype("float16") else value)
        source_type = type(value)
    if issubclass(source_type, pl.Series):
        column = True
        value = _plain_series(value)
        if value.dtype.base_type() is not pl.Object:
            return value, False, 0, None, False
    target, scalar = _pldt_diff_objects(value, column, count)
    return target, scalar, 2, None, False


def _boundary_difference(owner, dtobj, unit, absolute, inclusive):
    """Count boundaries directly; targets never become an intermediate Pldt."""
    entry = "Pldt.pldt.diff"
    try:
        absolute = _bool_option(absolute, entry, "absolute")
        for name, value in (("unit", unit), ("inclusive", inclusive)):
            if not isinstance(value, str):
                raise _own_error(TypeError("must be a string"), name, value)
        if type(unit) is not str:
            unit = str.__str__(unit)
        if type(inclusive) is not str:
            inclusive = str.__str__(inclusive)
        if unit not in ("Y", "Q", "M", "W", "D", "h", "m", "min", "s", "ms", "us", "ns"):
            raise _own_error(ValueError("unit must be Y/Q/M/W/D/h/m/min/s/ms/us/ns"), "unit", unit)
        if inclusive not in ("one", "both", "neither"):
            raise _own_error(ValueError("must be 'one', 'both' or 'neither'"), "inclusive", inclusive)
        expression = isinstance(owner, _ExprNamespace)
        source = owner._expr if expression else _plain_series(owner._series if isinstance(owner, _SeriesNamespace) else owner)
        if expression and issubclass(type(dtobj), pl.Expr):
            target, scalar, storage, numpy, aware = dtobj, dtobj.meta.is_scalar(), 0, None, False
        else:
            target, scalar, storage, numpy, aware = _diff_target(dtobj, None if expression else source.len())
            if expression:
                target = pl.lit(target[0], dtype=pl.Binary) if scalar else pl.lit(target)
        if expression:
            return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_diff",
                                            args=[owner._expr, target], kwargs={"version": 1, "unit": unit,
                                                "absolute": absolute, "inclusive": inclusive, "scalar": scalar,
                                                "storage": storage, "numpy": numpy, "aware": aware},
                                            is_elementwise=False)
        return _pldt_diff(cast(pl.Series, source), cast(pl.Series, target), unit, absolute, inclusive, scalar, storage, numpy, aware)
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


def _query_operation(owner, code, method, value=_NO_QUERY_TARGET, names=0, parameter=None):
    """Prepare a scalar/strict positional query, emitting only its result."""
    entry = "Pldt." + method
    try:
        expression = isinstance(owner, _ExprNamespace)
        source = owner._expr if expression else _plain_series(owner._series if isinstance(owner, _SeriesNamespace) else owner)
        target = None
        scalar = False
        if value is not _NO_QUERY_TARGET:
            if expression and issubclass(type(value), pl.Expr):
                target = cast(pl.Expr, value)
                scalar = target.meta.is_scalar()
            else:
                target, scalar = _component(value, entry, parameter, False, names, None, None)
                if expression:
                    target = pl.lit(target[0], dtype=pl.Int64) if scalar else pl.lit(target)
        reference = _pldt_query_clock() if code in (107, 108) and (expression or cast(pl.Series, source).len() != cast(pl.Series, source).null_count()) else None
        if expression:
            return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_query",
                                            args=[source] if target is None else [source, target],
                                            kwargs={"version": 1, "code": code, "entry": entry,
                                                    "scalar": scalar, "reference": reference},
                                            is_elementwise=target is None)
        result = _pldt_query(cast(pl.Series, source), code, entry, cast("pl.Series | None", target), scalar, reference)
        return result.struct.unnest() if code in (202, 203) else result
    except Exception as error:
        _raise_argument_context(error, entry, parameter or "arguments", None if value is _NO_QUERY_TARGET else value)


def _output_operation(owner, code, method, utc: _Boolean=False, sep="T", timespec="auto", locale=None):
    """Prepare one native output plan, preserving a plain result's role."""
    entry = "Pldt." + method
    try:
        context = _pldt_output_prepare(code, utc, sep, timespec, locale, entry)
        if isinstance(owner, _ExprNamespace):
            return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_output",
                                            args=[owner._expr], kwargs={"prepared": context.plugin_data()},
                                            is_elementwise=True)
        source = _plain_series(owner._series if isinstance(owner, _SeriesNamespace) else owner)
        return _pldt_output(source, context, pl.Series)
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


def _python_output(owner, clock=False):
    entry = "Pldt.timetz" if clock else "Pldt.datetime"
    try:
        source = _plain_series(owner._series if isinstance(owner, _SeriesNamespace) else owner)
        key = cast(pl.Datetime, source.dtype).time_zone if source.dtype.base_type() is pl.Datetime else None
        zone = _resolve_zone(key) if key is not None else None
        values = _pldt_python_output(source, Pydt, zone, clock)
        result = np.empty(len(values), dtype=object)
        result[:] = values
        return result
    except Exception as error:
        _raise_argument_context(error, entry, "data", None)


class _PythonOutputMethods:
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
        On a native Polars Series

        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', [1234, None], dtype=pl.Datetime('ns'))
        >>> dates = source.pldt.datetime()
        >>> print(type(dates[0]).__name__, dates[0].isoformat(), dates[1])
        Pydt 1970-01-01T00:00:00.000001 None

        On a Pldt

        >>> from rstimes import Pldt
        >>> type(Pldt([0], unit="ns").datetime()[0]).__name__
        'Pydt'
        """
        return _python_output(self)

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
        return _python_output(self, True)


def _strftime_operation(owner, format):
    entry = "Pldt.strftime"
    try:
        context = _strftime_prepare(format)
        if isinstance(owner, _ExprNamespace):
            if not context.native():
                raise _own_error(ValueError("system-locale/platform formats require eager data; use eager strftime or native .dt.strftime"), "format", format)
            return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_strftime",
                                            args=[owner._expr], kwargs={"prepared": context.plugin_data()},
                                            is_elementwise=True)
        source = _plain_series(owner._series if isinstance(owner, _SeriesNamespace) else owner)
        zone = None
        if not context.native() and source.dtype.base_type() is pl.Datetime and cast(pl.Datetime, source.dtype).time_zone is not None:
            zone = _resolve_zone(cast(pl.Datetime, source.dtype).time_zone)
        return _pldt_strftime(source, context, zone, pl.Series)
    except Exception as error:
        _raise_argument_context(error, entry, "format", format)


class _OutputMethods:
    """Native numerical, date, clock and text outputs without Python row objects."""
    def toseconds(self, utc: _Boolean=False) -> pl.Series | pl.Expr:
        """Return Float64 seconds in local coordinates, or UTC when requested.

        Parameters
        ----------
        utc : bool or numpy.bool_
            Use UTC coordinates when True; otherwise use local clock coordinates. A naive datetime remains
            timezone-naive.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        On a native Polars Series

        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', [0, None], dtype=pl.Datetime('us', 'Asia/Shanghai'))
        >>> dates = source.pldt.toseconds()
        >>> print(dates.to_list())
        [28800.0, None]

        In a Polars query

        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', [0, None], dtype=pl.Datetime('us', 'Asia/Shanghai'))])
        >>> expr = pl.col('event').pldt.toseconds()
        >>> dates = frame.select(expr)['event']
        >>> print(dates.to_list())
        [28800.0, None]

        On a Pldt

        >>> from rstimes import Pldt
        >>> x = Pldt(["1970-01-01 08:00:00"], tz="Asia/Shanghai", unit="us")
        >>> x.toseconds().to_list()
        [28800.0]
        >>> x.toseconds(utc=True).to_list()
        [0.0]
        """
        return _output_operation(self, 0, "toseconds", utc=utc)

    def tomicroseconds(self, utc: _Boolean=False) -> pl.Series | pl.Expr:
        """Return Int64 microseconds, flooring only at this explicit output.

        Parameters
        ----------
        utc : bool or numpy.bool_
            Use UTC coordinates when True; otherwise use local clock coordinates. A naive datetime remains
            timezone-naive.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        On a native Polars Series

        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', [-1500, None], dtype=pl.Datetime('ns'))
        >>> dates = source.pldt.tomicroseconds()
        >>> print(dates.to_list())
        [-2, None]

        In a Polars query

        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', [-1500, None], dtype=pl.Datetime('ns'))])
        >>> expr = pl.col('event').pldt.tomicroseconds()
        >>> dates = frame.select(expr)['event']
        >>> print(dates.to_list())
        [-2, None]

        On a Pldt

        >>> from rstimes import Pldt
        >>> Pldt(["1970-01-01 00:00:00.000001"], unit="ns").tomicroseconds().to_list()
        [1]
        """
        return _output_operation(self, 1, "tomicroseconds", utc=utc)

    def toordinal(self) -> pl.Series | pl.Expr:
        """Return Int64 proleptic Gregorian day ordinals; missing stays null.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _output_operation(self, 2, "toordinal")

    def timestamp(self) -> pl.Series | pl.Expr:
        """Return Float64 UTC seconds; naive dates use the process local zone.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        On a native Polars Series

        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', [0, None], dtype=pl.Datetime('us', 'Asia/Shanghai'))
        >>> dates = source.pldt.timestamp()
        >>> print(dates.to_list())
        [0.0, None]

        In a Polars query

        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', [0, None], dtype=pl.Datetime('us', 'Asia/Shanghai'))])
        >>> expr = pl.col('event').pldt.timestamp()
        >>> dates = frame.select(expr)['event']
        >>> print(dates.to_list())
        [0.0, None]

        On a Pldt

        >>> from rstimes import Pldt
        >>> Pldt(["1970-01-01 08:00:00"], tz="Asia/Shanghai").timestamp().to_list()
        [0.0]
        """
        return _output_operation(self, 3, "timestamp")

    @property
    def values_naive(self) -> pl.Series | pl.Expr:
        """Return a plain native Datetime column of local wall coordinates.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _output_operation(self, 4, "values_naive")

    @property
    def date(self) -> pl.Series | pl.Expr:
        """Return a native Date column, checked against its signed32-day range.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _output_operation(self, 5, "date")

    @property
    def time(self) -> pl.Series | pl.Expr:
        """Return a native Time column retaining the full time-of-day nanoseconds.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _output_operation(self, 6, "time")

    def isoformat(self, sep: str='T', timespec: str='auto') -> pl.Series | pl.Expr:
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
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _output_operation(self, 10, "isoformat", sep=sep, timespec=timespec)

    def strftime(self, format: str) -> pl.Series | pl.Expr:
        """Return strings using native numeric/fraction fields or an eager system adapter.

        Parameters
        ----------
        format : str
            Shared strftime format. %f emits 9 digits for ns and 6 for ms/us; %.1f through %.9f emit a dot
            plus that many truncated/padded digits, and %.0f is empty. System-locale/platform directives
            are eager-only; numeric directives remain native in Expr.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        On a native Polars Series

        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', [123_456_789, None], dtype=pl.Datetime('ns'))
        >>> dates = source.pldt.strftime('%f|%.3f|%.0f')
        >>> print(dates.to_list())
        ['123456789|.123|', None]

        In a Polars query

        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', [123_456_789, None], dtype=pl.Datetime('ns'))])
        >>> expr = pl.col('event').pldt.strftime('%f|%.3f|%.0f')
        >>> dates = frame.select(expr)['event']
        >>> print(dates.to_list())
        ['123456789|.123|', None]

        On a Pldt

        >>> from rstimes import Pldt
        >>> Pldt([123456789], unit="ns").strftime("%f|%.3f|%.0f").to_list()
        ['123456789|.123|']
        """
        return _strftime_operation(self, format)

    def ctime(self) -> pl.Series | pl.Expr:
        """Return English ctime strings, independent of the process locale.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _output_operation(self, 11, "ctime")

    def month_name(self, locale: str | None=None) -> pl.Series | pl.Expr:
        """Return compiled CLDR month names; the default language is English.

        Parameters
        ----------
        locale : str or None
            Supported CLDR locale such as en_US or zh_CN; None uses English. This does not change parser
            Configs.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _output_operation(self, 12, "month_name", locale=locale)

    def weekday_name(self, locale: str | None=None) -> pl.Series | pl.Expr:
        """Return compiled CLDR weekday names; the default language is English.

        Parameters
        ----------
        locale : str or None
            Supported CLDR locale such as en_US or zh_CN; None uses English. This does not change parser
            Configs.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _output_operation(self, 13, "weekday_name", locale=locale)

    def tzname(self) -> pl.Series | pl.Expr:
        """Return the native zone abbreviation at each instant, or null if naive.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _output_operation(self, 14, "tzname")


class _QueryMethods:
    """Direct nullable Int64/Boolean queries over actual local date fields."""
    @property
    def year(self) -> pl.Series | pl.Expr:
        """Signed calendar year as a nullable Int64 column.

        Returns
        -------
        pl.Series | pl.Expr
            The signed calendar year as a nullable Int64 Series.
            On Expr.pldt, the expression produces that column in select or collect.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 20, "year")

    @property
    def month(self) -> pl.Series | pl.Expr:
        """One-based month as a nullable Int64 column.

        Returns
        -------
        pl.Series | pl.Expr
            The month number (1 through 12) as a nullable Int64 Series.
            On Expr.pldt, the expression produces that column in select or collect.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 21, "month")

    @property
    def day(self) -> pl.Series | pl.Expr:
        """One-based day as a nullable Int64 column.

        Returns
        -------
        pl.Series | pl.Expr
            The day of the month as a nullable Int64 Series.
            On Expr.pldt, the expression produces that column in select or collect.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 22, "day")

    @property
    def hour(self) -> pl.Series | pl.Expr:
        """Hour within the local day as nullable Int64.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 23, "hour")

    @property
    def minute(self) -> pl.Series | pl.Expr:
        """Minute within the hour as nullable Int64.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 24, "minute")

    @property
    def second(self) -> pl.Series | pl.Expr:
        """Second within the minute as nullable Int64.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 25, "second")

    @property
    def microsecond(self) -> pl.Series | pl.Expr:
        """Microsecond within the second as nullable Int64.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 26, "microsecond")

    @property
    def nanosecond(self) -> pl.Series | pl.Expr:
        """Additional nanosecond tail, 0 through 999, as nullable Int64.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 27, "nanosecond")

    @property
    def weekday(self) -> pl.Series | pl.Expr:
        """Weekday with Monday 0, as nullable Int64.

        Returns
        -------
        pl.Series | pl.Expr
            The weekday as a nullable Int64 Series, Monday=0 through Sunday=6.
            On Expr.pldt, the expression produces that column in select or collect.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 28, "weekday")

    @property
    def day_of_year(self) -> pl.Series | pl.Expr:
        """One-based day within the local calendar year.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 29, "day_of_year")

    @property
    def days_in_month(self) -> pl.Series | pl.Expr:
        """Number of days in the local calendar month.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 30, "days_in_month")

    @property
    def quarter(self) -> pl.Series | pl.Expr:
        """One-based calendar quarter as nullable Int64.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 31, "quarter")

    @property
    def millisecond(self) -> pl.Series | pl.Expr:
        """Millisecond within the second, from 0 through 999.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 10, "millisecond")

    @property
    def is_leap_year(self) -> pl.Series | pl.Expr:
        """Whether the local year is leap; source null is False.

        Returns
        -------
        pl.Series | pl.Expr
            A Boolean Series. A null source date gives False.
            On Expr.pldt, the expression produces that column in select or collect.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 109, "is_leap_year")

    def isoyear(self) -> pl.Series | pl.Expr:
        """Signed ISO week year, independently of UInt32 table capacity.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 0, "isoyear")

    def isoweek(self) -> pl.Series | pl.Expr:
        """One-based ISO week number.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 1, "isoweek")

    def isoweekday(self) -> pl.Series | pl.Expr:
        """ISO weekday with Monday 1.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 2, "isoweekday")

    def days_in_year(self) -> pl.Series | pl.Expr:
        """Number of days in the local calendar year.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 3, "days_in_year")

    def days_bf_year(self) -> pl.Series | pl.Expr:
        """Days before this calendar year, relative to 0001-01-01.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 4, "days_bf_year")

    def days_in_quarter(self) -> pl.Series | pl.Expr:
        """Number of calendar days in this quarter.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 5, "days_in_quarter")

    def days_bf_quarter(self) -> pl.Series | pl.Expr:
        """Days in this year before the current quarter.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 6, "days_bf_quarter")

    def day_of_quarter(self) -> pl.Series | pl.Expr:
        """One-based day in this calendar quarter.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 7, "day_of_quarter")

    def days_bf_month(self) -> pl.Series | pl.Expr:
        """Days in this year before the current month.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 8, "days_bf_month")

    def day_of_month(self) -> pl.Series | pl.Expr:
        """One-based local day of month.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 9, "day_of_month")

    def is_year(self, year: _ExprIntegerInput) -> pl.Series | pl.Expr:
        """Match scalar or equal-length integer year targets.

        Parameters
        ----------
        year : integer or one-dimensional integer collection or polars.Expr
            An integer year or a same-length integer column paired by position. A valid
            integer outside the matching range yields False. Strings, booleans and missing targets are invalid.
            Use an integer-valued expression for a target supplied by the query.

        Returns
        -------
        pl.Series | pl.Expr
            An eager Series, or an Expr producing a Boolean column. With a valid target, a null source date yields False.

        Raises
        ------
        TypeError
            Unsupported Python arguments, including a literal None target, fail
            when the expression is created. Eager calls also raise TypeError for a missing target.
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
        return _query_operation(self, 100, "is_year", year, parameter="year")

    def is_quarter(self, quarter: _ExprIntegerInput) -> pl.Series | pl.Expr:
        """Match scalar or equal-length integer quarter targets.

        Parameters
        ----------
        quarter : integer or one-dimensional integer collection or polars.Expr
            Required scalar or equal-length integer quarter target. Legal nonmatches return False; missing
            targets fail even for source null.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _query_operation(self, 101, "is_quarter", quarter, parameter="quarter")

    def is_month(self, month: _ExprQuerySelection) -> pl.Series | pl.Expr:
        """Match integer or saved month names, by position; null is False.

        Parameters
        ----------
        month : integer, name or one-dimensional collection or polars.Expr
            Required month number or name from the default vocabulary. A column pairs by position.

        Returns
        -------
        pl.Series | pl.Expr
            An eager Series, or an Expr producing a Boolean column. With a valid target, a null source date yields False.

        Raises
        ------
        TypeError
            Unsupported Python arguments, including a literal None target, fail
            when the expression is created. Eager calls also raise TypeError for a missing target.
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
        return _query_operation(self, 102, "is_month", month, 1, "month")

    def is_weekday(self, weekday: _ExprQuerySelection) -> pl.Series | pl.Expr:
        """Test for a local weekday by name or by number, with Monday as 0.

        Parameters
        ----------
        weekday : integer, name or one-dimensional collection or polars.Expr
            Weekday number, with Monday as 0, or a weekday name in the library's default
            vocabulary.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _query_operation(self, 103, "is_weekday", weekday, 2, "weekday")

    def is_day(self, day: _ExprIntegerInput) -> pl.Series | pl.Expr:
        """Test whether each local day of the month equals the supplied day.

        Parameters
        ----------
        day : integer or one-dimensional integer collection or polars.Expr
            An integer day or a same-length integer column paired by position. A valid
            integer outside the matching range yields False. Strings, booleans and missing targets are invalid.
            Use an integer-valued expression for a target supplied by the query.

        Returns
        -------
        pl.Series | pl.Expr
            An eager Series, or an Expr producing a Boolean column. With a valid target, a null source date yields False.

        Raises
        ------
        TypeError
            Unsupported Python arguments, including a literal None target, fail
            when the expression is created. Eager calls also raise TypeError for a missing target.
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
        return _query_operation(self, 104, "is_day", day, parameter="day")

    def is_long_year(self) -> pl.Series | pl.Expr:
        """Whether the local calendar year contains 53 ISO weeks; null is False.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 105, "is_long_year")

    def leap_bt_year(self, year: _ExprIntegerInput) -> pl.Series | pl.Expr:
        """Count leap years between row years and targets, lower inclusive.

        Parameters
        ----------
        year : integer or one-dimensional integer collection or polars.Expr
            Required integer year or an equal-length column of years. Count leap years from the lower year inclusive to the upper year exclusive.

        Returns
        -------
        pl.Series | pl.Expr
            An eager Series, or an Expr producing a nullable integer count. A null source date yields null.

        Raises
        ------
        TypeError
            Unsupported Python arguments, including a literal None target, fail
            when the expression is created. Eager calls also raise TypeError for a missing target.
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
        return _query_operation(self, 11, "leap_bt_year", year, parameter="year")

    def is_dst(self) -> pl.Series | pl.Expr:
        """Whether the native zone has nonzero DST; naive/null is False.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 106, "is_dst")

    def utcoffset_seconds(self) -> pl.Series | pl.Expr:
        """Actual integer UTC offset; naive and missing rows are null.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 12, "utcoffset_seconds")

    def is_past(self) -> pl.Series | pl.Expr:
        """Strictly before one captured reference; Expr captures on creation.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 107, "is_past")

    def is_future(self) -> pl.Series | pl.Expr:
        """Strictly after one captured reference; Expr captures on creation.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 108, "is_future")

    def isocalendar(self) -> pl.Series | pl.Expr:
        """Return year/week/day as a native Struct with UInt32 fields.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.

        Examples
        --------
        On a native Polars Series

        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series('event', ['2021-01-01']).str.to_datetime(time_unit='us')
        >>> dates = source.pldt.isocalendar()
        >>> print(dates.to_list())
        [{'year': 2020, 'week': 53, 'day': 5}]

        In a Polars query

        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame([pl.Series('event', ['2021-01-01']).str.to_datetime(time_unit='us')])
        >>> expr = pl.col('event').pldt.isocalendar()
        >>> dates = frame.select(expr)['event']
        >>> print(dates.to_list())
        [{'year': 2020, 'week': 53, 'day': 5}]

        On a Pldt

        >>> from rstimes import Pldt
        >>> Pldt(["2021-01-01"]).isocalendar().to_list()
        [{'year': 2020, 'week': 53, 'day': 5}]
        """
        return _query_operation(self, 201, "isocalendar")

    def timedf(self) -> pl.DataFrame | pl.Expr:
        """Read nine local time fields, including fractional seconds and fold.

        Returns
        -------
        pl.DataFrame | pl.Expr
            Pldt and Series.pldt return a Polars DataFrame with nine columns.
            Expr.pldt returns an expression producing one Struct column with nine fields.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 202, "timedf")

    def utctimedf(self) -> pl.DataFrame | pl.Expr:
        """Return UTC time fields; naive fields do not move and DST is zero.

        Returns
        -------
        pl.DataFrame | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _query_operation(self, 203, "utctimedf")


class _PeriodMethods:
    """Shared date boundaries and names, distinct from native numerical methods."""
    def to_first_of(self, unit: str) -> Pldt | pl.Expr:
        """Move to the first calendar day of the selected period, keeping the time of day.

        The clock and subsecond digits are carried to the selected calendar day. A regional gap can require a valid clock on that day. If the entire selected day is missing, the operation raises an error.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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

        For Expr.pldt.to_first_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-month-boundaries

        For Series.pldt.to_first_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-month-boundaries

        For Pldt.to_first_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-pldt-month-boundaries
        """
        return _period_operation(self, "boundary", unit, 0, 0, False, "to_first_of")

    def is_first_of(self, unit: str) -> pl.Series | pl.Expr:
        """Test whether each date falls on the first calendar day of the selected period.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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

        For Expr.pldt.is_first_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-month-boundaries

        For Series.pldt.is_first_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-month-boundaries

        For Pldt.is_first_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-pldt-month-boundaries
        """
        return _period_operation(self, "boundary", unit, 0, 0, True, "is_first_of")

    def to_last_of(self, unit: str) -> Pldt | pl.Expr:
        """Move to the last calendar day of the selected period, keeping the time of day.

        The clock and subsecond digits are carried to the selected calendar day. A regional gap can require a valid clock on that day. If the entire selected day is missing, the operation raises an error.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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

        For Expr.pldt.to_last_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-month-boundaries

        For Series.pldt.to_last_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-month-boundaries

        For Pldt.to_last_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-pldt-month-boundaries
        """
        return _period_operation(self, "boundary", unit, 0, 1, False, "to_last_of")

    def is_last_of(self, unit: str) -> pl.Series | pl.Expr:
        """Test whether each date falls on the last calendar day of the selected period.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _period_operation(self, "boundary", unit, 0, 1, True, "is_last_of")

    def to_start_of(self, unit: str) -> Pldt | pl.Expr:
        """Move to the first valid instant of the selected period.

        Use the first or last valid time in the selected period, at the source precision. For example, a millisecond day ends at 23:59:59.999.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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

        For Expr.pldt.to_start_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-month-boundaries

        For Series.pldt.to_start_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-month-boundaries

        For Pldt.to_start_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-pldt-month-boundaries
        """
        return _period_operation(self, "boundary", unit, 0, 2, False, "to_start_of")

    def is_start_of(self, unit: str) -> pl.Series | pl.Expr:
        """Test whether each time equals the first valid instant of the selected period.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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

        For Expr.pldt.is_start_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-month-boundaries

        For Series.pldt.is_start_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-month-boundaries

        For Pldt.is_start_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-pldt-month-boundaries
        """
        return _period_operation(self, "boundary", unit, 0, 2, True, "is_start_of")

    def to_end_of(self, unit: str) -> Pldt | pl.Expr:
        """Move to the last valid instant of the selected period in the current unit.

        Use the first or last valid time in the selected period, at the source precision. For example, a millisecond day ends at 23:59:59.999.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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

        For Expr.pldt.to_end_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-month-boundaries

        For Series.pldt.to_end_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-month-boundaries

        For Pldt.to_end_of, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-pldt-month-boundaries
        """
        return _period_operation(self, "boundary", unit, 0, 3, False, "to_end_of")

    def is_end_of(self, unit: str) -> pl.Series | pl.Expr:
        """Test whether each time equals the last valid instant in the current unit.

        Parameters
        ----------
        unit : str
            One supported natural unit for this boundary; it is not an arbitrary multi-step frequency.

        Returns
        -------
        pl.Series | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _period_operation(self, "boundary", unit, 0, 3, True, "is_end_of")

    def normalize(self) -> Pldt | pl.Expr:
        """Return the real start of this local day, staying within the day.

        Choose the first valid instant of the source's local calendar day.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _period_operation(self, "boundary", "D", 0, 2, False, "normalize")

    def snap(self, unit: str='s') -> Pldt | pl.Expr:
        """Select the nearest real period start; equal distances select later.

        Parameters
        ----------
        unit : str
            One natural Y/Q/M/W/D/h/m/min/s/ms/us/ns period or an exact saved month/weekday name; no
            arbitrary multi-step frequency or numeric weekday.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        On a native Polars Series

        >>> import polars as pl
        >>> import rstimes.pldt
        >>> source = pl.Series("event", ["2024-01-02 11:59", "2024-01-02 12:00", None])
        >>> dates = source.str.to_datetime(time_unit="us").pldt.snap("D")
        >>> print(dates.isoformat().to_list())
        ['2024-01-02T00:00:00', '2024-01-03T00:00:00', None]

        In a Polars query

        >>> import polars as pl
        >>> import rstimes.pldt
        >>> frame = pl.DataFrame({"event": ["2024-01-02 11:59", "2024-01-02 12:00", None]})
        >>> expr = pl.col("event").pldt.parse(unit="us").pldt.snap("D")
        >>> print(frame.lazy().select(expr).collect()["event"].dt.strftime("%Y-%m-%dT%H:%M:%S").to_list())
        ['2024-01-02T00:00:00', '2024-01-03T00:00:00', None]

        On a Pldt

        >>> from rstimes import Pldt
        >>> events = Pldt(["2024-01-02 11:59", "2024-01-02 12:00", None])
        >>> print(events.snap("D").isoformat().to_list())
        ['2024-01-02T00:00:00', '2024-01-03T00:00:00', None]
        """
        return _period_operation(self, "snap", unit, 0, 0, False, "snap")

    def fsp(self, precision: SupportsIndex) -> Pldt | pl.Expr:
        """Truncate the fractional second, preserving the current storage unit.

        Parameters
        ----------
        precision : SupportsIndex
            Single integer number of fractional-second digits. Negative values fail; 9 or more preserve
            existing precision without inventing finer data.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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

        For Expr.pldt.fsp, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-second-grid

        For Series.pldt.fsp, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-second-grid

        For Pldt.fsp, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-pldt-second-grid
        """
        return _period_operation(self, "fsp", None, precision, 0, False, "fsp")


class _TransformMethods:
    """Date operations shared by Pldt and the two native namespaces."""
    def to_datetime(self, year: _ExprOptionalField=None, month: _ExprOptionalField=None, day: _ExprOptionalField=None, hour: _ExprOptionalField=None, minute: _ExprOptionalField=None, second: _ExprOptionalField=None, microsecond: _ExprOptionalField=None, nanosecond: _ExprOptionalField=None) -> Pldt | pl.Expr:
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
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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

        For Expr.pldt.to_datetime, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-calendar.html#reader-expr-month-and-fields

        For Series.pldt.to_datetime, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-calendar.html#reader-series-month-and-fields

        For Pldt.to_datetime, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-calendar.html#reader-pldt-month-and-fields
        """
        return _date_operation(self, "adjust", (year, month, day, hour, minute, second, microsecond, nanosecond), "to_datetime")

    def to_date(self, year: _ExprOptionalField=None, month: _ExprOptionalField=None, day: _ExprOptionalField=None) -> Pldt | pl.Expr:
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
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "adjust", (year, month, day, None, None, None, None, None), "to_date")

    def to_time(self, hour: _ExprOptionalField=None, minute: _ExprOptionalField=None, second: _ExprOptionalField=None, microsecond: _ExprOptionalField=None, nanosecond: _ExprOptionalField=None) -> Pldt | pl.Expr:
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
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "adjust", (None, None, None, hour, minute, second, microsecond, nanosecond), "to_time")

    def to_year(self, offset: _ExprIntegerInput, month: _ExprSelection=None, day: _ExprOptionalField=None) -> Pldt | pl.Expr:
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
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "year", (offset, month, day), "to_year")

    def to_quarter(self, offset: _ExprIntegerInput, month: _ExprOptionalField=None, day: _ExprOptionalField=None) -> Pldt | pl.Expr:
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
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "quarter", (offset, month, day), "to_quarter")

    def to_month(self, offset: _ExprIntegerInput, day: _ExprOptionalField=None) -> Pldt | pl.Expr:
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
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "month", (offset, day), "to_month")

    def to_weekday(self, offset: _ExprIntegerInput, weekday: _ExprSelection=None) -> Pldt | pl.Expr:
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
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "weekday", (offset, weekday), "to_weekday")

    def to_day(self, offset: _ExprIntegerInput) -> Pldt | pl.Expr:
        """Move by calendar days, keeping the time of day.

        Parameters
        ----------
        offset : integer or one-dimensional integer collection or polars.Expr
            Signed integer amount, scalar or exactly source-length column. Zero is real and a negative
            amount reverses direction; no float truncation.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "day", (offset, ), "to_day")

    def to_curr_year(self, month: _ExprSelection=None, day: _ExprOptionalField=None) -> Pldt | pl.Expr:
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
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "year", (0, month, day), "to_curr_year")

    def to_prev_year(self, month: _ExprSelection=None, day: _ExprOptionalField=None) -> Pldt | pl.Expr:
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
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "year", (-1, month, day), "to_prev_year")

    def to_next_year(self, month: _ExprSelection=None, day: _ExprOptionalField=None) -> Pldt | pl.Expr:
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
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "year", (1, month, day), "to_next_year")

    def to_curr_quarter(self, month: _ExprOptionalField=None, day: _ExprOptionalField=None) -> Pldt | pl.Expr:
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
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "quarter", (0, month, day), "to_curr_quarter")

    def to_prev_quarter(self, month: _ExprOptionalField=None, day: _ExprOptionalField=None) -> Pldt | pl.Expr:
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
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "quarter", (-1, month, day), "to_prev_quarter")

    def to_next_quarter(self, month: _ExprOptionalField=None, day: _ExprOptionalField=None) -> Pldt | pl.Expr:
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
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "quarter", (1, month, day), "to_next_quarter")

    def to_curr_month(self, day: _ExprOptionalField=None) -> Pldt | pl.Expr:
        """Select the current calendar month and fit the day to that month.

        Parameters
        ----------
        day : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "month", (0, day), "to_curr_month")

    def to_prev_month(self, day: _ExprOptionalField=None) -> Pldt | pl.Expr:
        """Select the previous calendar month and fit the day to that month.

        Parameters
        ----------
        day : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "month", (-1, day), "to_prev_month")

    def to_next_month(self, day: _ExprOptionalField=None) -> Pldt | pl.Expr:
        """Select the next calendar month and fit the day to that month.

        Parameters
        ----------
        day : integer or one-dimensional integer collection or None or polars.Expr
            Optional integer field/selector. None retains the source. Day is 1-31. Strict replace requires
            a real resulting date; calendar conveniences keep their separate valid upper-selection/month-
            end rules.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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

        For Expr.pldt.to_next_month, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-calendar.html#reader-expr-month-and-fields

        For Series.pldt.to_next_month, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-calendar.html#reader-series-month-and-fields

        For Pldt.to_next_month, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-calendar.html#reader-pldt-month-and-fields
        """
        return _date_operation(self, "month", (1, day), "to_next_month")

    def to_curr_weekday(self, weekday: _ExprSelection=None) -> Pldt | pl.Expr:
        """Select the current calendar week and optionally choose a weekday.

        Parameters
        ----------
        weekday : integer, name or one-dimensional collection or None or polars.Expr
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "weekday", (0, weekday), "to_curr_weekday")

    def to_prev_weekday(self, weekday: _ExprSelection=None) -> Pldt | pl.Expr:
        """Select the previous calendar week and optionally choose a weekday.

        Parameters
        ----------
        weekday : integer, name or one-dimensional collection or None or polars.Expr
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "weekday", (-1, weekday), "to_prev_weekday")

    def to_next_weekday(self, weekday: _ExprSelection=None) -> Pldt | pl.Expr:
        """Select the next calendar week and optionally choose a weekday.

        Parameters
        ----------
        weekday : integer, name or one-dimensional collection or None or polars.Expr
            Optional Monday-0 through Sunday-6 integer or exact saved weekday name. None retains the
            source; out-of-range selectors fail.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "weekday", (1, weekday), "to_next_weekday")

    def to_monday(self) -> Pldt | pl.Expr:
        """Move to Monday of the current calendar week, keeping the time of day.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _date_operation(self, "weekday", (0, 0), "to_monday")

    def to_tuesday(self) -> Pldt | pl.Expr:
        """Move to Tuesday of the current calendar week, keeping the time of day.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _date_operation(self, "weekday", (0, 1), "to_tuesday")

    def to_wednesday(self) -> Pldt | pl.Expr:
        """Move to Wednesday of the current calendar week, keeping the time of day.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _date_operation(self, "weekday", (0, 2), "to_wednesday")

    def to_thursday(self) -> Pldt | pl.Expr:
        """Move to Thursday of the current calendar week, keeping the time of day.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _date_operation(self, "weekday", (0, 3), "to_thursday")

    def to_friday(self) -> Pldt | pl.Expr:
        """Move to Friday of the current calendar week, keeping the time of day.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _date_operation(self, "weekday", (0, 4), "to_friday")

    def to_saturday(self) -> Pldt | pl.Expr:
        """Move to Saturday of the current calendar week, keeping the time of day.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _date_operation(self, "weekday", (0, 5), "to_saturday")

    def to_sunday(self) -> Pldt | pl.Expr:
        """Move to Sunday of the current calendar week, keeping the time of day.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _date_operation(self, "weekday", (0, 6), "to_sunday")

    def to_yesterday(self) -> Pldt | pl.Expr:
        """Move to the previous local calendar day, keeping the time of day.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _date_operation(self, "day", (-1,), "to_yesterday")

    def to_tomorrow(self) -> Pldt | pl.Expr:
        """Move to the next local calendar day, keeping the time of day.

        Returns
        -------
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

        Raises
        ------
        TypeError
            An unsupported source dtype cannot be read as a date column.
        polars.exceptions.ComputeError
            A Polars expression can fail during planning or evaluation.

        Notes
        -----
        Polars checks its input types when planning and evaluates values in select or collect.
        An execution error can report a position within its input batch.
        """
        return _date_operation(self, "day", (1,), "to_tomorrow")

    def add(self, years: _ExprIntegerInput=0, quarters: _ExprIntegerInput=0, months: _ExprIntegerInput=0, weeks: _ExprIntegerInput=0, days: _ExprIntegerInput=0, hours: _ExprIntegerInput=0, minutes: _ExprIntegerInput=0, seconds: _ExprIntegerInput=0, milliseconds: _ExprIntegerInput=0, microseconds: _ExprIntegerInput=0, nanoseconds: _ExprIntegerInput=0) -> Pldt | pl.Expr:
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
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        On a native Polars Series

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

        In a Polars query

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

        On a Pldt

        >>> from rstimes import Pldt
        >>> events = Pldt(["2024-01-31 14:30", None])
        >>> print(events.add(months=1).isoformat().to_list())
        ['2024-02-29T14:30:00', None]

        >>> from rstimes import Pldt
        >>> Pldt([1], unit="us").add(microseconds=1, nanoseconds=-1000).to_physical().to_list()
        [1]
        """
        return _date_operation(self, "add", (years, quarters, months, weeks, days, hours, minutes, seconds, milliseconds, microseconds, nanoseconds), "add")

    def sub(self, years: _ExprIntegerInput=0, quarters: _ExprIntegerInput=0, months: _ExprIntegerInput=0, weeks: _ExprIntegerInput=0, days: _ExprIntegerInput=0, hours: _ExprIntegerInput=0, minutes: _ExprIntegerInput=0, seconds: _ExprIntegerInput=0, milliseconds: _ExprIntegerInput=0, microseconds: _ExprIntegerInput=0, nanoseconds: _ExprIntegerInput=0) -> Pldt | pl.Expr:
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
        Pldt | pl.Expr
            A date column or query result for direct calls. The Expr accessor returns
            a native expression to evaluate inside a query.

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
        return _date_operation(self, "sub", (years, quarters, months, weeks, days, hours, minutes, seconds, milliseconds, microseconds, nanoseconds), "sub")


class _TimezoneMetadata:
    """Whole-column eager metadata; Expr has no implicit schema collection."""

    def _timezone_key(self):
        source = self._series if isinstance(self, _SeriesNamespace) else self
        dtype = pl.Series.dtype.fget(source)  # pyright: ignore[reportOptionalCall] -- TY025; see tests/typing/pyright_exceptions.json.
        if dtype.base_type() not in (pl.Date, pl.Datetime):
            raise _own_error(TypeError('requires a Date or Datetime source'), 'data', source)
        return dtype.time_zone if dtype.base_type() is pl.Datetime else None

    @property
    def tzinfo(self) -> _dt.tzinfo | None:
        """Return the normalized timezone encoded by the entire column.
        
        Returns
        -------
        datetime.tzinfo or None
            None for naive dates, timezone.utc for UTC aliases, or ZoneInfo
            for another supported IANA key. Original object identity is absent
            from Polars metadata, including for empty columns."""
        try:
            key = self._timezone_key()
            return None if key is None else _named_zone(key)
        except Exception as error:
            _raise_argument_context(error, 'Pldt.tzinfo', 'metadata', None)

    @property
    def tz_available(self) -> set[str]:
        """Return region names supported by the bundled native backend.
        
        Returns
        -------
        set[str]
            A fresh set of supported keys, independent of the system ZoneInfo
            database. This does not resolve the local timezone or read dates."""
        return set(_pldt_available_zones())

    def is_utc(self) -> bool:
        """Return whether the column's actual metadata represents UTC.
        
        Returns
        -------
        bool
            One boolean for the whole column, also for empty/all-null data.
            This query does not resolve the process-local timezone."""
        try:
            key = self._timezone_key()
            return key is not None and key.lower() in _UTC_ALIASES
        except Exception as error:
            _raise_argument_context(error, 'Pldt.is_utc', 'metadata', None)

    def is_local(self) -> bool:
        """Compare encoded metadata with the cached process-local zone.
        
        Returns
        -------
        bool
            False for naive dates without detecting a local zone. An aware
            column resolves the shared local service only when this is called;
            a failed lookup raises instead of silently assuming UTC."""
        try:
            key = self._timezone_key()
            return key is not None and _prepare_zone(key).key == _prepare_zone(_local_zone()).key
        except Exception as error:
            _raise_argument_context(error, 'Pldt.is_local', 'metadata', None)


class Pldt(_TransformMethods, _PeriodMethods, _QueryMethods, _OutputMethods, _PythonOutputMethods, _TimezoneMetadata, pl.Series):
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
        try:
            unit = _unit(unit, optional=True)
            name = _name(name)
            copy = _bool_option(copy, "Pldt", "copy")
            isoformat = _bool_option(isoformat, "Pldt", "isoformat")
            strict = _bool_option(strict, "Pldt", "strict")
            yearfirst = None if yearfirst is None else _bool_option(yearfirst, "Pldt", "yearfirst")
            dayfirst = None if dayfirst is None else _bool_option(dayfirst, "Pldt", "dayfirst")
            if cfg is not None and not issubclass(type(cfg), Configs):
                raise _own_error(TypeError("must be a Configs instance or None"), "cfg", cfg)
            target = _prepare_zone(tz)
            policy, _, _ = _timezone_policy(ambiguous, nonexistent, expression=False)
            carrier = _construct(data, unit=unit, name=name, copy=copy, default=default,
                                 yearfirst=yearfirst, dayfirst=dayfirst, isoformat=isoformat,
                                 strict=strict, cfg=cfg, tz=target, policy=policy)
            super().__init__(carrier)

        except Exception as error:
            _raise_argument_context(error, "Pldt", "arguments", None)

    @classmethod
    def _from_pyseries(cls, pyseries):
        # One mature result boundary: only Datetime columns remain Pldt.
        # Integer/String/Date/etc. outputs keep ordinary Series protocols.
        if pyseries.dtype().base_type() is not pl.Datetime:
            return pl.Series._from_pyseries(pyseries)
        return super()._from_pyseries(pyseries)

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
            through nine, even if the additional digits are zero. An explicit unit is lossless.
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
        try:
            return cls(data, unit=unit, name=name, copy=copy, tz=tz, default=default,
                       yearfirst=yearfirst, dayfirst=dayfirst, isoformat=isoformat,
                       strict=strict, cfg=cfg, ambiguous=ambiguous, nonexistent=nonexistent)

        except Exception as error:
            _raise_argument_context(error, "Pldt.parse", "arguments", None)

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
        return _strptime_eager(cls, dtstr, fmt, size=size, tz=tz, unit=unit, name=name,
                              cfg=cfg, ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _clock_factory(cls, size, tz, unit, name, "Pldt.now", tz is None)

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
        return _clock_factory(cls, size, None, unit, name, "Pldt.today", True)

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
        return _clock_factory(cls, size, timezone.utc, unit, name, "Pldt.utcnow", False)

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
        return _numeric_eager(cls, seconds, 'seconds', size=size, tz=tz, unit=unit,
                              name=name, ambiguous=ambiguous, nonexistent=nonexistent, entry="Pldt.fromseconds")

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
        return _numeric_eager(cls, us, 'micros', size=size, tz=tz, unit=unit,
                              name=name, ambiguous=ambiguous, nonexistent=nonexistent, entry="Pldt.frommicroseconds")

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
        return _numeric_eager(cls, ts, ("local_timestamp" if tz is None else "timestamp"), size=size, tz=tz, unit=unit,
                              name=name, entry="Pldt.fromtimestamp")

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
        return _numeric_eager(cls, ts, 'utc_timestamp', size=size, tz=timezone.utc, unit=unit,
                              name=name, entry="Pldt.utcfromtimestamp")

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
        return _date_factory(cls, dt, "date", size=size, tz=tz, unit=unit, name=name,
                             ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _date_factory(cls, dt, "datetime", size=size, tz=tz, unit=unit, name=name,
                             ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _date_factory(cls, dt64, "numpy", size=size, tz=tz, unit=unit, name=name,
                             ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _calendar_factory(cls, "ordinal", (ordinal,), size=size, tz=tz, unit=unit,
                                  name=name, ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _calendar_factory(cls, "iso", (year, week, weekday), size=size, tz=tz, unit=unit,
                                  name=name, ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _calendar_factory(cls, "doy", (year, doy), size=size, tz=tz, unit=unit,
                                  name=name, ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _combine_factory(cls, date, time, size=size, tz=tz, unit=unit, name=name,
                                 ambiguous=ambiguous, nonexistent=nonexistent)

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
            through nine, even if the additional digits are zero. An explicit unit is lossless.
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
        return _iso_factory(cls, dtstr, size=size, tz=tz, unit=unit, name=name,
                             ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _range_factory(cls, start, end=end, periods=periods, freq=freq, tz=tz,
                              normalize=normalize, inclusive=inclusive, unit=unit, name=name,
                              default=default, yearfirst=yearfirst, dayfirst=dayfirst,
                              isoformat=isoformat, strict=strict, cfg=cfg,
                              ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _as_unit(self, unit, round_ok, entry="Pldt.as_unit")

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
        return _tz_eager(self, "localize", tz, ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _tz_eager(self, "convert", tz)

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
        return _tz_eager(self, "astimezone", tz, ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _tz_eager(self, "switch", targ_tz, base_tz, naive, ambiguous, nonexistent)

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
        return _state_copy(self, False)  # pyright: ignore[reportReturnType] -- TY026; see tests/typing/pyright_exceptions.json.

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
        try:
            return _state_copy(self, _bool_option(deep, 'Pldt.copy', 'deep'),  # pyright: ignore[reportReturnType] -- TY027; see tests/typing/pyright_exceptions.json.
                               name=_name(name), honor_copy=True)
        except Exception as error:
            _raise_argument_context(error, 'Pldt.copy', 'arguments', None)

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
        return _state_copy(self, True, memo)  # pyright: ignore[reportReturnType] -- TY028; see tests/typing/pyright_exceptions.json.

    def __getstate__(self) -> object:  # pyright: ignore[reportIncompatibleMethodOverride] -- TY029; see tests/typing/pyright_exceptions.json.
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
        return _capture_state(self)

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
        _apply_state(self, state)

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
        return _state_recipe(self)

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
        if _state_definition(type(self), "__reduce__") is not Pldt.__reduce__:
            try:
                return self.__reduce__()
            except Exception as error:
                raise _external_error(error)
        return _state_recipe(self)

    def to_numpy(self, *, writable: _Boolean=False, allow_copy: _Boolean=True, allow_nat_collision: _Boolean=False) -> np.ndarray:  # pyright: ignore[reportIncompatibleMethodOverride] -- TY030; see tests/typing/pyright_exceptions.json.
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
        allow = _bool_option(allow_nat_collision, "Pldt.to_numpy", "allow_nat_collision")
        source = _plain_series(self)
        return _numpy_export(source, writable, allow_copy, allow)

    def to_pandas(self, *, use_pyarrow_extension_array: _Boolean=False, allow_nat_collision: _Boolean=False, **kwargs: Any) -> object:  # pyright: ignore[reportIncompatibleMethodOverride] -- TY032; see tests/typing/pyright_exceptions.json.
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
            The true final result exceeds the current unit/target capacity.

        Examples
        --------
        See the complete example at
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-pandas-arrow.html#pldt-arrow-valid-endpoint-roundtrip
        """
        allow = _bool_option(allow_nat_collision, "Pldt.to_pandas", "allow_nat_collision")
        source = _plain_series(self)
        result = pl.Series.to_pandas(self, use_pyarrow_extension_array=use_pyarrow_extension_array, **kwargs)  # pyright: ignore[reportArgumentType] -- TY033; see tests/typing/pyright_exceptions.json.
        # This is the actual returned representation, including user callbacks;
        # selecting an Arrow keyword alone is not evidence of preserved validity.
        target = pl.from_pandas(result)
        _pldt_check_temporal(source, target, allow)
        return result

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
        # Preserve Polars' dtype/copy protocol, but bind the real exporter once:
        # a neutral attribute wrapper does not transfer ownership of this exit.
        if dtype is None and not self.has_nulls() and self.dtype == pl.String:
            dtype = np.dtype("U")
        if copy is None:
            writable, allow_copy = False, True
        elif copy is True:
            writable, allow_copy = True, True
        elif copy is False:
            writable, allow_copy = False, False
        else:
            raise TypeError(f"invalid input for `copy`: {copy!r}")
        exporter = self.to_numpy
        base_exporter = (type(exporter) is MethodType and exporter.__self__ is self
                         and exporter.__func__ is _BASE_NUMPY_EXPORT)
        protected = dtype is not None and base_exporter
        source = _plain_series(self) if base_exporter else None
        result = (_numpy_export(cast(pl.Series, source), writable, allow_copy, False)
                  if base_exporter else exporter(writable=writable, allow_copy=allow_copy))
        converted = False
        if dtype is not None and dtype != result.dtype:
            if copy is False:
                raise RuntimeError(f"copy not allowed: cast from {result.dtype} to {dtype} prohibited")
            result = result.__array__(dtype)
            converted = True
        # A genuine business override owns its returned representation. Do not
        # invoke its descriptor again or impose this base exit on that protocol.
        if not protected:
            return result
        # The actual base exporter already checked NaT collisions. Without a
        # date dtype change its native representation needs no second scan.
        if not converted and result.dtype.kind == "M":
            return result
        # The original protected flag proves the already-captured owner exists.
        source = cast(pl.Series, source)
        if result.dtype.kind == "M":
            unit, multiplier = np.datetime_data(result.dtype)
            code = _NUMPY_DATE_CODES.get(unit, _NUMPY_EXPORT_SUBNS.get(unit))
            if code is None:
                raise ValueError("Pldt.__array__: NumPy output needs a concrete date unit")
            _pldt_check_numpy(source, _plain_series(result.view(np.int64)), (code, multiplier))
        elif result.dtype.kind == "f" and result.dtype.type not in _NUMPY_FLOAT_TYPES:
            if np.finfo(result.dtype).nmant < 63:
                _pldt_check_numpy(source, _plain_series(result.astype(np.float64)), None)
            elif source.has_nulls() or not np.array_equal(result, source.to_physical().to_numpy()):
                raise ValueError("Pldt.__array__: requested NumPy dtype cannot preserve the date tick or missing positions")
        elif result.dtype.kind in "iuf":
            _pldt_check_numpy(source, _plain_series(result), None)
        else:
            # Explicit object/text requests still must round-trip each value
            # and missing position. No implicit fallback or replacement dtype.
            original = cast(pl.Datetime, source.dtype).time_unit
            restored = np.asarray(result, dtype=f"datetime64[{original}]")
            _pldt_check_numpy(source, _plain_series(restored.view(np.int64)), (_NUMPY_DATE_CODES[original], 1))
        return result

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
        if method == "__call__" and len(inputs) == 2 and not kwargs and ufunc in (np.add, np.subtract):
            left, right = inputs
            other = right if left is self else left
            temporal = isinstance(other, (np.datetime64, np.timedelta64)) or issubclass(type(other), np.ndarray) and other.dtype.kind in "Mm"
            if temporal:
                if ufunc is np.subtract and left is not self:
                    return NotImplemented
                return _binary_eager(self, other, subtract=ufunc is np.subtract, reflected=left is not self)
        return super().__array_ufunc__(ufunc, method, *inputs, **kwargs)

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
        return _binary_eager(self, other)

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
        return _binary_eager(self, other, reflected=True)

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
        return _binary_eager(self, other, subtract=True)



class _SeriesNamespace(_TransformMethods, _PeriodMethods, _QueryMethods, _OutputMethods, _PythonOutputMethods, _TimezoneMetadata):
    """Run rsTimes date operations on a native Polars Series.

    Import rstimes.pldt to register the accessor. Date operations produce a
    Pldt, and queries retain their native Polars result types.

    Examples
    --------
    >>> import polars as pl
    >>> import rstimes.pldt
    >>> source = pl.Series("day", ["2024-02-29", None])
    >>> source.pldt.parse(unit="us").isoformat().to_list()
    ['2024-02-29T00:00:00', None]

    For Pldt(...).pldt, see
    https://aresjef.github.io/rsTimes/1.1.1/api/inherited-pldt-accessors.html#ref-pldt-native-registered-accessor
    """

    def diff(self, dtobj: _DiffInput, unit: str, absolute: _Boolean=False, inclusive: str='one') -> pl.Series | pl.Expr:
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
            Count boundaries with one, both or neither endpoint. Use this method on
            Series.pldt or Expr.pldt. Polars Series.diff compares adjacent rows.

        Returns
        -------
        pl.Series | pl.Expr
            The result column, computed from the supplied Series.

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
        return _boundary_difference(self, dtobj, unit, absolute, inclusive)

    def round(self, freq: _FixedFrequency='s') -> Pldt:
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

        For Series.pldt.round, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-second-grid
        """
        return _period_operation(self, "round", None, freq, 0, False, "pldt.round")

    def ceil(self, freq: _FixedFrequency='s') -> Pldt:
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

        For Series.pldt.ceil, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-second-grid
        """
        return _period_operation(self, "round", None, freq, 1, False, "pldt.ceil")

    def floor(self, freq: _FixedFrequency='s') -> Pldt:
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

        For Series.pldt.floor, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-boundaries.html#reader-series-second-grid
        """
        return _period_operation(self, "round", None, freq, 2, False, "pldt.floor")

    def add_delta(self, delta: _DeltaInput) -> Pldt:
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
        return _binary_eager(self, delta, named=True)

    def sub_delta(self, delta: _DeltaInput) -> Pldt:
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

        For Series.pldt.sub_delta, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-arithmetic.html#reader-series-subtract-delta
        """
        return _binary_eager(self, delta, subtract=True, named=True)

    def replace(self, year: _OptionalField=None, month: _OptionalField=None, day: _OptionalField=None, hour: _OptionalField=None, minute: _OptionalField=None, second: _OptionalField=None, microsecond: _OptionalField=None, nanosecond: _OptionalField=None, tzinfo: _Zone=_UNCHANGED_ZONE, *, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:  # pyright: ignore[reportArgumentType] -- TY035; see tests/typing/pyright_exceptions.json.
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
        return _date_operation(self, "replace", (year, month, day, hour, minute, second, microsecond, nanosecond),
                               "pldt.replace", tzinfo=tzinfo, ambiguous=ambiguous, nonexistent=nonexistent)

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
        self._series = series

    def fromisoformat(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:
        """Parse complete ISO text into one native date column.

        Parameters
        ----------
        tz : str, datetime.tzinfo or None
            Use an IANA name, a ZoneInfo object or a fixed offset that Polars can represent.
            Attach the chosen zone to naive ISO dates and convert ISO values with a zone to it.
            With None, keep a common zone from the input if one is present.
        unit : {"ms", "us", "ns"} or None
            Without a unit, text uses us for up to six fractional digits and ns for seven
            through nine, even if the additional digits are zero. An explicit unit is lossless.
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

        For Series.pldt.fromisoformat, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-factories.html#reader-series-iso-text
        """
        cls = type(self._series) if isinstance(self._series, Pldt) else Pldt
        return _iso_factory(cls, self._series, tz=tz, unit=unit, name=name,
                             ambiguous=ambiguous, nonexistent=nonexistent)

    def combine(self, time: _CombineTime=None, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:
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

        For Series.pldt.combine, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-factories.html#reader-series-combine-clock
        """
        cls = type(self._series) if isinstance(self._series, Pldt) else Pldt
        return _combine_factory(cls, self._series, time, tz=tz, unit=unit, name=name,
                                 ambiguous=ambiguous, nonexistent=nonexistent)

    def fromordinal(self, *, tz: _Zone=None, unit: _Unit='us', name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:
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
        cls = type(self._series) if isinstance(self._series, Pldt) else Pldt
        return _calendar_factory(cls, "ordinal", (self._series,), tz=tz, unit=unit, name=name,
                                 ambiguous=ambiguous, nonexistent=nonexistent)

    def fromisocalendar(self, week: _CalendarInput, weekday: _CalendarInput, *, tz: _Zone=None, unit: _Unit='us', name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:
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
        cls = type(self._series) if isinstance(self._series, Pldt) else Pldt
        return _calendar_factory(cls, "iso", (self._series, week, weekday), tz=tz, unit=unit, name=name,
                                 ambiguous=ambiguous, nonexistent=nonexistent)

    def fromdayofyear(self, doy: _CalendarInput, *, tz: _Zone=None, unit: _Unit='us', name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:
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
        cls = type(self._series) if isinstance(self._series, Pldt) else Pldt
        return _calendar_factory(cls, "doy", (self._series, doy), tz=tz, unit=unit, name=name,
                                 ambiguous=ambiguous, nonexistent=nonexistent)

    def parse(self, *, unit: _Unit | None=None, name: str | None=None, copy: _Boolean=False, tz: _Zone=None, default: _DateValue=None, yearfirst: _Boolean | None=None, dayfirst: _Boolean | None=None, isoformat: _Boolean=True, strict: _Boolean=False, cfg: Configs | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:
        """Parse supported native data into a Pldt without a Python row UDF.

        Parameters
        ----------
        unit : {"ms", "us", "ns"} or None
            Without a unit, text uses us for up to six fractional digits and ns for seven
            through nine, even if the additional digits are zero. An explicit unit is lossless.
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
        cls = type(self._series) if isinstance(self._series, Pldt) else Pldt
        try:
            return cls(self._series, unit=unit, name=name, copy=copy, tz=tz,
                              default=default, yearfirst=yearfirst, dayfirst=dayfirst,
                              isoformat=isoformat, strict=strict, cfg=cfg,
                              ambiguous=ambiguous, nonexistent=nonexistent)

        except Exception as error:
            _raise_argument_context(error, "Pldt.parse", "arguments", None)

    def strptime(self, fmt: str, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, cfg: Configs | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:
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
        return Pldt.strptime(self._series, fmt, tz=tz, unit=unit, name=name, cfg=cfg,
                             ambiguous=ambiguous, nonexistent=nonexistent)

    def fromseconds(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:
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
        return _numeric_eager((type(self._series) if isinstance(self._series, Pldt) else Pldt), self._series, 'seconds', tz=tz, unit=unit, name=name, ambiguous=ambiguous, nonexistent=nonexistent, entry="Pldt.fromseconds")

    def frommicroseconds(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:
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
        return _numeric_eager((type(self._series) if isinstance(self._series, Pldt) else Pldt), self._series, 'micros', tz=tz, unit=unit, name=name, ambiguous=ambiguous, nonexistent=nonexistent, entry="Pldt.frommicroseconds")

    def fromtimestamp(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None) -> Pldt:
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
        return _numeric_eager((type(self._series) if isinstance(self._series, Pldt) else Pldt), self._series, ("local_timestamp" if tz is None else "timestamp"), tz=tz, unit=unit, name=name, entry="Pldt.fromtimestamp")

    def utcfromtimestamp(self, *, unit: _Unit | None=None, name: str | None=None) -> Pldt:
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
        return _numeric_eager((type(self._series) if isinstance(self._series, Pldt) else Pldt), self._series, 'utc_timestamp', tz=timezone.utc, unit=unit, name=name, entry="Pldt.utcfromtimestamp")

    def fromdate(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:
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
        return _date_factory((type(self._series) if isinstance(self._series, Pldt) else Pldt), self._series, "date", tz=tz, unit=unit, name=name,
                                  ambiguous=ambiguous, nonexistent=nonexistent)

    def fromdatetime(self, *, tz: _Zone=None, unit: _Unit | None=None, name: str | None=None, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:
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

        For Series.pldt.fromdatetime, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-factories.html#reader-series-datetime-source-zone
        """
        return _date_factory((type(self._series) if isinstance(self._series, Pldt) else Pldt), self._series, "datetime", tz=tz, unit=unit, name=name,
                                  ambiguous=ambiguous, nonexistent=nonexistent)

    def as_unit(self, unit: _Unit, round_ok: _Boolean=True) -> Pldt:
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
        return _as_unit(self._series, unit, round_ok, entry="Series.pldt.as_unit")

    def tz_localize(self, tz: _Zone, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:
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

        For Series.pldt.tz_localize, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-timezones.html#reader-series-timezone-choices
        """
        return _tz_eager(self._series, "localize", tz, ambiguous=ambiguous, nonexistent=nonexistent)

    def tz_convert(self, tz: _Zone) -> Pldt:
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

        For Series.pldt.tz_convert, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-timezones.html#reader-series-timezone-choices
        """
        return _tz_eager(self._series, "convert", tz)

    def astimezone(self, tz: _Zone=None, *, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:
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

        For Series.pldt.astimezone, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-timezones.html#reader-series-timezone-choices
        """
        return _tz_eager(self._series, "astimezone", tz, ambiguous=ambiguous, nonexistent=nonexistent)

    def tz_switch(self, targ_tz: _Zone, base_tz: _Zone=None, naive: _Boolean=False, *, ambiguous: _Ambiguous='raise', nonexistent: _Nonexistent='raise') -> Pldt:
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

        For Series.pldt.tz_switch, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/pldt-timezones.html#reader-series-timezone-choices
        """
        return _tz_eager(self._series, "switch", targ_tz, base_tz, naive, ambiguous, nonexistent)



class _ExprNamespace(_TransformMethods, _PeriodMethods, _QueryMethods, _OutputMethods):
    """Build native Polars expressions for rsTimes date operations.

    Import rstimes.pldt to register the accessor. Use the result in select
    or with_columns. Lazy queries evaluate it when you call collect.

    Examples
    --------
    >>> import polars as pl
    >>> import rstimes.pldt
    >>> frame = pl.DataFrame({"day": ["2024-02-29", None]})
    >>> expr = pl.col("day").pldt.parse(unit="us")
    >>> frame.lazy().select(expr.pldt.isoformat()).collect()["day"].to_list()
    ['2024-02-29T00:00:00', None]
    """

    def diff(self, dtobj: _DiffInput | pl.Expr, unit: str, absolute: _Boolean=False, inclusive: str='one') -> pl.Series | pl.Expr:
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
            Count boundaries with one, both or neither endpoint. Use this method on
            Series.pldt or Expr.pldt. Polars Series.diff compares adjacent rows.

        Returns
        -------
        pl.Series | pl.Expr
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
        return _boundary_difference(self, dtobj, unit, absolute, inclusive)

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

        For Expr.pldt.round, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-second-grid
        """
        return _period_operation(self, "round", None, freq, 0, False, "pldt.round")

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

        For Expr.pldt.ceil, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-second-grid
        """
        return _period_operation(self, "round", None, freq, 1, False, "pldt.ceil")

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

        For Expr.pldt.floor, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-boundaries.html#reader-expr-second-grid
        """
        return _period_operation(self, "round", None, freq, 2, False, "pldt.floor")

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

        For Expr.pldt.add_delta, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-calendar.html#expr-apply-concrete-delta
        """
        return _delta_expression(self._expr, delta, False)

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

        For Expr.pldt.sub_delta, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-calendar.html#reader-expr-subtract-delta
        """
        return _delta_expression(self._expr, delta, True)

    def replace(self, year: _ExprOptionalField=None, month: _ExprOptionalField=None, day: _ExprOptionalField=None, hour: _ExprOptionalField=None, minute: _ExprOptionalField=None, second: _ExprOptionalField=None, microsecond: _ExprOptionalField=None, nanosecond: _ExprOptionalField=None, tzinfo: _Zone=_UNCHANGED_ZONE, *, ambiguous: _ExprAmbiguous='raise', nonexistent: _Nonexistent='raise') -> pl.Expr:  # pyright: ignore[reportArgumentType] -- TY036; see tests/typing/pyright_exceptions.json.
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
        return _date_operation(self, "replace", (year, month, day, hour, minute, second, microsecond, nanosecond),
                               "pldt.replace", tzinfo=tzinfo, ambiguous=ambiguous, nonexistent=nonexistent)

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
        self._expr = expr

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

        For Expr.pldt.fromisoformat, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-inputs.html#reader-expr-iso-text
        """
        return _iso_expression(self._expr, tz=tz, unit=unit, ambiguous=ambiguous, nonexistent=nonexistent)

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

        For Expr.pldt.combine, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-inputs.html#reader-expr-combine-clock
        """
        return _combine_expression(self._expr, time, tz=tz, unit=unit,
                                    ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _calendar_expression("ordinal", (self._expr,), tz=tz, unit=unit,
                                    ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _calendar_expression("iso", (self._expr, week, weekday), tz=tz, unit=unit,
                                    ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _calendar_expression("doy", (self._expr, doy), tz=tz, unit=unit,
                                    ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _text_expression(self._expr, unit=unit, tz=tz, default=default,
                                yearfirst=yearfirst, dayfirst=dayfirst,
                                isoformat=isoformat, strict=strict, cfg=cfg,
                                ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _text_expression(self._expr, fmt=fmt, unit=unit, tz=tz, cfg=cfg,
                                ambiguous=ambiguous, nonexistent=nonexistent)

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
        return _numeric_expression(self._expr, 'seconds', tz=tz, unit=unit, ambiguous=ambiguous, nonexistent=nonexistent, entry="Pldt.fromseconds")

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
        return _numeric_expression(self._expr, 'micros', tz=tz, unit=unit, ambiguous=ambiguous, nonexistent=nonexistent, entry="Pldt.frommicroseconds")

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
        return _numeric_expression(self._expr, ("local_timestamp" if tz is None else "timestamp"), tz=tz, unit=unit, entry="Pldt.fromtimestamp")

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
        return _numeric_expression(self._expr, 'utc_timestamp', tz=timezone.utc, unit=unit, entry="Pldt.utcfromtimestamp")

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
        return _date_expression(self._expr, "date", tz=tz, unit=unit,
                                  ambiguous=ambiguous, nonexistent=nonexistent)

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

        For Expr.pldt.fromdatetime, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-inputs.html#reader-expr-datetime-source-zone
        """
        return _date_expression(self._expr, "datetime", tz=tz, unit=unit,
                                  ambiguous=ambiguous, nonexistent=nonexistent)

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
        unit = _unit(unit)
        round_ok = _bool_option(round_ok, "Expr.pldt.as_unit", "round_ok")
        return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_as_unit",
                                        args=[self._expr], kwargs={"version": 1, "unit": unit, "round_ok": round_ok}, is_elementwise=True)

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

        For Expr.pldt.tz_localize, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-timezones.html#reader-expr-timezone-choices
        """
        return _tz_expr(self._expr, "localize", tz, ambiguous=ambiguous, nonexistent=nonexistent)

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

        For Expr.pldt.tz_convert, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-timezones.html#reader-expr-timezone-choices
        """
        return _tz_expr(self._expr, "convert", tz)

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

        For Expr.pldt.astimezone, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-timezones.html#reader-expr-timezone-choices
        """
        return _tz_expr(self._expr, "astimezone", tz, ambiguous=ambiguous, nonexistent=nonexistent)

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

        For Expr.pldt.tz_switch, see
        https://aresjef.github.io/rsTimes/1.1.1/guides/expressions-timezones.html#reader-expr-timezone-choices
        """
        return _tz_expr(self._expr, "switch", targ_tz, base_tz, naive, ambiguous, nonexistent)



# Keep ordinary Python binding errors on public names without call wrappers.
_public_name, _public_item, _public_function = "", None, None
for _public_owner, _public_prefix in (
    (_TransformMethods, "Pldt"), (_PeriodMethods, "Pldt"),
    (_QueryMethods, "Pldt"), (_OutputMethods, "Pldt"),
    (_PythonOutputMethods, "Pldt"), (_TimezoneMetadata, "Pldt"),
    (_SeriesNamespace, "Pldt.pldt"), (_ExprNamespace, "Expr.pldt"),
):
    for _public_name, _public_item in vars(_public_owner).items():
        if _public_name.startswith("_"):
            continue
        _public_function = (_public_item.fget if isinstance(_public_item, property)
                            else _public_item.__func__ if isinstance(_public_item, (classmethod, staticmethod))
                            else _public_item)
        if _public_function is not None:
            _public_function.__qualname__ = _public_prefix + "." + _public_name
del _public_owner, _public_prefix, _public_name, _public_item, _public_function

if hasattr(pl.Series, "pldt") or hasattr(pl.Expr, "pldt"):
    raise RuntimeError("Cannot register rstimes.pldt: the Polars 'pldt' namespace is already occupied")

_BASE_NUMPY_EXPORT = Pldt.to_numpy
_state_register(Pldt)
_register_polars_base(Pldt)
pl.api.register_series_namespace("pldt")(_SeriesNamespace)
pl.api.register_expr_namespace("pldt")(_ExprNamespace)

__all__ = ["Pldt"]
