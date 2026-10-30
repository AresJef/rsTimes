"""Native Polars date columns and expression namespaces.

Column calculations share a Rust kernel. Loading this module explicitly enables
the official Series/Expr namespaces; the base rsTimes import does not require
Polars. The implementation is being expanded under the approved PLDT contract.
"""

from pathlib import Path
from collections.abc import Mapping
from datetime import date, timezone, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from ._optional import POLARS as pl, PANDAS as pd

if pl is None:
    raise ImportError('Pldt requires Polars; install "rstimes[polars]".')

from polars.plugins import register_plugin_function
from . import _native
from ._native import (_integer_arg, _bool_option, _pldt_execute, _pldt_native,
                      _pldt_objects, _pldt_register_missing, _pldt_policies, _pldt_timezone)
from .parser import Configs
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
                      _pldt_binary, _pldt_scalar_callback)
from ._pldt_timezone import prepare_timezone as _prepare_zone
from ._localization import local_timezone as _local_zone, resolve_timezone as _resolve_zone
from .errors import _own_error, _raise_argument_context, _external_error

if pd is not None:
    from ._range import frequency as _pandas_frequency, mature_units as _mature_units
else:
    _pandas_frequency = _mature_units = None

_PLUGIN_PATH = Path(_native.__file__)
_UNITS = ("ms", "us", "ns")
_PD_COLUMN = (pd.Series, pd.Index, pd.api.extensions.ExtensionArray) if pd is not None else ()
_PD_TABLE = (pd.DataFrame, pd.MultiIndex) if pd is not None else ()
_PD_DATETIME_ARRAY = pd.arrays.DatetimeArray if pd is not None else ()
_NUMPY_FLOAT_TYPES = (np.float16, np.float32, np.float64)
_NUMPY_DATE_CODES = {"Y": 0, "M": 1, "W": 2, "D": 4, "h": 5, "m": 6, "s": 7, "ms": 8, "us": 9, "ns": 10, "generic": 14}
_pldt_register_missing(pd.NA if pd is not None else None, pd.NaT if pd is not None else None)


def _unit(value, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise _own_error(TypeError("must be a string: 'ms', 'us' or 'ns'"), "unit", value)
    if value not in _UNITS:
        raise _own_error(ValueError("must be 'ms', 'us' or 'ns'; Polars has no Datetime(s)"), "unit", value)
    return value


def _name(value):
    if value is not None and not isinstance(value, str):
        raise _own_error(TypeError("must be a string or None"), "name", value)
    return value


def _base_array(value):
    """Normalize only layout/byte order; keep date unit and numeric roles."""
    value = np.asarray(value)
    if value.ndim != 1:
        raise ValueError("Pldt: data must be one-dimensional; zero/two-dimensional arrays are not flattened")
    if not value.dtype.isnative:
        value = value.astype(value.dtype.newbyteorder("="))
    return np.ascontiguousarray(value)


def _zone_key(zone):
    if zone is None:
        return None
    if isinstance(zone, ZoneInfo):
        return zone.key
    if isinstance(zone, timezone):
        seconds = zone.utcoffset(None).total_seconds()
        if seconds == 0:
            return "UTC"
        if seconds % 3600 == 0:
            return "Etc/GMT" + ("-" if seconds > 0 else "+") + str(abs(int(seconds)) // 3600)
    raise TypeError("Pldt: this source timezone cannot be represented by Polars; select a supported target tz")


def _construct(data, *, unit, name, copy, default, yearfirst, dayfirst, isoformat, strict, cfg, tz, policy):
    """Read source roles once, then produce one native result carrier."""
    if isinstance(data, (str, bytes, bytearray, date, Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame, pl.Expr) + _PD_TABLE) or data is None:
        raise TypeError("Pldt: data must be a one-dimensional date collection; use [value] for one date")
    source_name = None
    source_zone = None
    base_unit = None
    if isinstance(data, _PD_COLUMN):
        source_name = getattr(data, "name", None)
        selected_name = name if name is not None else _name(source_name) or ""
        if isinstance(data, (pd.Series, pd.Index)):
            data = data.array
        if isinstance(data, _PD_DATETIME_ARRAY):
            source_zone = ("UTC" if tz is not None else _zone_key(data.tz)) if data.tz is not None else None
            array = _base_array(data.asi8)
            code = _NUMPY_DATE_CODES[data.unit]
            carrier = pl.Series(selected_name, array)
            return _pldt_native(carrier, pl.Series, unit, copy, False, (code, 1), source_zone, tz, policy).rename(name if name is not None else _name(source_name) or "")
        if getattr(data.dtype, "kind", None) in ("i", "u", "f"):
            if data.dtype.kind == "f" and data.dtype.type not in _NUMPY_FLOAT_TYPES:
                raise TypeError("Pldt: only actual NumPy float16/32/64 dtypes are supported numeric ticks")
            base_unit = "ns"
        elif getattr(data.dtype, "kind", None) in ("b", "m", "V", "c", "S"):
            raise TypeError("Pldt: this declared pandas dtype does not contain dates or supported numeric ticks")
    if isinstance(data, np.ndarray):
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
    if isinstance(data, pl.Series):
        data = pl.Series(data)  # Independent shell; retain typed native owner/chunks.
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


def _text_eager(source, unit, tz, policy, default=None, yearfirst=None,
                dayfirst=None, isoformat=True, strict=False, cfg=None, formatted=None):
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


def _text_expression(source, *, unit=None, tz=None, default=None, yearfirst=None,
                     dayfirst=None, isoformat=True, strict=False, cfg=None,
                     ambiguous="raise", nonexistent="raise", fmt=None):
    entry = "Pldt.parse" if fmt is None else "Pldt.strptime"
    try:
        target = _prepare_zone(tz)
        policy, mask, scalar = _timezone_policy(ambiguous, nonexistent, expression=True)
        if fmt is None:
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


def _strptime_eager(data, fmt, *, size=None, tz=None, unit=None, name=None,
                    cfg=None, ambiguous="raise", nonexistent="raise"):
    try:
        unit = _unit(unit, optional=True)
        name = _name(name)
        if name is None and isinstance(data, (pl.Series,) + _PD_COLUMN):
            name = _name(getattr(data, "name", None))
        compiled = _prepare_format(fmt)
        target = _prepare_zone(tz)
        policy, _, _ = _timezone_policy(ambiguous, nonexistent, expression=False)
        scalar = isinstance(data, (str, bytes, bytearray, date, int, float, np.generic)) or data is None or (pd is not None and (data is pd.NA or data is pd.NaT))
        if scalar:
            if size is None:
                raise _own_error(ValueError("a scalar strptime input requires size"), "size", size)
            size = _integer_arg(size, "Pldt.strptime", "size")
            if size < 0:
                raise _own_error(ValueError("size must be nonnegative"), "size", size)
        elif size is not None:
            raise _own_error(ValueError("omit size for a collection"), "size", size)
        if isinstance(data, pl.Series) and data.dtype.base_type() in (pl.String, pl.Null):
            source = pl.Series(data)
            if source.dtype == pl.Null:
                source = source.cast(pl.String)
            context = _pldt_prepare_format(compiled, cfg)
            result = _text_eager(source, unit, target, policy, formatted=context)
            return result.rename(name if name is not None else source.name)
        if isinstance(data, (Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame, pl.Expr) + _PD_TABLE):
            raise _own_error(TypeError("strptime requires text or a one-dimensional text collection"), "dtstr", data)
        if isinstance(data, pl.Series) and data.dtype.base_type() is not pl.Object:
            raise _own_error(TypeError("strptime requires a String or text Object column"), "dtstr", data)
        if isinstance(data, _PD_COLUMN) and getattr(data.dtype, "kind", None) not in ("O", "U"):
            raise _own_error(TypeError("strptime requires text values, not a numeric/date dtype"), "dtstr", data)
        if isinstance(data, np.ndarray):
            data = _base_array(data)
            if data.dtype.kind not in ("O", "U"):
                raise _own_error(TypeError("strptime requires text values, not a numeric/date dtype"), "dtstr", data)
        result = _pldt_format_objects(data, pl.Series, compiled, unit, target, policy,
                                       cfg, size, name or "")
        return result
    except Exception as error:
        _raise_argument_context(error, "Pldt.strptime", "arguments", None)


def _size(value, entry):
    value = _integer_arg(value, entry, "size")
    if value < 0:
        raise _own_error(ValueError("must be nonnegative"), "size", value)
    return value


def _clock_factory(cls, size, tz, unit, name, entry, naive):
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


def _numeric_eager(cls, data, kind, *, size=None, tz=None, unit=None, name=None,
                   ambiguous="raise", nonexistent="raise", entry):
    try:
        unit = _unit(unit, optional=True)
        name = _name(name)
        size = None if size is None else _size(size, entry)
        target_zone = _prepare_zone(tz)
        policy, _, _ = _timezone_policy(ambiguous, nonexistent, expression=False)
        if isinstance(data, (Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame, pl.Expr) + _PD_TABLE):
            raise _own_error(TypeError("requires a numeric scalar or one-dimensional numeric collection"), "data", data)
        column = False
        source_name = None
        if isinstance(data, _PD_COLUMN):
            source_name = getattr(data, "name", None)
            column = True
            if getattr(data.dtype, "kind", None) in ("M", "m", "b", "c", "S", "V"):
                raise _own_error(TypeError("this declared dtype is not numeric epoch input"), "data", data)
            if isinstance(data, (pd.Series, pd.Index)):
                data = data.array
        if isinstance(data, np.ndarray):
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
        target = Pldt if cls is Pldt else pl.Series
        local = _local_zone if kind == "local_timestamp" else None
        if isinstance(data, pl.Series):
            if size is not None:
                raise _own_error(ValueError("omit size for a collection"), "size", size)
            source = pl.Series(data)
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
                        ambiguous="raise", nonexistent="raise", entry):
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


def _range_factory(cls, start=None, *, end=None, periods=None, freq=None, tz=None,
                   normalize=False, inclusive="both", unit=None, name=None, default=None,
                   yearfirst=None, dayfirst=None, isoformat=True, strict=False, cfg=None,
                   ambiguous="raise", nonexistent="raise"):
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
        if cfg is not None and not isinstance(cfg, Configs):
            raise _own_error(TypeError("must be Configs or None"), "cfg", cfg)
        if not isinstance(inclusive, str):
            raise _own_error(TypeError("must be both/left/right/neither"), "inclusive", inclusive)
        if inclusive not in ("both", "left", "right", "neither"):
            raise _own_error(ValueError("must be both/left/right/neither"), "inclusive", inclusive)
        policy, _, _ = _timezone_policy(ambiguous, nonexistent, expression=False)
        target = _prepare_zone(tz)
        if freq is None and (start is None or end is None or periods is None):
            freq = "D"
        metadata = None
        delegated = False
        if freq is None:
            plan = None
        elif pd is not None and isinstance(freq, pd.DateOffset) and not isinstance(freq, timedelta):
            plan, metadata, delegated = _pandas_frequency(freq)
        else:
            plan = _pldt_frequency(freq)
            delegated = plan is None
            if delegated:
                if pd is None:
                    raise ImportError("this special date_range rule requires optional pandas; install rstimes[pandas]")
                plan, metadata, delegated = _pandas_frequency(freq)
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
            generation_unit, minimum_unit = _mature_units(metadata, inputs.unit, carrier_unit)
            if generation_unit is not None:
                units = ("s", "ms", "us", "ns")
                generation_unit = units[max(units.index(generation_unit), units.index(carrier_unit))]
            try:
                external = pd.date_range(start=first, end=last, periods=periods, freq=metadata,
                                         unit=generation_unit, inclusive="both")
            except Exception as error:
                raise _external_error(error)
            carrier = pl.Series("", _base_array(external.asi8))
            result = _pldt_range_external(output, inputs, carrier, external.unit, policy, inclusive,
                                         unit or minimum_unit, unit is None and minimum_unit is not None, name or "")
        return result if cls is Pldt else cls(result)
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


def _iso_factory(cls, data, *, size=None, tz=None, unit=None, name=None,
                 ambiguous="raise", nonexistent="raise"):
    try:
        unit = _unit(unit, optional=True)
        size = None if size is None else _size(size, "Pldt.fromisoformat")
        name = _name(name)
        target = _prepare_zone(tz)
        policy, _, _ = _timezone_policy(ambiguous, nonexistent, expression=False)
        if isinstance(data, (Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame, pl.Expr) + _PD_TABLE):
            raise _own_error(TypeError("requires ISO text or a one-dimensional text collection"), "dtstr", data)
        output = Pldt if cls is Pldt else pl.Series
        column = isinstance(data, _PD_COLUMN)
        source_name = _name(getattr(data, "name", None)) if column else None
        if isinstance(data, np.ndarray):
            data = _base_array(data)
            column = True
        if isinstance(data, pl.Series):
            if size is not None:
                raise _own_error(ValueError("omit size for a collection"), "size", size)
            data = pl.Series(data)
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


def _iso_expression(source, *, tz=None, unit=None, ambiguous="raise", nonexistent="raise"):
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


def _date_factory(cls, data, kind, *, size=None, tz=None, unit=None, name=None,
                  ambiguous="raise", nonexistent="raise"):
    entry = "Pldt." + {"date": "fromdate", "datetime": "fromdatetime", "numpy": "fromdatetime64"}[kind]
    try:
        unit = _unit(unit, optional=True)
        name = _name(name)
        size = None if size is None else _size(size, entry)
        zone = _prepare_zone(tz)
        policy, _, _ = _timezone_policy(ambiguous, nonexistent, expression=False)
        if isinstance(data, (Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame, pl.Expr) + _PD_TABLE):
            raise _own_error(TypeError("requires a real date source or one-dimensional date collection"), "data", data)
        target = Pldt if cls is Pldt else pl.Series
        column = False
        source_name = None
        if isinstance(data, _PD_COLUMN):
            if kind == "numpy":
                raise _own_error(TypeError("fromdatetime64 requires real NumPy datetime64 sources"), "dt64", data)
            source_name = getattr(data, "name", None)
            column = True
            if isinstance(data, (pd.Series, pd.Index)):
                data = data.array
            if isinstance(data, _PD_DATETIME_ARRAY):
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
                        rule = _prepare_zone(source_zone)
                    carrier = pl.Series(name if name is not None else _name(source_name) or "", _base_array(data.asi8))
                    result = _pldt_date_buffer(carrier, target, kind, _NUMPY_DATE_CODES[data.unit], rule,
                                               offset, unit, zone, policy)
                    return result if cls is Pldt else cls(result)
        if isinstance(data, np.ndarray):
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
        if isinstance(data, pl.Series):
            if kind == "numpy":
                raise _own_error(TypeError("fromdatetime64 requires a real NumPy source, not Polars"), "dt64", data)
            if size is not None:
                raise _own_error(ValueError("omit size for a collection"), "size", size)
            source = pl.Series(data)
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


def _date_expression(source, kind, *, tz=None, unit=None, ambiguous="raise", nonexistent="raise"):
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


def _part_source(value, clock, keep_zone):
    """Own one date/clock role without constructing an intermediate Pldt."""
    parameter = "time" if clock else "date"
    if isinstance(value, (Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame, pl.Expr) + _PD_TABLE):
        raise _own_error(TypeError("requires a scalar or one-dimensional date/clock collection"), parameter, value)
    column = False
    name = None
    if isinstance(value, _PD_COLUMN):
        name = getattr(value, "name", None)
        column = True
        if isinstance(value, (pd.Series, pd.Index)):
            value = value.array
        if isinstance(value, _PD_DATETIME_ARRAY):
            source_zone = _resolve_zone(value.tz)
            if source_zone is None or isinstance(source_zone, (timezone, ZoneInfo)):
                rule, offset = None, None
                if isinstance(source_zone, timezone):
                    delta = source_zone.utcoffset(None)
                    offset = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
                elif source_zone is not None:
                    rule = _prepare_zone(source_zone)
                carrier = pl.Series("", _base_array(value.asi8))
                return _pldt_parts_buffer(carrier, clock, _NUMPY_DATE_CODES[value.unit], 1,
                                          rule, offset, keep_zone), _name(name)
    if isinstance(value, np.ndarray):
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
    if isinstance(value, pl.Series):
        value = pl.Series(value)
        name = value.name
        column = True
        if value.dtype.base_type() is pl.Time and clock:
            return _pldt_parts_time(value.to_physical()), _name(name)
        if value.dtype.base_type() is not pl.Object:
            return _pldt_parts_column(value, clock, keep_zone), _name(name)
    return _pldt_parts_objects(value, _resolve_zone, clock, column, keep_zone), _name(name)


def _combine_factory(cls, date, time, *, size=None, tz=None, unit=None, name=None,
                     ambiguous="raise", nonexistent="raise"):
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


def _combine_expression(source, time=None, *, tz=None, unit=None, ambiguous="raise", nonexistent="raise"):
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
    if isinstance(value, (Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame, pl.Expr) + _PD_TABLE):
        raise _own_error(TypeError("requires an integer scalar or one-dimensional integer collection"), parameter, value)
    column = False
    source_name = None
    if isinstance(value, _PD_COLUMN):
        source_name = _name(getattr(value, "name", None))
        column = True
    if isinstance(value, np.ndarray):
        value = _base_array(value)
        column = True
        if value.dtype.kind in "iufb":
            if value.dtype.kind == "f" and value.dtype.type not in _NUMPY_FLOAT_TYPES:
                raise _own_error(TypeError("extended floating dtypes are not integer components"), parameter, value)
            value = pl.Series("", value.astype(np.float32) if value.dtype == np.dtype("float16") else value)
    if isinstance(value, pl.Series):
        column = True
        value = pl.Series(value)
        if value.dtype.base_type() is not pl.Object:
            return _pldt_integer_column(value), False
    source, scalar = _pldt_integer_objects(value, column, entry, parameter)
    return source.rename(source_name or ""), scalar


def _calendar_factory(cls, kind, components, *, size=None, tz=None, unit="us", name=None,
                      ambiguous="raise", nonexistent="raise"):
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


def _calendar_expression(kind, components, *, tz=None, unit="us", ambiguous="raise", nonexistent="raise"):
    entry = "Pldt." + {"ordinal": "fromordinal", "iso": "fromisocalendar", "doy": "fromdayofyear"}[kind]
    try:
        unit = _unit(unit)
        target = _prepare_zone(tz)
        policy, mask, mask_scalar = _timezone_policy(ambiguous, nonexistent, expression=True)
        labels = {"ordinal": ("ordinal",), "iso": ("year", "week", "weekday"), "doy": ("year", "doy")}[kind]
        args, scalars = [], []
        for value, label in zip(components, labels):
            if isinstance(value, pl.Expr):
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


def _as_unit(source, unit, round_ok):
    if source.dtype.base_type() not in (pl.Date, pl.Datetime):
        raise _own_error(TypeError("as_unit requires a Date/Datetime source"), "data", source)
    unit = _unit(unit)
    round_ok = _bool_option(round_ok, "Pldt.as_unit", "round_ok")
    target = type(source) if isinstance(source, Pldt) else Pldt
    if target is Pldt:
        return _pldt_native(source, Pldt, unit, False, round_ok)
    return target(_pldt_native(source, pl.Series, unit, False, round_ok))



def _timezone_policy(ambiguous, nonexistent, *, expression):
    if isinstance(ambiguous, pl.Expr):
        if not expression:
            raise _own_error(TypeError("ambiguous Expr is only valid in an Expr call"), "ambiguous", ambiguous)
        return _pldt_policies("raise", nonexistent, True), ambiguous, ambiguous.meta.is_scalar()
    if isinstance(ambiguous, np.ndarray):
        if ambiguous.ndim != 1:
            raise _own_error(ValueError("ambiguous must be one-dimensional"), "ambiguous", ambiguous)
        if ambiguous.dtype.kind != "b":
            raise _own_error(TypeError("ambiguous array must have Boolean dtype"), "ambiguous", ambiguous)
    if isinstance(ambiguous, (pl.DataFrame, pl.LazyFrame, Mapping, set, frozenset) + _PD_TABLE):
        raise _own_error(TypeError("ambiguous must be one boolean policy or a one-dimensional boolean collection"), "ambiguous", ambiguous)
    if isinstance(ambiguous, pl.Series) and ambiguous.dtype != pl.Boolean:
        raise _own_error(TypeError("ambiguous Series must have Boolean dtype"), "ambiguous", ambiguous)
    return _pldt_policies(ambiguous, nonexistent), None, False


def _tz_eager(source, operation, tz, base_tz=None, naive=False, ambiguous="raise", nonexistent="raise"):
    entry = "Pldt." + {"localize": "tz_localize", "convert": "tz_convert", "switch": "tz_switch", "astimezone": "astimezone"}[operation]
    try:
        naive = _bool_option(naive, entry, "naive")
        policy, _, _ = _timezone_policy(ambiguous, nonexistent, expression=False)
        receiver = pl.Series(source)
        dtype = receiver.dtype
        if dtype.base_type() not in (pl.Date, pl.Datetime):
            raise _own_error(TypeError("source must be a Date/Datetime column"), "data", source)
        source_aware = dtype.base_type() == pl.Datetime and dtype.time_zone is not None
        target = _prepare_zone(_local_zone() if operation == "astimezone" and tz is None else tz)
        base = None
        if operation == "astimezone" and not source_aware:
            base = target if tz is None else _prepare_zone(_local_zone())
        elif operation == "switch" and tz is not None and not source_aware and base_tz is not None:
            base = _prepare_zone(base_tz)
        cls = type(source) if isinstance(source, Pldt) else Pldt
        if cls is Pldt:
            return _pldt_timezone(receiver, Pldt, operation, target, base, policy, naive)
        return cls(_pldt_timezone(receiver, pl.Series, operation, target, base, policy, naive))
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


def _tz_expr(source, operation, tz, base_tz=None, naive=False, ambiguous="raise", nonexistent="raise"):
    entry = "Pldt." + {"localize": "tz_localize", "convert": "tz_convert", "switch": "tz_switch", "astimezone": "astimezone"}[operation]
    try:
        naive = _bool_option(naive, entry, "naive")
        policy, mask, scalar = _timezone_policy(ambiguous, nonexistent, expression=True)
        target = _prepare_zone(_local_zone() if operation == "astimezone" and tz is None else tz)
        # Expr has no input schema yet. Static required fallbacks are frozen now;
        # actual aware execution never reinterprets the source or uses base rules.
        base = None
        if operation == "astimezone":
            base = target if tz is None else _prepare_zone(_local_zone())
        elif operation == "switch" and tz is not None and base_tz is not None:
            base = _prepare_zone(base_tz)
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



def _expr(source, operation, argument=0, operand=None, scalar=False):
    """Build an official plugin expression with owned, versioned kwargs."""
    args = [source] if operand is None else [source, operand]
    return register_plugin_function(
        plugin_path=_PLUGIN_PATH,
        function_name="pldt_execute",
        args=args,
        kwargs={"version": 1, "operation": operation, "argument": argument, "scalar": scalar},
        is_elementwise=operand is None,
    )


def _eager(source, operation, argument=0, operand=None, scalar=False):
    target = pl.Series if operation == "is_month" else type(source) if isinstance(source, Pldt) else Pldt
    if target not in (pl.Series, Pldt):
        return target(_pldt_execute(source, pl.Series, operation, argument, operand, scalar))
    return _pldt_execute(source, target, operation, argument, operand, scalar)


_UNCHANGED_ZONE = object()
_FIELD_NAMES = ("year", "month", "day", "hour", "minute", "second", "microsecond", "nanosecond")
_INCREMENT_NAMES = ("years", "quarters", "months", "weeks", "days", "hours", "minutes", "seconds", "milliseconds", "microseconds", "nanoseconds")
_FIELD_RANGES = ((None, None), (1, 12), (1, 31), (0, 23), (0, 59), (0, 59), (0, 999999), (0, 999))


def _component(value, entry, parameter, optional, names, low, high):
    """Read a modification parameter once, preserving None and owning literals."""
    if isinstance(value, (Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame, pl.Expr) + _PD_TABLE):
        raise _own_error(TypeError("requires a scalar or one-dimensional field collection"), parameter, value)
    column = isinstance(value, _PD_COLUMN)
    if isinstance(value, np.ndarray):
        value = _base_array(value)
        column = True
        if value.dtype.kind in "iu":
            value = pl.Series(parameter, value)
        elif value.dtype.kind in "US" and names:
            value = pl.Series(parameter, value)
        elif value.dtype.kind != "O":
            raise _own_error(TypeError("requires integer fields, not Boolean or floating dtype"), parameter, value)
    if isinstance(value, _PD_COLUMN):
        kind = getattr(value.dtype, "kind", None)
        if kind not in ("i", "u", "O", "U", "T"):
            raise _own_error(TypeError("requires integer fields or supported selector names"), parameter, value)
    if isinstance(value, pl.Series):
        value = pl.Series(value)
        column = True
        if value.dtype.base_type() is not pl.Object:
            return _pldt_component_column(value, (optional, names, low, high), entry, parameter), False
    return _pldt_component_objects(value, column, (optional, names, low, high), entry, parameter)


def _transform_roles(kind):
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


def _date_operation(owner, kind, components, method, *, tzinfo=_UNCHANGED_ZONE,
                    ambiguous="raise", nonexistent="raise"):
    """Prepare roles once and enter one native Series/Expr calendar kernel."""
    entry = "Pldt." + method
    try:
        expression = isinstance(owner, _ExprNamespace)
        source = owner._expr if expression else pl.Series(owner._series if isinstance(owner, _SeriesNamespace) else owner)
        replace_zone = tzinfo is not _UNCHANGED_ZONE
        target = _prepare_zone(tzinfo) if replace_zone else None
        if kind == "replace":
            policy, mask, mask_scalar = _timezone_policy(ambiguous, nonexistent, expression=expression)
        else:
            policy, mask, mask_scalar = None, None, False
        args, scalars = [], []
        for value, role in zip(components, _transform_roles(kind)):
            if isinstance(value, pl.Expr):
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
            return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_transform",
                                            args=[source, *args], kwargs=options, is_elementwise=False)
        cls = type(owner._series) if isinstance(owner, _SeriesNamespace) and isinstance(owner._series, Pldt) else type(owner) if isinstance(owner, Pldt) else Pldt
        result = _pldt_transform(source, args, scalars, Pldt if cls is Pldt else pl.Series,
                                kind, entry, target, replace_zone, policy)
        return result if cls is Pldt else cls(result)
    except Exception as error:
        _raise_argument_context(error, entry, "arguments", None)


def _prepare_arithmetic(other, entry, subtract, reflected=False, named=False):
    """Read real temporal metadata without extracting Python date scalars."""
    if isinstance(other, (pl.Expr, Mapping, set, frozenset, pl.DataFrame, pl.LazyFrame) + _PD_TABLE):
        if named:
            raise _own_error(TypeError("requires actual Delta values or a one-dimensional Delta collection; dynamic Expr operands are unsupported"), "delta", other)
        return None
    column = False
    if isinstance(other, _PD_COLUMN):
        column = True
        array = other.array if isinstance(other, (pd.Series, pd.Index)) else other
        if isinstance(array, (pd.arrays.DatetimeArray, pd.arrays.TimedeltaArray)):
            storage = "M" if isinstance(array, pd.arrays.DatetimeArray) else "m"
            if named:
                raise _own_error(TypeError("requires actual Delta values"), "delta", other)
            unit = array.unit
            data = _base_array(array.asi8)
            return _pldt_operand_ticks(pl.Series("", data), storage, _NUMPY_DATE_CODES[unit], 1,
                                       storage == "M" and array.tz is not None, True)
        other = array
    if isinstance(other, np.ndarray):
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
    if isinstance(other, pl.Series):
        other = pl.Series(other)
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
    source = pl.Series(actual)
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
                                        is_elementwise=False)
    except Exception as error:
        _raise_argument_context(error, entry, "delta", delta)


class _TransformMethods:
    """Date operations shared by Pldt and the two native namespaces."""
    def to_datetime(self, year=None, month=None, day=None, hour=None, minute=None, second=None, microsecond=None, nanosecond=None):
        """Merge legal fields once; fit a legal day intent to the final month."""
        return _date_operation(self, "adjust", (year, month, day, hour, minute, second, microsecond, nanosecond), "to_datetime")

    def to_date(self, year=None, month=None, day=None):
        """Merge legal fields once; fit a legal day intent to the final month."""
        return _date_operation(self, "adjust", (year, month, day, None, None, None, None, None), "to_date")

    def to_time(self, hour=None, minute=None, second=None, microsecond=None, nanosecond=None):
        """Merge legal fields once; fit a legal day intent to the final month."""
        return _date_operation(self, "adjust", (None, None, None, hour, minute, second, microsecond, nanosecond), "to_time")

    def to_year(self, offset, month=None, day=None):
        """Move local calendar periods, retaining precision and fitting month end."""
        return _date_operation(self, "year", (offset, month, day), "to_year")

    def to_quarter(self, offset, month=None, day=None):
        """Move local calendar periods, retaining precision and fitting month end."""
        return _date_operation(self, "quarter", (offset, month, day), "to_quarter")

    def to_month(self, offset, day=None):
        """Move local calendar periods, retaining precision and fitting month end."""
        return _date_operation(self, "month", (offset, day), "to_month")

    def to_weekday(self, offset, weekday=None):
        """Move local calendar periods, retaining precision and fitting month end."""
        return _date_operation(self, "weekday", (offset, weekday), "to_weekday")

    def to_day(self, offset):
        """Move local calendar periods, retaining precision and fitting month end."""
        return _date_operation(self, "day", (offset, ), "to_day")

    def to_curr_year(self, month=None, day=None):
        """Select the calendar period directly through the shared native kernel."""
        return _date_operation(self, "year", (0, month, day), "to_curr_year")

    def to_prev_year(self, month=None, day=None):
        """Select the calendar period directly through the shared native kernel."""
        return _date_operation(self, "year", (-1, month, day), "to_prev_year")

    def to_next_year(self, month=None, day=None):
        """Select the calendar period directly through the shared native kernel."""
        return _date_operation(self, "year", (1, month, day), "to_next_year")

    def to_curr_quarter(self, month=None, day=None):
        """Select the calendar period directly through the shared native kernel."""
        return _date_operation(self, "quarter", (0, month, day), "to_curr_quarter")

    def to_prev_quarter(self, month=None, day=None):
        """Select the calendar period directly through the shared native kernel."""
        return _date_operation(self, "quarter", (-1, month, day), "to_prev_quarter")

    def to_next_quarter(self, month=None, day=None):
        """Select the calendar period directly through the shared native kernel."""
        return _date_operation(self, "quarter", (1, month, day), "to_next_quarter")

    def to_curr_month(self, day=None):
        """Select the calendar period directly through the shared native kernel."""
        return _date_operation(self, "month", (0, day), "to_curr_month")

    def to_prev_month(self, day=None):
        """Select the calendar period directly through the shared native kernel."""
        return _date_operation(self, "month", (-1, day), "to_prev_month")

    def to_next_month(self, day=None):
        """Select the calendar period directly through the shared native kernel."""
        return _date_operation(self, "month", (1, day), "to_next_month")

    def to_curr_weekday(self, weekday=None):
        """Select the calendar period directly through the shared native kernel."""
        return _date_operation(self, "weekday", (0, weekday), "to_curr_weekday")

    def to_prev_weekday(self, weekday=None):
        """Select the calendar period directly through the shared native kernel."""
        return _date_operation(self, "weekday", (-1, weekday), "to_prev_weekday")

    def to_next_weekday(self, weekday=None):
        """Select the calendar period directly through the shared native kernel."""
        return _date_operation(self, "weekday", (1, weekday), "to_next_weekday")

    def to_monday(self):
        """Select this week's monday, using Monday as day zero."""
        return _date_operation(self, "weekday", (0, 0), "to_monday")

    def to_tuesday(self):
        """Select this week's tuesday, using Monday as day zero."""
        return _date_operation(self, "weekday", (0, 1), "to_tuesday")

    def to_wednesday(self):
        """Select this week's wednesday, using Monday as day zero."""
        return _date_operation(self, "weekday", (0, 2), "to_wednesday")

    def to_thursday(self):
        """Select this week's thursday, using Monday as day zero."""
        return _date_operation(self, "weekday", (0, 3), "to_thursday")

    def to_friday(self):
        """Select this week's friday, using Monday as day zero."""
        return _date_operation(self, "weekday", (0, 4), "to_friday")

    def to_saturday(self):
        """Select this week's saturday, using Monday as day zero."""
        return _date_operation(self, "weekday", (0, 5), "to_saturday")

    def to_sunday(self):
        """Select this week's sunday, using Monday as day zero."""
        return _date_operation(self, "weekday", (0, 6), "to_sunday")

    def to_yesterday(self):
        """Move one local calendar day, retaining clock and nanoseconds."""
        return _date_operation(self, "day", (-1,), "to_yesterday")

    def to_tomorrow(self):
        """Move one local calendar day, retaining clock and nanoseconds."""
        return _date_operation(self, "day", (1,), "to_tomorrow")

    def add(self, years=0, quarters=0, months=0, weeks=0, days=0, hours=0, minutes=0, seconds=0, milliseconds=0, microseconds=0, nanoseconds=0):
        """Combine integer calendar increments before final precision/capacity checks."""
        return _date_operation(self, "add", (years, quarters, months, weeks, days, hours, minutes, seconds, milliseconds, microseconds, nanoseconds), "add")

    def sub(self, years=0, quarters=0, months=0, weeks=0, days=0, hours=0, minutes=0, seconds=0, milliseconds=0, microseconds=0, nanoseconds=0):
        """Combine integer calendar increments before final precision/capacity checks."""
        return _date_operation(self, "sub", (years, quarters, months, weeks, days, hours, minutes, seconds, milliseconds, microseconds, nanoseconds), "sub")


class Pldt(_TransformMethods, pl.Series):
    """A true Polars Datetime Series with native calendar operations.

    Args:
        data: One-dimensional supported date data. Native metadata, precision
            and independent validity are retained; generators are read once.
        unit: Optional target resolution, one of ``ms``, ``us`` or ``ns``.
        name: Optional output column name; otherwise retain the source name.

    Construction chooses a resolution once. Ordinary operations keep it;
    ``as_unit`` is the explicit operation that may reduce precision.
    """

    def __init__(self, data, *, unit=None, name=None, copy=False,
                 default=None, yearfirst=None, dayfirst=None, isoformat=True,
                 strict=False, cfg=None, tz=None, ambiguous="raise", nonexistent="raise"):
        try:
            unit = _unit(unit, optional=True)
            name = _name(name)
            copy = _bool_option(copy, "Pldt", "copy")
            isoformat = _bool_option(isoformat, "Pldt", "isoformat")
            strict = _bool_option(strict, "Pldt", "strict")
            yearfirst = None if yearfirst is None else _bool_option(yearfirst, "Pldt", "yearfirst")
            dayfirst = None if dayfirst is None else _bool_option(dayfirst, "Pldt", "dayfirst")
            if cfg is not None and not isinstance(cfg, Configs):
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
    def parse(cls, data, *, unit=None, name=None, copy=False, tz=None, default=None,
              yearfirst=None, dayfirst=None, isoformat=True, strict=False, cfg=None,
              ambiguous="raise", nonexistent="raise"):
        """Construct a date column through the same shared native input rules."""
        try:
            return cls(data, unit=unit, name=name, copy=copy, tz=tz, default=default,
                       yearfirst=yearfirst, dayfirst=dayfirst, isoformat=isoformat,
                       strict=strict, cfg=cfg, ambiguous=ambiguous, nonexistent=nonexistent)

        except Exception as error:
            _raise_argument_context(error, "Pldt.parse", "arguments", None)

    @classmethod
    def strptime(cls, dtstr, fmt, *, size=None, tz=None, unit=None, name=None,
                 cfg=None, ambiguous="raise", nonexistent="raise"):
        """Match a shared explicit format; scalar text requires size."""
        return cls(_strptime_eager(dtstr, fmt, size=size, tz=tz, unit=unit, name=name,
                                  cfg=cfg, ambiguous=ambiguous, nonexistent=nonexistent))

    @classmethod
    def now(cls, size, *, tz=None, unit=None, name=None):
        """Repeat one current instant, or its local naive clock when tz is None."""
        return _clock_factory(cls, size, tz, unit, name, "Pldt.now", tz is None)

    @classmethod
    def today(cls, size, *, unit=None, name=None):
        """Repeat the current full local clock; this does not normalize midnight."""
        return _clock_factory(cls, size, None, unit, name, "Pldt.today", True)

    @classmethod
    def utcnow(cls, size, *, unit=None, name=None):
        """Repeat one current true instant with UTC metadata and real precision."""
        return _clock_factory(cls, size, timezone.utc, unit, name, "Pldt.utcnow", False)

    @classmethod
    def fromseconds(cls, seconds, *, size=None, tz=None, unit=None, name=None, ambiguous="raise", nonexistent="raise"):
        """Read the fixed input quantity and construct one native date column."""
        return _numeric_eager(cls, seconds, 'seconds', size=size, tz=tz, unit=unit,
                              name=name, ambiguous=ambiguous, nonexistent=nonexistent, entry="Pldt.fromseconds")

    @classmethod
    def frommicroseconds(cls, us, *, size=None, tz=None, unit=None, name=None, ambiguous="raise", nonexistent="raise"):
        """Read the fixed input quantity and construct one native date column."""
        return _numeric_eager(cls, us, 'micros', size=size, tz=tz, unit=unit,
                              name=name, ambiguous=ambiguous, nonexistent=nonexistent, entry="Pldt.frommicroseconds")

    @classmethod
    def fromtimestamp(cls, ts, *, size=None, tz=None, unit=None, name=None):
        """Read the fixed input quantity and construct one native date column."""
        return _numeric_eager(cls, ts, ("local_timestamp" if tz is None else "timestamp"), size=size, tz=tz, unit=unit,
                              name=name, entry="Pldt.fromtimestamp")

    @classmethod
    def utcfromtimestamp(cls, ts, *, size=None, unit=None, name=None):
        """Read the fixed input quantity and construct one native date column."""
        return _numeric_eager(cls, ts, 'utc_timestamp', size=size, tz=timezone.utc, unit=unit,
                              name=name, entry="Pldt.utcfromtimestamp")

    @classmethod
    def fromdate(cls, dt, *, size=None, tz=None, unit=None, name=None,
                 ambiguous="raise", nonexistent="raise"):
        """Read the named actual date source, keeping its local/instant role."""
        return _date_factory(cls, dt, "date", size=size, tz=tz, unit=unit, name=name,
                             ambiguous=ambiguous, nonexistent=nonexistent)

    @classmethod
    def fromdatetime(cls, dt, *, size=None, tz=None, unit=None, name=None,
                 ambiguous="raise", nonexistent="raise"):
        """Read the named actual date source, keeping its local/instant role."""
        return _date_factory(cls, dt, "datetime", size=size, tz=tz, unit=unit, name=name,
                             ambiguous=ambiguous, nonexistent=nonexistent)

    @classmethod
    def fromdatetime64(cls, dt64, *, size=None, tz=None, unit=None, name=None,
                 ambiguous="raise", nonexistent="raise"):
        """Read the named actual date source, keeping its local/instant role."""
        return _date_factory(cls, dt64, "numpy", size=size, tz=tz, unit=unit, name=name,
                             ambiguous=ambiguous, nonexistent=nonexistent)

    @classmethod
    def fromordinal(cls, ordinal, *, size=None, tz=None, unit="us", name=None,
                      ambiguous="raise", nonexistent="raise"):
        """Resolve real integer calendar components into one checked date column."""
        return _calendar_factory(cls, "ordinal", (ordinal,), size=size, tz=tz, unit=unit,
                                  name=name, ambiguous=ambiguous, nonexistent=nonexistent)

    @classmethod
    def fromisocalendar(cls, year, week, weekday, *, size=None, tz=None, unit="us", name=None,
                      ambiguous="raise", nonexistent="raise"):
        """Resolve real integer calendar components into one checked date column."""
        return _calendar_factory(cls, "iso", (year, week, weekday), size=size, tz=tz, unit=unit,
                                  name=name, ambiguous=ambiguous, nonexistent=nonexistent)

    @classmethod
    def fromdayofyear(cls, year, doy, *, size=None, tz=None, unit="us", name=None,
                      ambiguous="raise", nonexistent="raise"):
        """Resolve real integer calendar components into one checked date column."""
        return _calendar_factory(cls, "doy", (year, doy), size=size, tz=tz, unit=unit,
                                  name=name, ambiguous=ambiguous, nonexistent=nonexistent)

    @classmethod
    def combine(cls, date=None, time=None, *, size=None, tz=None, unit=None, name=None,
                ambiguous="raise", nonexistent="raise"):
        """Combine local YMD and clock fields; only the final result is a Pldt."""
        return _combine_factory(cls, date, time, size=size, tz=tz, unit=unit, name=name,
                                 ambiguous=ambiguous, nonexistent=nonexistent)

    @classmethod
    def fromisoformat(cls, dtstr, *, size=None, tz=None, unit=None, name=None,
                      ambiguous="raise", nonexistent="raise"):
        """Read complete strict ISO dates, retaining source fraction width."""
        return _iso_factory(cls, dtstr, size=size, tz=tz, unit=unit, name=name,
                             ambiguous=ambiguous, nonexistent=nonexistent)

    @classmethod
    def date_range(cls, start=None, *, end=None, periods=None, freq=None, tz=None,
                   normalize=False, inclusive="both", unit=None, name=None, default=None,
                   yearfirst=None, dayfirst=None, isoformat=True, strict=False, cfg=None,
                   ambiguous="raise", nonexistent="raise"):
        """Generate native calendar/elapsed dates; only special rules use optional pandas."""
        return _range_factory(cls, start, end=end, periods=periods, freq=freq, tz=tz,
                              normalize=normalize, inclusive=inclusive, unit=unit, name=name,
                              default=default, yearfirst=yearfirst, dayfirst=dayfirst,
                              isoformat=isoformat, strict=strict, cfg=cfg,
                              ambiguous=ambiguous, nonexistent=nonexistent)

    def as_unit(self, unit, round_ok=True):
        """Return the chosen ms/us/ns resolution; round_ok=True floors precision loss."""
        return _as_unit(self, unit, round_ok)

    def tz_localize(self, tz, ambiguous="raise", nonexistent="raise"):
        """Interpret naive clocks, or remove a timezone while keeping clocks."""
        return _tz_eager(self, "localize", tz, ambiguous=ambiguous, nonexistent=nonexistent)

    def tz_convert(self, tz):
        """Preserve actual instants; None removes the UTC timezone metadata."""
        return _tz_eager(self, "convert", tz)

    def astimezone(self, tz=None, *, ambiguous="raise", nonexistent="raise"):
        """Convert to the target; naive input uses the process-local timezone."""
        return _tz_eager(self, "astimezone", tz, ambiguous=ambiguous, nonexistent=nonexistent)

    def tz_switch(self, targ_tz, base_tz=None, naive=False, *, ambiguous="raise", nonexistent="raise"):
        """Convert with an explicit naive source zone, optionally removing target metadata."""
        return _tz_eager(self, "switch", targ_tz, base_tz, naive, ambiguous, nonexistent)

    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
        """Preserve NumPy temporal operands for the approved arithmetic routes."""
        if method == "__call__" and len(inputs) == 2 and not kwargs and ufunc in (np.add, np.subtract):
            left, right = inputs
            other = right if left is self else left
            temporal = isinstance(other, (np.datetime64, np.timedelta64)) or isinstance(other, np.ndarray) and other.dtype.kind in "Mm"
            if temporal:
                if ufunc is np.subtract and left is not self:
                    return NotImplemented
                return _binary_eager(self, other, subtract=ufunc is np.subtract, reflected=left is not self)
        return super().__array_ufunc__(ufunc, method, *inputs, **kwargs)

    def __add__(self, other):
        """Apply a calendar Delta or fixed elapsed duration at the current unit."""
        return _binary_eager(self, other)

    def __radd__(self, other):
        """Apply reflected Delta/duration addition through normal Python negotiation."""
        return _binary_eager(self, other, reflected=True)

    def __sub__(self, other):
        """Subtract Delta/duration, or return a native Duration Series for dates."""
        return _binary_eager(self, other, subtract=True)

    def is_month(self, month):
        """Return a Boolean Series; missing dates are False."""
        month = _integer_arg(month, "Pldt.is_month", "month")
        return _eager(self, "is_month", month)


class _SeriesNamespace(_TransformMethods):
    def add_delta(self, delta):
        """Apply actual Delta rules and return one final Pldt column."""
        return _binary_eager(self, delta, named=True)

    def sub_delta(self, delta):
        """Reverse relative Delta quantities while retaining absolute fields."""
        return _binary_eager(self, delta, subtract=True, named=True)

    def replace(self, year=None, month=None, day=None, hour=None, minute=None,
                second=None, microsecond=None, nanosecond=None, tzinfo=_UNCHANGED_ZONE, *,
                ambiguous="raise", nonexistent="raise"):
        """Strictly merge date fields; omitted tzinfo retains, None removes the zone."""
        return _date_operation(self, "replace", (year, month, day, hour, minute, second, microsecond, nanosecond),
                               "pldt.replace", tzinfo=tzinfo, ambiguous=ambiguous, nonexistent=nonexistent)

    def __init__(self, series):
        self._series = series

    def fromisoformat(self, *, tz=None, unit=None, name=None, ambiguous="raise", nonexistent="raise"):
        """Parse complete ISO text into one native date column."""
        cls = type(self._series) if isinstance(self._series, Pldt) else Pldt
        return _iso_factory(cls, self._series, tz=tz, unit=unit, name=name,
                             ambiguous=ambiguous, nonexistent=nonexistent)

    def combine(self, time=None, *, tz=None, unit=None, name=None, ambiguous="raise", nonexistent="raise"):
        """Use this Series for dates and compose one final native Pldt."""
        cls = type(self._series) if isinstance(self._series, Pldt) else Pldt
        return _combine_factory(cls, self._series, time, tz=tz, unit=unit, name=name,
                                 ambiguous=ambiguous, nonexistent=nonexistent)

    def fromordinal(self, *, tz=None, unit="us", name=None, ambiguous="raise", nonexistent="raise"):
        """Resolve positional calendar components with a fixed output schema."""
        cls = type(self._series) if isinstance(self._series, Pldt) else Pldt
        return _calendar_factory(cls, "ordinal", (self._series,), tz=tz, unit=unit, name=name,
                                 ambiguous=ambiguous, nonexistent=nonexistent)

    def fromisocalendar(self, week, weekday, *, tz=None, unit="us", name=None, ambiguous="raise", nonexistent="raise"):
        """Resolve positional calendar components with a fixed output schema."""
        cls = type(self._series) if isinstance(self._series, Pldt) else Pldt
        return _calendar_factory(cls, "iso", (self._series, week, weekday), tz=tz, unit=unit, name=name,
                                 ambiguous=ambiguous, nonexistent=nonexistent)

    def fromdayofyear(self, doy, *, tz=None, unit="us", name=None, ambiguous="raise", nonexistent="raise"):
        """Resolve positional calendar components with a fixed output schema."""
        cls = type(self._series) if isinstance(self._series, Pldt) else Pldt
        return _calendar_factory(cls, "doy", (self._series, doy), tz=tz, unit=unit, name=name,
                                 ambiguous=ambiguous, nonexistent=nonexistent)

    def parse(self, *, unit=None, name=None, copy=False, tz=None, default=None,
              yearfirst=None, dayfirst=None, isoformat=True, strict=False, cfg=None,
              ambiguous="raise", nonexistent="raise"):
        """Parse supported native data into a Pldt without a Python row UDF."""
        cls = type(self._series) if isinstance(self._series, Pldt) else Pldt
        try:
            return cls(self._series, unit=unit, name=name, copy=copy, tz=tz,
                              default=default, yearfirst=yearfirst, dayfirst=dayfirst,
                              isoformat=isoformat, strict=strict, cfg=cfg,
                              ambiguous=ambiguous, nonexistent=nonexistent)

        except Exception as error:
            _raise_argument_context(error, "Pldt.parse", "arguments", None)

    def strptime(self, fmt, *, tz=None, unit=None, name=None, cfg=None,
                 ambiguous="raise", nonexistent="raise"):
        """Match text using the shared format language and final output unit."""
        return Pldt.strptime(self._series, fmt, tz=tz, unit=unit, name=name, cfg=cfg,
                             ambiguous=ambiguous, nonexistent=nonexistent)

    def fromseconds(self, *, tz=None, unit=None, name=None, ambiguous="raise", nonexistent="raise"):
        """Read the numeric column using fixed quantity and timezone semantics."""
        return _numeric_eager((type(self._series) if isinstance(self._series, Pldt) else Pldt), self._series, 'seconds', tz=tz, unit=unit, name=name, ambiguous=ambiguous, nonexistent=nonexistent, entry="Pldt.fromseconds")

    def frommicroseconds(self, *, tz=None, unit=None, name=None, ambiguous="raise", nonexistent="raise"):
        """Read the numeric column using fixed quantity and timezone semantics."""
        return _numeric_eager((type(self._series) if isinstance(self._series, Pldt) else Pldt), self._series, 'micros', tz=tz, unit=unit, name=name, ambiguous=ambiguous, nonexistent=nonexistent, entry="Pldt.frommicroseconds")

    def fromtimestamp(self, *, tz=None, unit=None, name=None):
        """Read the numeric column using fixed quantity and timezone semantics."""
        return _numeric_eager((type(self._series) if isinstance(self._series, Pldt) else Pldt), self._series, ("local_timestamp" if tz is None else "timestamp"), tz=tz, unit=unit, name=name, entry="Pldt.fromtimestamp")

    def utcfromtimestamp(self, *, unit=None, name=None):
        """Read the numeric column using fixed quantity and timezone semantics."""
        return _numeric_eager((type(self._series) if isinstance(self._series, Pldt) else Pldt), self._series, 'utc_timestamp', tz=timezone.utc, unit=unit, name=name, entry="Pldt.utcfromtimestamp")

    def fromdate(self, *, tz=None, unit=None, name=None, ambiguous="raise", nonexistent="raise"):
        """Use the real native date schema, without parsing text or numeric data."""
        return _date_factory((type(self._series) if isinstance(self._series, Pldt) else Pldt), self._series, "date", tz=tz, unit=unit, name=name,
                                  ambiguous=ambiguous, nonexistent=nonexistent)

    def fromdatetime(self, *, tz=None, unit=None, name=None, ambiguous="raise", nonexistent="raise"):
        """Use the real native date schema, without parsing text or numeric data."""
        return _date_factory((type(self._series) if isinstance(self._series, Pldt) else Pldt), self._series, "datetime", tz=tz, unit=unit, name=name,
                                  ambiguous=ambiguous, nonexistent=nonexistent)

    def as_unit(self, unit, round_ok=True):
        """Convert Date/Datetime storage with explicit loss permission."""
        return _as_unit(self._series, unit, round_ok)

    def tz_localize(self, tz, ambiguous="raise", nonexistent="raise"):
        """Interpret naive clocks, or remove a timezone while keeping clocks."""
        return _tz_eager(self._series, "localize", tz, ambiguous=ambiguous, nonexistent=nonexistent)

    def tz_convert(self, tz):
        """Preserve actual instants; None removes the UTC timezone metadata."""
        return _tz_eager(self._series, "convert", tz)

    def astimezone(self, tz=None, *, ambiguous="raise", nonexistent="raise"):
        """Convert to the target; naive input uses the process-local timezone."""
        return _tz_eager(self._series, "astimezone", tz, ambiguous=ambiguous, nonexistent=nonexistent)

    def tz_switch(self, targ_tz, base_tz=None, naive=False, *, ambiguous="raise", nonexistent="raise"):
        """Convert with an explicit naive source zone, optionally removing target metadata."""
        return _tz_eager(self._series, "switch", targ_tz, base_tz, naive, ambiguous, nonexistent)

    def is_month(self, month):
        """Return a native Boolean column without an intermediate Pldt."""
        month = _integer_arg(month, "Pldt.is_month", "month")
        return _eager(self._series, "is_month", month)


class _ExprNamespace(_TransformMethods):
    def add_delta(self, delta):
        """Build a native Expr from concrete ordinary Delta snapshots."""
        return _delta_expression(self._expr, delta, False)

    def sub_delta(self, delta):
        """Build a native Expr reversing only relative Delta quantities."""
        return _delta_expression(self._expr, delta, True)

    def replace(self, year=None, month=None, day=None, hour=None, minute=None,
                second=None, microsecond=None, nanosecond=None, tzinfo=_UNCHANGED_ZONE, *,
                ambiguous="raise", nonexistent="raise"):
        """Strictly merge date fields; omitted tzinfo retains, None removes the zone."""
        return _date_operation(self, "replace", (year, month, day, hour, minute, second, microsecond, nanosecond),
                               "pldt.replace", tzinfo=tzinfo, ambiguous=ambiguous, nonexistent=nonexistent)

    def __init__(self, expr):
        self._expr = expr

    def fromisoformat(self, *, tz=None, unit=None, ambiguous="raise", nonexistent="raise"):
        """Parse a strict ISO String Expr with a fixed unit/timezone schema."""
        return _iso_expression(self._expr, tz=tz, unit=unit, ambiguous=ambiguous, nonexistent=nonexistent)

    def combine(self, time=None, *, tz=None, unit=None, ambiguous="raise", nonexistent="raise"):
        """Compose a date Expr with a native clock, keeping a fixed schema."""
        return _combine_expression(self._expr, time, tz=tz, unit=unit,
                                    ambiguous=ambiguous, nonexistent=nonexistent)

    def fromordinal(self, *, tz=None, unit="us", ambiguous="raise", nonexistent="raise"):
        """Resolve positional calendar components with a fixed output schema."""
        return _calendar_expression("ordinal", (self._expr,), tz=tz, unit=unit,
                                    ambiguous=ambiguous, nonexistent=nonexistent)

    def fromisocalendar(self, week, weekday, *, tz=None, unit="us", ambiguous="raise", nonexistent="raise"):
        """Resolve positional calendar components with a fixed output schema."""
        return _calendar_expression("iso", (self._expr, week, weekday), tz=tz, unit=unit,
                                    ambiguous=ambiguous, nonexistent=nonexistent)

    def fromdayofyear(self, doy, *, tz=None, unit="us", ambiguous="raise", nonexistent="raise"):
        """Resolve positional calendar components with a fixed output schema."""
        return _calendar_expression("doy", (self._expr, doy), tz=tz, unit=unit,
                                    ambiguous=ambiguous, nonexistent=nonexistent)

    def parse(self, *, unit=None, tz=None, default=None, yearfirst=None,
              dayfirst=None, isoformat=True, strict=False, cfg=None,
              ambiguous="raise", nonexistent="raise"):
        """Freeze shared String parsing rules and a static output schema."""
        return _text_expression(self._expr, unit=unit, tz=tz, default=default,
                                yearfirst=yearfirst, dayfirst=dayfirst,
                                isoformat=isoformat, strict=strict, cfg=cfg,
                                ambiguous=ambiguous, nonexistent=nonexistent)

    def strptime(self, fmt, *, tz=None, unit=None, cfg=None,
                 ambiguous="raise", nonexistent="raise"):
        """Freeze an explicit format; %f needs unit and timezone steps need tz."""
        return _text_expression(self._expr, fmt=fmt, unit=unit, tz=tz, cfg=cfg,
                                ambiguous=ambiguous, nonexistent=nonexistent)

    def fromseconds(self, *, tz=None, unit=None, ambiguous="raise", nonexistent="raise"):
        """Read the numeric column using fixed quantity and timezone semantics."""
        return _numeric_expression(self._expr, 'seconds', tz=tz, unit=unit, ambiguous=ambiguous, nonexistent=nonexistent, entry="Pldt.fromseconds")

    def frommicroseconds(self, *, tz=None, unit=None, ambiguous="raise", nonexistent="raise"):
        """Read the numeric column using fixed quantity and timezone semantics."""
        return _numeric_expression(self._expr, 'micros', tz=tz, unit=unit, ambiguous=ambiguous, nonexistent=nonexistent, entry="Pldt.frommicroseconds")

    def fromtimestamp(self, *, tz=None, unit=None):
        """Read the numeric column using fixed quantity and timezone semantics."""
        return _numeric_expression(self._expr, ("local_timestamp" if tz is None else "timestamp"), tz=tz, unit=unit, entry="Pldt.fromtimestamp")

    def utcfromtimestamp(self, *, unit=None):
        """Read the numeric column using fixed quantity and timezone semantics."""
        return _numeric_expression(self._expr, 'utc_timestamp', tz=timezone.utc, unit=unit, entry="Pldt.utcfromtimestamp")

    def fromdate(self, *, tz=None, unit=None, ambiguous="raise", nonexistent="raise"):
        """Use the real native date schema, without parsing text or numeric data."""
        return _date_expression(self._expr, "date", tz=tz, unit=unit,
                                  ambiguous=ambiguous, nonexistent=nonexistent)

    def fromdatetime(self, *, tz=None, unit=None, ambiguous="raise", nonexistent="raise"):
        """Use the real native date schema, without parsing text or numeric data."""
        return _date_expression(self._expr, "datetime", tz=tz, unit=unit,
                                  ambiguous=ambiguous, nonexistent=nonexistent)

    def as_unit(self, unit, round_ok=True):
        """Return an Expr with statically selected ms/us/ns resolution."""
        unit = _unit(unit)
        round_ok = _bool_option(round_ok, "Pldt.as_unit", "round_ok")
        return register_plugin_function(plugin_path=_PLUGIN_PATH, function_name="pldt_as_unit",
                                        args=[self._expr], kwargs={"version": 1, "unit": unit, "round_ok": round_ok}, is_elementwise=True)

    def tz_localize(self, tz, ambiguous="raise", nonexistent="raise"):
        """Interpret naive clocks, or remove a timezone while keeping clocks."""
        return _tz_expr(self._expr, "localize", tz, ambiguous=ambiguous, nonexistent=nonexistent)

    def tz_convert(self, tz):
        """Preserve actual instants; None removes the UTC timezone metadata."""
        return _tz_expr(self._expr, "convert", tz)

    def astimezone(self, tz=None, *, ambiguous="raise", nonexistent="raise"):
        """Convert to the target; naive input uses the process-local timezone."""
        return _tz_expr(self._expr, "astimezone", tz, ambiguous=ambiguous, nonexistent=nonexistent)

    def tz_switch(self, targ_tz, base_tz=None, naive=False, *, ambiguous="raise", nonexistent="raise"):
        """Convert with an explicit naive source zone, optionally removing target metadata."""
        return _tz_expr(self._expr, "switch", targ_tz, base_tz, naive, ambiguous, nonexistent)

    def is_month(self, month):
        """Return a Boolean Expr, preserving the source expression name."""
        month = _integer_arg(month, "Pldt.is_month", "month")
        return _expr(self._expr, "is_month", month)


if hasattr(pl.Series, "pldt") or hasattr(pl.Expr, "pldt"):
    raise RuntimeError("Cannot register rstimes.pldt: the Polars 'pldt' namespace is already occupied")

pl.api.register_series_namespace("pldt")(_SeriesNamespace)
pl.api.register_expr_namespace("pldt")(_ExprNamespace)

__all__ = ["Pldt"]
