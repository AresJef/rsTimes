"""Integer-backed date columns with explicit resolution and calendar operations."""
from datetime import datetime, date, timezone, timedelta
from zoneinfo import available_timezones

import numpy as np
from ._optional import PANDAS as pd, POLARS as pl
from ._native import (_bool_option, _pddt_result_type, _pddt_rescale, _pddt_prepare, _pddt_dates,
                      _pddt_check_native_dates, _pddt_register, _pddt_policies, _pddt_check_policies, _pddt_wall, _pddt_now, _integer_arg, _pddt_numbers, _pddt_number_buffer,
                      _pddt_integers, _pddt_calendar, _pddt_date_objects, _pddt_date_buffer,
                      _pddt_parts, _pddt_combine, _pddt_strptime, _pddt_component, _pddt_transform, _pddt_operand, _pddt_binary, _pddt_period, _pddt_fsp, _pddt_round, _pddt_snap, _pddt_query, _pddt_diff, _pddt_export, _pddt_objects, _pddt_range, _pddt_range_endpoints, _pddt_range_external)
from ._formatting import prepare_format as _prepare_format
from ._native import _strftime_prepare, _pddt_strftime
from ._range import frequency as _range_frequency, attach_frequency as _range_attach_frequency, rounding_step as _rounding_step, mature_units as _range_mature_units
from ._range import _ARRAY_HAS_FREQ
from .parser import Configs
from .delta import Delta
from .pydt import Pydt
from ._pddt_state import capture as _capture_state, apply as _apply_state, recipe as _pickle_recipe, copy_value as _copy_value, _definition as _state_definition
from ._localization import resolve_timezone as _timezone, local_timezone as _local_timezone
from .errors import _own_error, _external_error, _raise_argument_context

if pd is None:
    raise _own_error(ImportError("Pddt requires pandas; install rstimes[pandas]."))

_UNITS = ("s", "ms", "us", "ns")
_MIN_TICK = np.iinfo("int64").min
_pddt_register(pd.NA, pd.NaT, _timezone)
# pandas2.0 ignores a non-ns unit for integer+timezone dtype construction.
# Probe this public container capability once; the fallback still uses only
# date arrays, never an intermediate Pddt or per-row datetime conversion.
_TZ_TICKS_UNIT_SAFE = pd.array(np.array([1], dtype="int64"),
    dtype=pd.DatetimeTZDtype(unit="us", tz=timezone.utc), copy=False).unit == "us"


def _unit(value, *, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise _own_error(TypeError("must be a string unit"), "unit", value)
    try:
        valid = value in _UNITS
    except Exception as error:
        raise _external_error(error)
    if not valid:
        raise _own_error(ValueError("must be 's', 'ms', 'us' or 'ns'"), "unit", value)
    return value


def _boolean(value, entry, name):
    return value if type(value) is bool else _bool_option(value, entry, name)


def _outer(data, parameter="data"):
    """Recognize actual one-dimensional column types and retain their owners."""
    if issubclass(type(data), (str, bytes, bytearray)) or data is None:
        raise _own_error(TypeError("must be a one-dimensional collection; use [value] for one date"), parameter, data)
    if issubclass(type(data), (pd.DataFrame, pd.MultiIndex)):
        raise _own_error(TypeError("must contain one-dimensional date values, not table or tuple records"), parameter, data)
    source_name = None
    source_zone = None
    hint = None
    try:
        if issubclass(type(data), (pd.Series, pd.Index)):
            source_name = data.name
            values = data._data if issubclass(type(data), pd.DatetimeIndex) else data.array
        else:
            values = data
        if pl is not None and issubclass(type(values), pl.Series):
            source_name = values.name
            dtype = values.dtype
            kind = dtype.base_type()
            if kind == pl.Datetime:
                # Snapshot the immutable native data into a plain Series shell.
                # A Pldt public NumPy export has its own NaT-collision guard;
                # this internal validity-aware path must reach final target
                # processing first, and must not reread a mutable source shell.
                values = pl.Series(values)
                source_name = values.name
                zone = values.dtype.time_zone
                source_zone = _timezone(zone) if zone is not None else None
                validity = b"" if values.null_count() == 0 else np.asarray(values.is_null().to_numpy(), dtype="uint8").tobytes()
                # NumPy carries the physical bits; source validity remains
                # separate until the actual target unit/timezone is checked.
                return values.to_numpy(), source_zone, source_name, None, validity
            if kind == pl.Date:
                values = pl.Series(values)
                source_name = values.name
                validity = b"" if values.null_count() == 0 else np.asarray(values.is_null().to_numpy(), dtype="uint8").tobytes()
                return values.to_numpy(), None, source_name, None, validity
            if kind in (pl.Time, pl.List, pl.Array, pl.Struct):
                raise _own_error(TypeError("this Polars dtype is not date data"), parameter, data)
            if dtype.is_numeric():
                hint = "ns"
        elif pl is not None and issubclass(type(values), (pl.DataFrame, pl.LazyFrame)):
            raise _own_error(TypeError("must be a one-dimensional collection, not a Polars table"), parameter, data)
        if issubclass(type(values), pd.arrays.DatetimeArray):
            source_zone = _timezone(values.tz) if values.tz is not None else None
            values = values.asi8.view(f"datetime64[{values.unit}]")
        elif issubclass(type(values), (np.ndarray, pd.api.extensions.ExtensionArray)):
            if issubclass(type(values), np.ndarray):
                values = np.asarray(values)
            if values.ndim != 1:
                raise _own_error(ValueError("must be one-dimensional"), parameter, data)
            if getattr(values.dtype, "kind", None) in ("i", "u", "f"):
                hint = "ns"
        return values, source_zone, source_name, hint, None
    except Exception as error:
        # The original callback/column adapter failure is not a parse error.
        raise _external_error(error)


def _policies(ambiguous, nonexistent):
    if isinstance(ambiguous, (pd.DataFrame, pd.MultiIndex)):
        raise _own_error(TypeError("must be a boolean scalar, policy string or one-dimensional boolean collection"), "ambiguous", ambiguous)
    if isinstance(ambiguous, (np.ndarray, pd.api.extensions.ExtensionArray)) and ambiguous.ndim != 1:
        raise _own_error(ValueError("must be a one-dimensional boolean collection"), "ambiguous", ambiguous)
    if pl is not None and isinstance(ambiguous, (pl.DataFrame, pl.LazyFrame)):
        raise _own_error(TypeError("must be one-dimensional, not a Polars table"), "ambiguous", ambiguous)
    return _pddt_policies(ambiguous, nonexistent)


def _date_array(values, zone):
    """Create the final date array through the public pandas container API."""
    try:
        if zone is not None:
            zone = _timezone(zone, "tzinfo")
        if zone is None:
            return pd.array(values, copy=False)
        if _TZ_TICKS_UNIT_SAFE:
            unit = np.datetime_data(values.dtype)[0]
            return pd.array(values.view("int64"),
                dtype=pd.DatetimeTZDtype(unit=unit, tz=zone), copy=False)
        return pd.array(values, copy=False).tz_localize(timezone.utc).tz_convert(zone)
    except Exception as error:
        raise _external_error(error)


def _wrap(cls, values, *, zone=None, name=None, freq=None):
    """Build only the final pandas container from verified ticks and metadata."""
    try:
        array = _date_array(values, zone)
        if not _ARRAY_HAS_FREQ and freq is not None:
            # pandas3.1 validates on the Index and invokes its tz_localize.
            # Validate using the standard Index, then inherit that metadata so
            # validation cannot call Pddt's intentionally fixed-unit operation.
            prepared = pd.DatetimeIndex(array, freq=freq, copy=False)
            return pd.DatetimeIndex.__new__(cls, prepared, name=name, copy=False)
        return pd.DatetimeIndex.__new__(cls, array,
            name=name, freq=freq, copy=False)
    except Exception as error:
        raise _external_error(error)


def _finish(cls, values, *, zone=None, name=None, freq=None):
    """A new subclass date goes through one normal whole-column constructor."""
    if cls is Pddt:
        return _wrap(cls, values, zone=zone, name=name, freq=freq)
    # An aware date array conveys known instants without a temporary Pddt.
    if zone is not None:
        values = _date_array(values, zone)
    try:
        result = cls(values, name=name, freq=freq, copy=False)
    except Exception as error:
        raise _external_error(error)
    if not _pddt_result_type(result, cls, Pddt):
        raise _own_error(TypeError("subclass construction must return the corresponding Pddt subclass"))
    return result


def _prepare(data, unit, target, copy, default, yearfirst, dayfirst,
             isoformat, strict, cfg, policy, entry):
    values, source_zone, name, hint, validity = _outer(data)
    if issubclass(type(values), (np.ndarray, pd.api.extensions.ExtensionArray)):
        kind = getattr(values.dtype, "kind", None)
        if kind not in ("i", "u", "f", "M", "O", "U"):
            raise _own_error(TypeError("this column dtype is not supported date data"), "data", data)
        if kind == "f" and values.dtype.type not in (float, np.float16, np.float32, np.float64):
            raise _own_error(TypeError("date ticks support float16, float32 and float64, not extended floats"), "data", data)
    if issubclass(type(values), np.ndarray) and values.dtype.kind == "M":
        if values.ndim != 1:
            raise _own_error(ValueError("data must be one-dimensional"), "data", data)
        source, multiplier = np.datetime_data(values.dtype)
        if not values.dtype.isnative:
            values = values.astype(values.dtype.newbyteorder("="))
        selected = unit or source
        # Correct native-unit views with known instants or no timezone need no
        # row conversion. copy=False permits sharing a safe source owner.
        if source in _UNITS and multiplier == 1 and selected == source:
            if source_zone is not None or target is None:
                _pddt_check_policies(policy, len(values))
                if validity is not None:
                    _pddt_check_native_dates(values.view("int64"), validity, entry)
                return values.copy() if copy else values, target if target is not None else source_zone, name
        packed, selected, zone = _pddt_dates(values.tobytes(), policy, source, multiplier,
            unit, source_zone, target, entry, validity)
    else:
        packed, selected, zone = _pddt_prepare(values, policy, unit, hint, default,
            yearfirst, dayfirst, isoformat, strict, cfg, target, entry)
    return np.frombuffer(packed, dtype=f"datetime64[{selected}]"), zone, name


def _utc_values(array):
    return array.asi8.view(f"datetime64[{array.unit}]")


def _wall_values(array, entry):
    if array.tz is None:
        return _utc_values(array)
    packed = _pddt_wall(array.asi8.tobytes(), array.unit, array.tz, entry)
    return np.frombuffer(packed, dtype=f"datetime64[{array.unit}]")


def _localize_values(values, target, policy, entry):
    source, multiplier = np.datetime_data(values.dtype)
    packed, unit, _ = _pddt_dates(values.tobytes(), policy, source,
        multiplier, source, None, target, entry)
    return np.frombuffer(packed, dtype=f"datetime64[{unit}]")


def _size(value, entry):
    value = _integer_arg(value, entry, "size")
    if value < 0:
        raise _own_error(ValueError("must be nonnegative"), "size", value)
    return value


def _now(cls, size, tz, unit, name, kind):
    count = _size(size, "Pddt." + kind)
    unit = _unit(unit, optional=True) or "us"
    if kind == "utcnow":
        zone, naive = timezone.utc, False
    elif tz is not None:
        zone, naive = _timezone(tz, "tz"), False
    else:
        zone, naive = (_local_timezone() if count else None), True
    packed = _pddt_now(count, unit, zone, naive)
    values = np.frombuffer(packed, dtype=f"datetime64[{unit}]")
    return _finish(cls, values, zone=None if naive else zone, name=name)


def _numeric_source(value, parameter="data", integer=False):
    known = issubclass(type(value), (list, tuple, dict, set, frozenset, np.ndarray,
                               pd.Series, pd.Index, pd.api.extensions.ExtensionArray))
    if pl is not None:
        known = known or issubclass(type(value), (pl.Series, pl.DataFrame, pl.LazyFrame))
    if not known:
        return value, False, None, None
    values, _, name, _, validity = _outer(value, parameter)
    kind = getattr(getattr(values, "dtype", None), "kind", None)
    if validity is not None and kind == "M":
        raise _own_error(TypeError("native date columns do not supply numeric fields or epoch seconds"), parameter, value)
    mask = None
    if kind in ("b", "c", "m", "S", "V"):
        raise _own_error(TypeError("this dtype is not numeric date input"), parameter, value)
    try:
        if pl is not None and issubclass(type(values), pl.Series) and values.dtype.is_numeric():
            mask = np.asarray(values.is_null().to_numpy(), dtype="uint8").tobytes()
            values = values.fill_null(0).to_numpy()
            kind = values.dtype.kind
        elif issubclass(type(values), pd.api.extensions.ExtensionArray) and kind in ("i", "u", "f"):
            mask = np.asarray(values.isna(), dtype="uint8").tobytes()
            dtype = {"i":"int64", "u":"uint64", "f":"float64"}[kind]
            values = values.to_numpy(dtype=dtype, na_value=0)
        if issubclass(type(values), np.ndarray) and kind in ("i", "u", "f"):
            if integer and kind == "f" and values.dtype.type not in (float, np.float16, np.float32, np.float64):
                raise _own_error(TypeError("integer fields do not accept extended floating types, including their NaN values"), parameter, value)
            dtype = {"i":"int64", "u":"uint64", "f":"float64"}[kind]
            values = np.asarray(values, dtype=dtype)
            return values, True, name, (values.tobytes(), kind, mask)
    except Exception as error:
        raise _external_error(error)
    return values, True, name, None


def _from_numeric(cls, value, size, tz, unit, name, ambiguous, nonexistent, kind, entry, parameter):
    unit = _unit(unit, optional=True)
    count = None if size is None else _size(size, entry)
    policy = _policies(ambiguous, nonexistent)
    source, column, source_name, native = _numeric_source(value, parameter, kind == "us")
    if column and count is not None:
        raise _own_error(ValueError("omit size for a collection; it is used only with a scalar"), "size", size)
    local = None
    if kind == "timestamp" and tz is None:
        kind, local, target = "local_timestamp", _local_timezone, None
    else:
        target = None if tz is None else _timezone(tz, "tz")
    if native is not None:
        packed, selected, zone = _pddt_number_buffer(*native, policy, kind,
            unit, target, local, entry)
    else:
        packed, selected, zone = _pddt_numbers(source, policy, kind, count,
            column, unit, target, local, entry, parameter)
    values = np.frombuffer(packed, dtype=f"datetime64[{selected}]")
    return _finish(cls, values, zone=zone, name=source_name if name is None else name)


def _from_dates(cls, data, size, tz, unit, name, ambiguous, nonexistent, kind, entry):
    unit = _unit(unit, optional=True)
    count = None if size is None else _size(size, entry)
    policy = _policies(ambiguous, nonexistent)
    target = None if tz is None else _timezone(tz, "tz")
    known = issubclass(type(data), (list, tuple, dict, set, frozenset, np.ndarray,
                             pd.Series, pd.Index, pd.api.extensions.ExtensionArray))
    if pl is not None:
        known = known or issubclass(type(data), (pl.Series, pl.DataFrame, pl.LazyFrame))
    parameter = "dtstr" if kind == "iso" else "dt64" if kind == "numpy" else "dt"
    source_name = None
    if known:
        values, source_zone, source_name, _, validity = _outer(data, parameter)
        if count is not None:
            raise _own_error(ValueError("omit size for a collection"), "size", size)
        if issubclass(type(values), np.ndarray) and values.dtype.kind == "M":
            if kind == "iso":
                raise _own_error(TypeError("fromisoformat requires ISO text, not native dates"), parameter, data)
            native_column = issubclass(type(data), (pd.Series, pd.Index, pd.arrays.DatetimeArray))
            if pl is not None:
                native_column = native_column or issubclass(type(data), pl.Series)
                if kind == "datetime" and issubclass(type(data), pl.Series) and data.dtype.base_type() == pl.Date:
                    raise _own_error(TypeError("requires Datetime data; use fromdate for a Polars Date column"), parameter, data)
            if kind != "numpy" and not native_column:
                raise _own_error(TypeError("use fromdatetime64 for a NumPy datetime64 column"), parameter, data)
            if kind == "numpy" and not issubclass(type(data), np.ndarray):
                raise _own_error(TypeError("requires a NumPy datetime64 column"), parameter, data)
            source, multiplier = np.datetime_data(values.dtype)
            if not values.dtype.isnative:
                values = values.astype(values.dtype.newbyteorder("="))
            packed, selected, zone = _pddt_date_buffer(values.tobytes(), policy, kind,
                source, multiplier, unit, source_zone, target, entry, validity)
        else:
            if issubclass(type(values), (np.ndarray, pd.api.extensions.ExtensionArray)) and values.dtype.kind not in (("O", "U") if kind == "iso" else ("O",)):
                raise _own_error(TypeError("requires actual date values, not this column dtype"), parameter, data)
            packed, selected, zone = _pddt_date_objects(values, policy, kind, None, True, unit, target, entry)
    else:
        packed, selected, zone = _pddt_date_objects(data, policy, kind, count, False, unit, target, entry)
    values = np.frombuffer(packed, dtype=f"datetime64[{selected}]")
    return _finish(cls, values, zone=zone, name=source_name if name is None else name)


def _integer_component(value, entry, parameter):
    source, column, name, native = _numeric_source(value, parameter, True)
    if native is None:
        return _pddt_integers(source, column, entry, parameter), name
    data, kind, mask = native
    return _pddt_integers(None, True, entry, parameter, data, kind, mask), name


def _from_calendar(cls, components, kind, size, tz, unit, name, ambiguous, nonexistent, entry):
    unit = _unit(unit, optional=True)
    count = None if size is None else _size(size, entry)
    policy = _policies(ambiguous, nonexistent)
    target = None if tz is None else _timezone(tz, "tz")
    prepared, source_name = [], None
    for parameter, value in components:
        column, candidate_name = _integer_component(value, entry, parameter)
        prepared.append(column)
        if source_name is None:
            source_name = candidate_name
    first, *remaining = prepared
    second = remaining[0] if remaining else None
    third = remaining[1] if len(remaining) > 1 else None
    packed, selected, zone = _pddt_calendar(first, policy, kind, second, third,
        count, unit, target, entry)
    return _finish(cls, np.frombuffer(packed, dtype=f"datetime64[{selected}]"),
        zone=zone, name=source_name if name is None else name)


def _combine_part(value, clock):
    entry = "Pddt.combine"
    if pl is not None and issubclass(type(value), pl.Series) and value.dtype.base_type() == pl.Time:
        if not clock:
            raise _own_error(TypeError("a Polars Time column supplies time, not date fields"), "date", value)
        ticks = value.cast(pl.Int64).fill_null(_MIN_TICK).to_numpy()
        return _pddt_parts(None, _timezone, True, True, entry,
            ticks.tobytes(), "ns", 1, None, True), value.name
    known = issubclass(type(value), (list, tuple, dict, set, frozenset, np.ndarray,
                              pd.Series, pd.Index, pd.api.extensions.ExtensionArray))
    if pl is not None:
        known = known or issubclass(type(value), (pl.Series, pl.DataFrame, pl.LazyFrame))
    if not known:
        return _pddt_parts(value, _timezone, clock, False, entry), None
    values, zone, name, _, validity = _outer(value, "time" if clock else "date")
    if issubclass(type(values), np.ndarray) and values.dtype.kind == "M":
        source, multiplier = np.datetime_data(values.dtype)
        if not values.dtype.isnative:
            values = values.astype(values.dtype.newbyteorder("="))
        return _pddt_parts(None, _timezone, clock, True, entry,
            values.tobytes(), source, multiplier, zone, False, validity), name
    kind = getattr(getattr(values, "dtype", None), "kind", None)
    if kind in ("b", "c", "m", "S", "V"):
        raise _own_error(TypeError("this dtype does not supply date or clock fields"), "time" if clock else "date", value)
    return _pddt_parts(values, _timezone, clock, True, entry), name


_KEEP = _pddt_component(None, False, 0, "Pddt", "field", True)
_ZERO = _pddt_component(0, False, 0, "Pddt", "offset")
_UNSET = object()


def _component(value, length, entry, parameter, optional=False, names=0, low=None, high=None):
    if value is None and optional:
        return _KEEP
    if type(value) is int and value == 0 and (low is None or low <= 0) and (high is None or high >= 0):
        return _ZERO
    data, column, _, native = _numeric_source(value, parameter, True)
    dtype = getattr(data, "dtype", None)
    if column and getattr(dtype, "kind", None) in ("M", "m", "b", "c", "f", "S", "V"):
        raise _own_error(TypeError("requires integer fields or explicitly supported stored names, not this dtype"), parameter, value)
    if native is not None:
        buffer, kind, mask = native
        return _pddt_component(data, column, length, entry, parameter, optional,
            names, low, high, buffer, kind, mask)
    return _pddt_component(data, column, length, entry, parameter, optional, names, low, high)


def _transformed(self, kind, specifications, entry, policy=None, target=None, replace_zone=False):
    length = len(self)
    components = [_component(value, length, entry, name, optional, names, low, high)
        for value, name, optional, names, low, high in specifications]
    packed, selected, zone, changed = _pddt_transform(self.asi8.tobytes(),
        self.unit, self.tz, kind, components, entry, policy, target, replace_zone)
    if not changed:
        return self
    array = _date_array(np.frombuffer(packed, dtype=f"datetime64[{selected}]"), zone)
    validated_freq = _range_attach_frequency(array, self.freq)
    return _finish(type(self), array, name=self.name, freq=validated_freq)


def _fields(self, values, entry, strict=False, tzinfo=_UNSET, ambiguous="raise", nonexistent="raise"):
    names = ("year", "month", "day", "hour", "minute", "second", "microsecond", "nanosecond")
    lows = (None, 1, 1, 0, 0, 0, 0, 0)
    highs = (None, 12, 31, 23, 59, 59, 999999, 999)
    specifications = [(v, n, True, 0, low, high) for v, n, low, high in zip(values, names, lows, highs)]
    policy = _policies(ambiguous, nonexistent) if strict else None
    target = _timezone(tzinfo, "tzinfo") if tzinfo is not _UNSET and tzinfo is not None else None
    return _transformed(self, "replace" if strict else "adjust", specifications,
        entry, policy, target, tzinfo is not _UNSET)


def _moved(self, kind, offset, selection, day, entry):
    specifications = [(offset, "offset", False, 0, None, None)]
    if kind in ("year", "quarter"):
        specifications.extend(((selection, "month", True, 1 if kind == "year" else 0, 1, 12 if kind == "year" else 3),
            (day, "day", True, 0, 1, 31)))
    elif kind == "month":
        specifications.append((day, "day", True, 0, 1, 31))
    elif kind == "weekday":
        specifications.append((selection, "weekday", True, 2, 0, 6))
    return _transformed(self, kind, specifications, entry)


def _incremented(self, values, entry, subtract):
    names = ("years", "quarters", "months", "weeks", "days", "hours", "minutes", "seconds", "milliseconds", "microseconds", "nanoseconds")
    specifications = [(v, n, False, 0, None, None) for v, n in zip(values, names)]
    return _transformed(self, "sub" if subtract else "add", specifications, entry)


def _binary(self, other, subtract=False, reflected=False):
    # pandas Series/DataFrame own their full alignment/column dispatch.
    if issubclass(type(other), (pd.Series, pd.DataFrame)):
        return NotImplemented
    source, source_zone, _, _, validity = (other, None, None, None, None)
    column = issubclass(type(other), (list, tuple, dict, set, frozenset, np.ndarray,
        pd.Index, pd.api.extensions.ExtensionArray))
    if pl is not None:
        column = column or issubclass(type(other), (pl.Series, pl.DataFrame, pl.LazyFrame))
    native = None
    if column:
        if pl is not None and issubclass(type(other), pl.Series) and other.dtype.base_type()==pl.Duration:
            source=other.cast(pl.Int64).fill_null(_MIN_TICK).to_numpy().view(f"timedelta64[{other.dtype.time_unit}]")
        else:
            source, source_zone, _, _, validity = _outer(other, "other")
        if issubclass(type(source), pd.arrays.TimedeltaArray):
            source=source.asi8.view(f"timedelta64[{source.unit}]")
        if issubclass(type(source), np.ndarray) and source.dtype.kind in ("M", "m"):
            unit, multiplier = np.datetime_data(source.dtype)
            if not source.dtype.isnative:
                source = source.astype(source.dtype.newbyteorder("="))
            native = (source.tobytes(), source.dtype.kind, unit, multiplier, source_zone, validity)
        elif issubclass(type(source), (np.ndarray, pd.api.extensions.ExtensionArray)) and source.dtype.kind not in ("O",):
            parent = pd.DatetimeIndex.__sub__ if subtract else pd.DatetimeIndex.__radd__ if reflected else pd.DatetimeIndex.__add__
            try:
                return parent(self, other)
            except Exception as error:
                raise _external_error(error)
    entry = "Pddt.__sub__" if subtract else "Pddt.__radd__" if reflected else "Pddt.__add__"
    if native is None:
        operand = _pddt_operand(source, column, len(self), entry, subtract, reflected)
    else:
        operand = _pddt_operand(source, column, len(self), entry, subtract, reflected, *native)
    if operand is None:
        if issubclass(type(other), (Delta, timedelta)):
            return NotImplemented
        parent = pd.DatetimeIndex.__sub__ if subtract else pd.DatetimeIndex.__radd__ if reflected else pd.DatetimeIndex.__add__
        try:
            return parent(self, other)
        except Exception as error:
            raise _external_error(error)
    if operand.date and not subtract:
        return NotImplemented
    packed, unit, duration, changed = _pddt_binary(self.asi8.tobytes(),
        self.unit, self.tz, operand, subtract, entry)
    if duration:
        return pd.TimedeltaIndex(np.frombuffer(packed, dtype=f"timedelta64[{unit}]"), name=self.name)
    if not changed:
        return self
    array = _date_array(np.frombuffer(packed, dtype=f"datetime64[{unit}]"), self.tz)
    validated_freq = _range_attach_frequency(array, self.freq)
    return _finish(type(self), array, name=self.name, freq=validated_freq)


def _period(self, unit, mode, query, entry):
    if not isinstance(unit,str):
        raise _own_error(TypeError("must be a period string or a supported stored name"), "unit", unit)
    packed, changed = _pddt_period(self.asi8.tobytes(), self.unit, self.tz,
        unit, mode, query, entry)
    if query:
        return pd.Index(np.frombuffer(packed,dtype="bool"),name=entry.rsplit(".",1)[-1])
    if not changed:
        return self
    array = _date_array(np.frombuffer(packed,dtype=f"datetime64[{self.unit}]"), self.tz)
    validated_freq=_range_attach_frequency(array,self.freq)
    return _finish(type(self),array,name=self.name,freq=validated_freq)


def _rounded(self, freq, mode, entry):
    step=_rounding_step(freq)
    packed,changed=_pddt_round(self.asi8.tobytes(),self.unit,self.tz,step,mode,entry)
    if not changed:
        return self
    array=_date_array(np.frombuffer(packed,dtype=f"datetime64[{self.unit}]"),self.tz)
    validated_freq=_range_attach_frequency(array,self.freq)
    return _finish(type(self),array,name=self.name,freq=validated_freq)


def _calendar_query(self, code, entry, target=_UNSET, parameter=None, names=0):
    prepared=None if target is _UNSET else _component(target,len(self),entry,parameter,False,names)
    packed,mask=_pddt_query(self.asi8.tobytes(),self.unit,self.tz,code,entry,prepared)
    if 100<=code<200:
        return pd.Index(np.frombuffer(packed,dtype="bool"),name=entry.rsplit(".",1)[-1])
    values=np.frombuffer(packed,dtype="int64")
    missing=None if mask is None else np.frombuffer(mask,dtype="bool")
    if code==201:
        values=values.reshape((-1,3))
        columns={}
        for i,name in enumerate(("year","week","day")):
            column=pd.array(values[:,i],dtype="UInt32",copy=True)
            if missing is not None:
                column[missing]=pd.NA
            columns[name]=column
        return pd.DataFrame(columns,index=self)
    if code==200:
        if missing is not None:
            values=values.astype("float64");values[missing]=np.nan
        elif len(values)==0 or (values.min()>=-2**31 and values.max()<2**31):
            values=values.astype("int32")
        return pd.Index(values,name=self.name)
    array=pd.array(values,dtype="Int64",copy=True)
    if missing is not None:
        array[missing]=pd.NA
    return pd.Index(array,name=entry.rsplit(".",1)[-1])


def _difference(self,dtobj,unit,absolute,inclusive):
    entry="Pddt.diff"
    absolute=_boolean(absolute,entry,"absolute")
    for name,value in (("unit",unit),("inclusive",inclusive)):
        if not issubclass(type(value), str):
            raise _own_error(TypeError("must be a string"),name,value)
    source=self.asi8.tobytes()
    known=issubclass(type(dtobj), (list,tuple,dict,set,frozenset,np.ndarray,pd.Series,pd.Index,pd.api.extensions.ExtensionArray))
    if pl is not None:
        known=known or issubclass(type(dtobj), (pl.Series,pl.DataFrame,pl.LazyFrame))
    values,zone,metadata=(dtobj,None,{})
    if known:
        try:
            values,zone,_,_,validity=_outer(dtobj,"dtobj")
        except Exception as error:
            _raise_argument_context(error,entry,"dtobj",dtobj)
        if issubclass(type(values), np.ndarray) and values.dtype.kind=="M":
            date_unit,multiplier=np.datetime_data(values.dtype)
            if not values.dtype.isnative:
                values=values.astype(values.dtype.newbyteorder("="))
            metadata=dict(buffer=values.tobytes(),storage="M",date_unit=date_unit,multiplier=multiplier,target_zone=zone,target_mask=validity)
        else:
            values,_,_,native=_numeric_source(values,"dtobj",True)
            if native is not None:
                buffer,storage,mask=native
                metadata=dict(buffer=buffer,storage=storage,target_mask=mask)
    packed,mask=_pddt_diff(source,self.unit,self.tz is not None,values,known,unit,absolute,inclusive,**metadata)
    values=np.frombuffer(packed,dtype="int64")
    if mask is not None:
        values=pd.array(values,dtype="Int64",copy=True)
        values[np.frombuffer(mask,dtype="bool")]=pd.NA
    return pd.Index(values,name="diff")


_TM_KEYS=("tm_year","tm_mon","tm_mday","tm_hour","tm_min","tm_sec","tm_wday","tm_yday","tm_isdst")
_TM_DTYPES=("Int64","Int8","Int8","Int8","Int8","Int8","Int8","Int16","Int8")


def _numeric_export(self,kind,entry,utc=False):
    packed,mask=_pddt_export(self.asi8.tobytes(),self.unit,self.tz,kind,entry,utc)
    values=np.frombuffer(packed,dtype="float64" if kind in (0,3) else "int64")
    missing=None if mask is None else np.frombuffer(mask,dtype="bool")
    if kind>=4:
        values=values.reshape((-1,9))
        columns={}
        for i,(name,dtype) in enumerate(zip(_TM_KEYS,_TM_DTYPES)):
            column=pd.array(values[:,i],dtype=dtype,copy=True)
            if missing is not None:
                column[missing]=pd.NA
            columns[name]=column
        return pd.DataFrame(columns,index=pd.RangeIndex(len(self)))
    name=("seconds","microseconds","ordinal","timestamp")[kind]
    if kind not in (0,3):
        values=pd.array(values,dtype="Int64",copy=True)
        if missing is not None:
            values[missing]=pd.NA
    return pd.Index(values,name=name)


def _object_export(self,kind,entry,option=None,timespec=None):
    values=_pddt_objects(self.asi8.tobytes(),self.unit,self.tz,kind,entry,Pydt if kind==0 else None,option,timespec)
    if kind<=3:
        return np.asarray(values,dtype=object)
    return pd.Index(values,dtype=object if kind==4 else None,name="tzname" if kind==4 else self.name)


def _restore_pddt_copy(cls,array,name,freq):
    if not isinstance(cls,type) or not issubclass(cls,Pddt):
        raise _own_error(TypeError("class must be Pddt or its subclass"),"state.class",cls)
    if not isinstance(array,pd.arrays.DatetimeArray):
        raise _own_error(TypeError("must be a DatetimeArray"),"state.data",array)
    # Base construction deliberately bypasses business __new__/__init__ during restore.
    if _ARRAY_HAS_FREQ:
        # Retain the original direct restore on pandas2/3.0. The array already
        # has the correct dtype/tz; no conversion or extra wrapper is needed.
        try:
            return pd.DatetimeIndex.__new__(cls,array,name=name,freq=freq,copy=False)
        except Exception as error:
            raise _external_error(error)
    return _wrap(cls,array,name=name,freq=freq)


def _restore_pddt(cls,marker,version,data,unit,tz,name,freq):
    entry="Pddt restore"
    try:
        if type(marker) is not str or marker!="rstimes.pddt":
            raise _own_error(ValueError("unsupported state marker; only the new Pddt format is accepted"),"state.marker",marker)
        if type(version) is not int:
            raise _own_error(TypeError("must be an exact int"),"state.version",version)
        if version!=1:
            raise _own_error(ValueError("unsupported Pddt state version"),"state.version",version)
        if not isinstance(cls,type) or not issubclass(cls,Pddt):
            raise _own_error(TypeError("class must be Pddt or its subclass"),"state.class",cls)
        if type(data) is not bytes:
            raise _own_error(TypeError("must be immutable date bytes"),"state.data",data)
        if len(data)%8:
            raise _own_error(ValueError("date bytes must contain complete int64 ticks"),"state.data",data)
        unit=_unit(unit)
        zone=None if tz is None else _timezone(tz,"state.tz")
        values=np.frombuffer(data,dtype="<i8").astype("int64",copy=False).view(f"datetime64[{unit}]")
        return _wrap(cls,values,zone=zone,name=name,freq=freq)
    except Exception as error:
        _raise_argument_context(error,entry,"state",None)


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

    def __new__(cls, data, *, unit=None, name=None, copy=False, freq=None,
                tz=None, default=None, yearfirst=None, dayfirst=None,
                isoformat=True, strict=False, cfg=None,
                ambiguous="raise", nonexistent="raise"):
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
        try:
            unit = _unit(unit, optional=True)
            copy = _boolean(copy, "Pddt", "copy")
            strict = _boolean(strict, "Pddt", "strict")
            isoformat = _boolean(isoformat, "Pddt", "isoformat")
            if yearfirst is not None:
                yearfirst = _boolean(yearfirst, "Pddt", "yearfirst")
            if dayfirst is not None:
                dayfirst = _boolean(dayfirst, "Pddt", "dayfirst")
            if cfg is not None and not isinstance(cfg, Configs):
                raise _own_error(TypeError("must be a Configs instance or None"), "cfg", cfg)
            policy = _policies(ambiguous, nonexistent)
            target = None if tz is None else _timezone(tz, "tz")
            values, zone, source_name = _prepare(data, unit, target, copy, default,
                yearfirst, dayfirst, isoformat, strict, cfg, policy, "Pddt")
            if name is None:
                name = source_name
            return _wrap(cls, values, zone=zone, name=name, freq=freq)
        except Exception as error:
            _raise_argument_context(error, "Pddt", "arguments", None)

    @classmethod
    def parse(cls, data, *, unit=None, name=None, copy=False, freq=None,
              tz=None, default=None, yearfirst=None, dayfirst=None,
              isoformat=True, strict=False, cfg=None,
              ambiguous="raise", nonexistent="raise"):
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
        try:
            try:
                result = cls(data, unit=unit, name=name, copy=copy, freq=freq, tz=tz,
                    default=default, yearfirst=yearfirst, dayfirst=dayfirst,
                    isoformat=isoformat, strict=strict, cfg=cfg,
                    ambiguous=ambiguous, nonexistent=nonexistent)
            except Exception as error:
                if cls is not Pddt:
                    raise _external_error(error)
                raise
            if not _pddt_result_type(result, cls, Pddt):
                raise _own_error(TypeError("subclass construction must return the corresponding Pddt subclass"))
            return result
        except Exception as error:
            _raise_argument_context(error, "Pddt.parse", "arguments", None)


    def as_unit(self, unit, round_ok=True):
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
        try:
            unit = _unit(unit)
            round_ok = _boolean(round_ok, "Pddt.as_unit", "round_ok")
            array = self._data
            if unit == array.unit:
                return self
            packed = _pddt_rescale(array.asi8.tobytes(), array.unit, unit,
                                  round_ok, "Pddt.as_unit")
            values = np.frombuffer(packed, dtype=f"datetime64[{unit}]")
            return _finish(type(self), values, zone=array.tz, name=self.name)
        except Exception as error:
            _raise_argument_context(error, "Pddt.as_unit", "unit", unit)


    @property
    def tzinfo(self):
        """The timezone shared by this column, or None for naive dates.

        Returns
        -------
        datetime.tzinfo or None
            Actual timezone metadata, independent of any single row's offset.
        """
        return self._data.tz

    @property
    def tz_available(self):
        """The region names available to ZoneInfo on this system.

        Returns
        -------
        set[str]
            Available IANA timezone keys. This does not read the local clock.
        """
        try:
            return available_timezones()
        except Exception as error:
            _raise_argument_context(_external_error(error), "Pddt.tz_available", "arguments", None)

    def is_utc(self):
        """Return whether this column uses datetime.timezone.utc.

        Returns
        -------
        bool
            One metadata result for the whole column, including an empty one.
        """
        return self._data.tz is timezone.utc

    def is_local(self):
        """Return whether the column uses the cached process-local timezone.

        Returns
        -------
        bool
            False for a naive column. The local timezone is loaded only when
            a timezone-bearing column actually needs this query.
        """
        zone = self._data.tz
        if zone is None:
            return False
        try:
            return zone is _local_timezone()
        except Exception as error:
            _raise_argument_context(_external_error(error), "Pddt.is_local", "arguments", None)

    def tz_convert(self, tz):
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
        try:
            array = self._data
            if array.tz is None:
                raise _own_error(TypeError("source is naive; attach its timezone with tz_localize first"))
            target = None if tz is None else _timezone(tz, "tz")
            if target is array.tz:
                return self
            return _finish(type(self), _utc_values(array), zone=target, name=self.name)
        except Exception as error:
            _raise_argument_context(error, "Pddt.tz_convert", "arguments", None)

    def tz_localize(self, tz, ambiguous="raise", nonexistent="raise"):
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
        try:
            policy = _policies(ambiguous, nonexistent)
            array = self._data
            _pddt_check_policies(policy, len(array))
            target = None if tz is None else _timezone(tz, "tz")
            if array.tz is not None:
                if target is not None:
                    raise _own_error(TypeError("source already has a timezone; use tz_convert to preserve its instants"))
                values = _wall_values(array, "Pddt.tz_localize")
            else:
                if target is None:
                    return self
                values = _localize_values(_utc_values(array), target, policy, "Pddt.tz_localize")
            return _finish(type(self), values, zone=target, name=self.name)
        except Exception as error:
            _raise_argument_context(error, "Pddt.tz_localize", "arguments", None)

    def astimezone(self, tz=None, *, ambiguous="raise", nonexistent="raise"):
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
        try:
            policy = _policies(ambiguous, nonexistent)
            array = self._data
            _pddt_check_policies(policy, len(array))
            target = _local_timezone() if tz is None else _timezone(tz, "tz")
            if array.tz is target:
                return self
            values = _utc_values(array)
            if array.tz is None:
                values = _localize_values(values, _local_timezone(), policy, "Pddt.astimezone")
            return _finish(type(self), values, zone=target, name=self.name)
        except Exception as error:
            _raise_argument_context(error, "Pddt.astimezone", "arguments", None)

    def tz_switch(self, targ_tz, base_tz=None, naive=False, *, ambiguous="raise", nonexistent="raise"):
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
        try:
            naive = _boolean(naive, "Pddt.tz_switch", "naive")
            policy = _policies(ambiguous, nonexistent)
            array = self._data
            _pddt_check_policies(policy, len(array))
            if targ_tz is None:
                if array.tz is None:
                    return self
                values = _wall_values(array, "Pddt.tz_switch")
                return _finish(type(self), values, name=self.name)
            target = _timezone(targ_tz, "targ_tz")
            values = _utc_values(array)
            if array.tz is None:
                if base_tz is None:
                    raise _own_error(ValueError("naive dates need base_tz, for example tz_switch('UTC', base_tz='Asia/Shanghai')"), "base_tz", base_tz)
                base = _timezone(base_tz, "base_tz")
                values = _localize_values(values, base, policy, "Pddt.tz_switch")
            if naive:
                packed = _pddt_wall(values.view("int64").tobytes(), array.unit, target, "Pddt.tz_switch")
                values = np.frombuffer(packed, dtype=f"datetime64[{array.unit}]")
                target = None
            return _finish(type(self), values, zone=target, name=self.name)
        except Exception as error:
            _raise_argument_context(error, "Pddt.tz_switch", "arguments", None)


    @classmethod
    def now(cls, size, *, tz=None, unit=None, name=None):
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
        try:
            return _now(cls, size, tz, unit, name, "now")
        except Exception as error:
            _raise_argument_context(error, "Pddt.now", "arguments", None)

    @classmethod
    def today(cls, size, *, unit=None, name=None):
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
        try:
            return _now(cls, size, None, unit, name, "today")
        except Exception as error:
            _raise_argument_context(error, "Pddt.today", "arguments", None)

    @classmethod
    def utcnow(cls, size, *, unit=None, name=None):
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
        try:
            return _now(cls, size, timezone.utc, unit, name, "utcnow")
        except Exception as error:
            _raise_argument_context(error, "Pddt.utcnow", "arguments", None)


    @classmethod
    def fromseconds(cls, seconds, *, size=None, tz=None, unit=None, name=None,
                    ambiguous="raise", nonexistent="raise"):
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
        try:
            return _from_numeric(cls, seconds, size, tz, unit, name, ambiguous,
                nonexistent, "seconds", "Pddt.fromseconds", "seconds")
        except Exception as error:
            _raise_argument_context(error, "Pddt.fromseconds", "arguments", None)

    @classmethod
    def frommicroseconds(cls, us, *, size=None, tz=None, unit=None, name=None,
                         ambiguous="raise", nonexistent="raise"):
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
        try:
            return _from_numeric(cls, us, size, tz, unit, name, ambiguous,
                nonexistent, "us", "Pddt.frommicroseconds", "us")
        except Exception as error:
            _raise_argument_context(error, "Pddt.frommicroseconds", "arguments", None)

    @classmethod
    def fromtimestamp(cls, ts, *, size=None, tz=None, unit=None, name=None):
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
        try:
            return _from_numeric(cls, ts, size, tz, unit, name, "raise",
                "raise", "timestamp", "Pddt.fromtimestamp", "ts")
        except Exception as error:
            _raise_argument_context(error, "Pddt.fromtimestamp", "arguments", None)

    @classmethod
    def utcfromtimestamp(cls, ts, *, size=None, unit=None, name=None):
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
        try:
            return _from_numeric(cls, ts, size, timezone.utc, unit, name, "raise",
                "raise", "timestamp", "Pddt.utcfromtimestamp", "ts")
        except Exception as error:
            _raise_argument_context(error, "Pddt.utcfromtimestamp", "arguments", None)

    @classmethod
    def fromdate(cls, dt, *, size=None, tz=None, unit=None, name=None,
                 ambiguous="raise", nonexistent="raise"):
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
        try:
            return _from_dates(cls, dt, size, tz, unit, name, ambiguous,
                nonexistent, "date", "Pddt.fromdate")
        except Exception as error:
            _raise_argument_context(error, "Pddt.fromdate", "arguments", None)

    @classmethod
    def fromdatetime(cls, dt, *, size=None, tz=None, unit=None, name=None,
                 ambiguous="raise", nonexistent="raise"):
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
        try:
            return _from_dates(cls, dt, size, tz, unit, name, ambiguous,
                nonexistent, "datetime", "Pddt.fromdatetime")
        except Exception as error:
            _raise_argument_context(error, "Pddt.fromdatetime", "arguments", None)

    @classmethod
    def fromdatetime64(cls, dt64, *, size=None, tz=None, unit=None, name=None,
                 ambiguous="raise", nonexistent="raise"):
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
        try:
            return _from_dates(cls, dt64, size, tz, unit, name, ambiguous,
                nonexistent, "numpy", "Pddt.fromdatetime64")
        except Exception as error:
            _raise_argument_context(error, "Pddt.fromdatetime64", "arguments", None)

    @classmethod
    def fromordinal(cls, ordinal, *, size=None, tz=None, unit=None, name=None,
                 ambiguous="raise", nonexistent="raise"):
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
        try:
            return _from_calendar(cls, (("ordinal", ordinal),), "ordinal", size, tz, unit,
                name, ambiguous, nonexistent, "Pddt.fromordinal")
        except Exception as error:
            _raise_argument_context(error, "Pddt.fromordinal", "arguments", None)

    @classmethod
    def fromisocalendar(cls, year, week, weekday, *, size=None, tz=None, unit=None, name=None,
                 ambiguous="raise", nonexistent="raise"):
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
        try:
            return _from_calendar(cls, (("year", year), ("week", week), ("weekday", weekday)), "iso", size, tz, unit,
                name, ambiguous, nonexistent, "Pddt.fromisocalendar")
        except Exception as error:
            _raise_argument_context(error, "Pddt.fromisocalendar", "arguments", None)

    @classmethod
    def fromdayofyear(cls, year, doy, *, size=None, tz=None, unit=None, name=None,
                 ambiguous="raise", nonexistent="raise"):
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
        try:
            return _from_calendar(cls, (("year", year), ("doy", doy)), "doy", size, tz, unit,
                name, ambiguous, nonexistent, "Pddt.fromdayofyear")
        except Exception as error:
            _raise_argument_context(error, "Pddt.fromdayofyear", "arguments", None)

    @classmethod
    def fromisoformat(cls, dtstr, *, size=None, tz=None, unit=None, name=None,
                      ambiguous="raise", nonexistent="raise"):
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
        try:
            return _from_dates(cls, dtstr, size, tz, unit, name, ambiguous,
                nonexistent, "iso", "Pddt.fromisoformat")
        except Exception as error:
            _raise_argument_context(error, "Pddt.fromisoformat", "arguments", None)

    @classmethod
    def combine(cls, date=None, time=None, *, size=None, tz=None, unit=None,
                name=None, ambiguous="raise", nonexistent="raise"):
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
        try:
            selected = _unit(unit, optional=True)
            count = None if size is None else _size(size, "Pddt.combine")
            policy = _policies(ambiguous, nonexistent)
            target = None if tz is None else _timezone(tz, "tz")
            dates, date_name = _combine_part(date, False)
            clocks, time_name = _combine_part(time, True)
            packed, selected, zone = _pddt_combine(dates, clocks, policy,
                _local_timezone, count, selected, target)
            values = np.frombuffer(packed, dtype=f"datetime64[{selected}]")
            if name is None:
                name = date_name if date_name is not None else time_name
            return _finish(cls, values, zone=zone, name=name)
        except Exception as error:
            _raise_argument_context(error, "Pddt.combine", "arguments", None)

    @classmethod
    def strptime(cls, dtstr, fmt, *, size=None, tz=None, unit=None, name=None, cfg=None,
                 ambiguous="raise", nonexistent="raise"):
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
        try:
            selected = _unit(unit, optional=True)
            count = None if size is None else _size(size, "Pddt.strptime")
            policy = _policies(ambiguous, nonexistent)
            target = None if tz is None else _timezone(tz, "tz")
            compiled = _prepare_format(fmt)
            known = issubclass(type(dtstr), (list, tuple, dict, set, frozenset, np.ndarray,
                pd.Series, pd.Index, pd.api.extensions.ExtensionArray))
            if pl is not None:
                known = known or issubclass(type(dtstr), (pl.Series, pl.DataFrame, pl.LazyFrame))
            source_name = None
            if known:
                values, _, source_name, _, _ = _outer(dtstr, "dtstr")
                if issubclass(type(values), (np.ndarray, pd.api.extensions.ExtensionArray)) and values.dtype.kind not in ("O", "U"):
                    raise _own_error(TypeError("requires text values for the supplied format"), "dtstr", dtstr)
            else:
                values = dtstr
            packed, selected, zone = _pddt_strptime(values, compiled, policy, cfg,
                count, known, selected, target=target)
            return _finish(cls, np.frombuffer(packed, dtype=f"datetime64[{selected}]"),
                zone=zone, name=source_name if name is None else name)
        except Exception as error:
            _raise_argument_context(error, "Pddt.strptime", "arguments", None)


    @classmethod
    def date_range(cls, start=None, *, end=None, periods=None, freq=None, tz=None,
                   normalize=False, inclusive="both", unit=None, name=None,
                   default=None, yearfirst=None, dayfirst=None, isoformat=True,
                   strict=False, cfg=None, ambiguous="raise", nonexistent="raise"):
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
        try:
            entry = "Pddt.date_range"
            unit = _unit(unit, optional=True)
            if periods is not None:
                periods = _integer_arg(periods, entry, "periods")
                if periods < 0:
                    raise _own_error(ValueError("must be nonnegative"), "periods", periods)
            normalize = _boolean(normalize, entry, "normalize")
            isoformat = _boolean(isoformat, entry, "isoformat")
            strict = _boolean(strict, entry, "strict")
            yearfirst = None if yearfirst is None else _boolean(yearfirst, entry, "yearfirst")
            dayfirst = None if dayfirst is None else _boolean(dayfirst, entry, "dayfirst")
            if cfg is not None and not isinstance(cfg, Configs):
                raise _own_error(TypeError("must be Configs or None"), "cfg", cfg)
            policy = _policies(ambiguous, nonexistent)
            target = None if tz is None else _timezone(tz, "tz")
            if freq is None and (start is None or end is None or periods is None):
                freq = "D"
            plan, metadata, delegate = _range_frequency(freq)
            if delegate:
                if sum(x is not None for x in (start, end, periods)) != 2:
                    raise _own_error(ValueError("exactly two of start, end and periods are required with a frequency"))
                inputs = _pddt_range_endpoints(start, end, policy, unit, target,
                    normalize, default, yearfirst, dayfirst, isoformat, strict, cfg)
                # The mature executor receives already-decoded local coordinates.
                # Regional candidate choice remains in the shared Rust finalizer.
                start_tick, end_tick = inputs.start, inputs.end
                carrier_unit = inputs.carrier_unit
                start_value = None if start_tick is None else pd.Timestamp(np.datetime64(start_tick, carrier_unit))
                end_value = None if end_tick is None else pd.Timestamp(np.datetime64(end_tick, carrier_unit))
                generation_unit,minimum_unit=_range_mature_units(metadata,inputs.unit)
                if generation_unit is not None:
                    generation_unit = _UNITS[max(_UNITS.index(generation_unit), _UNITS.index(carrier_unit))]
                try:
                    external = pd.date_range(start=start_value, end=end_value,
                        periods=periods, freq=metadata, unit=generation_unit, inclusive="both")
                except Exception as error:
                    raise _external_error(error)
                packed, selected, zone, left, right = _pddt_range_external(inputs,
                    external.asi8.tobytes(), external.unit, policy, inclusive,
                    unit or minimum_unit, unit is None and minimum_unit is not None)
            else:
                packed, selected, zone, left, right = _pddt_range(start, end, periods,
                    plan, policy, unit, target, inclusive, normalize, default,
                    yearfirst, dayfirst, isoformat, strict, cfg)
            values = np.frombuffer(packed, dtype=f"datetime64[{selected}]")
            if left or right:
                values = values[left:len(values)-right]
            array = _date_array(values, zone)
            validated_freq = _range_attach_frequency(array, metadata)
            return _finish(cls, array, name=name, freq=validated_freq)
        except Exception as error:
            _raise_argument_context(error, "Pddt.date_range", "arguments", None)


    @property
    def pddt(self):
        """Return the date-field namespace for this Pddt instance.

        Returns
        -------
        _PddtNamespace
            Its replace method changes date fields. A direct replace method,
            when provided by the installed pandas, retains pandas' complete
            whole-value replacement contract.
        """
        return _PddtNamespace(self)

    def to_datetime(self, year=None, month=None, day=None, hour=None, minute=None,
                    second=None, microsecond=None, nanosecond=None):
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
        try:
            return _fields(self, (year,month,day,hour,minute,second,microsecond,nanosecond), "Pddt.to_datetime")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_datetime", "arguments", None)

    def to_date(self, year=None, month=None, day=None):
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
        try:
            return _fields(self, (year,month,day,None,None,None,None,None), "Pddt.to_date")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_date", "arguments", None)

    def to_time(self, hour=None, minute=None, second=None, microsecond=None, nanosecond=None):
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
        try:
            return _fields(self, (None,None,None,hour,minute,second,microsecond,nanosecond), "Pddt.to_time")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_time", "arguments", None)

    def add(self, years=0, quarters=0, months=0, weeks=0, days=0, hours=0, minutes=0, seconds=0, milliseconds=0, microseconds=0, nanoseconds=0):
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
        try:
            return _incremented(self, (years,quarters,months,weeks,days,hours,minutes,seconds,milliseconds,microseconds,nanoseconds), "Pddt.add", False)
        except Exception as error:
            _raise_argument_context(error, "Pddt.add", "arguments", None)

    def sub(self, years=0, quarters=0, months=0, weeks=0, days=0, hours=0, minutes=0, seconds=0, milliseconds=0, microseconds=0, nanoseconds=0):
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
        try:
            return _incremented(self, (years,quarters,months,weeks,days,hours,minutes,seconds,milliseconds,microseconds,nanoseconds), "Pddt.sub", True)
        except Exception as error:
            _raise_argument_context(error, "Pddt.sub", "arguments", None)

    def to_year(self, offset, month=None, day=None):
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
        try:
            return _moved(self, "year", offset, month, day, "Pddt.to_year")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_year", "arguments", None)

    def to_quarter(self, offset, month=None, day=None):
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
        try:
            return _moved(self, "quarter", offset, month, day, "Pddt.to_quarter")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_quarter", "arguments", None)

    def to_month(self, offset, day=None):
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
        try:
            return _moved(self, "month", offset, None, day, "Pddt.to_month")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_month", "arguments", None)

    def to_weekday(self, offset, weekday=None):
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
        try:
            return _moved(self, "weekday", offset, weekday, None, "Pddt.to_weekday")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_weekday", "arguments", None)

    def to_day(self, offset):
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
        try:
            return _moved(self, "day", offset, None, None, "Pddt.to_day")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_day", "arguments", None)

    def to_curr_year(self, month=None, day=None):
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
        try:
            return _moved(self, "year", 0, month, day, "Pddt.to_curr_year")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_curr_year", "arguments", None)

    def to_prev_year(self, month=None, day=None):
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
        try:
            return _moved(self, "year", -1, month, day, "Pddt.to_prev_year")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_prev_year", "arguments", None)

    def to_next_year(self, month=None, day=None):
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
        try:
            return _moved(self, "year", 1, month, day, "Pddt.to_next_year")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_next_year", "arguments", None)

    def to_curr_quarter(self, month=None, day=None):
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
        try:
            return _moved(self, "quarter", 0, month, day, "Pddt.to_curr_quarter")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_curr_quarter", "arguments", None)

    def to_prev_quarter(self, month=None, day=None):
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
        try:
            return _moved(self, "quarter", -1, month, day, "Pddt.to_prev_quarter")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_prev_quarter", "arguments", None)

    def to_next_quarter(self, month=None, day=None):
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
        try:
            return _moved(self, "quarter", 1, month, day, "Pddt.to_next_quarter")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_next_quarter", "arguments", None)

    def to_curr_month(self, day=None):
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
        try:
            return _moved(self, "month", 0, None, day, "Pddt.to_curr_month")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_curr_month", "arguments", None)

    def to_prev_month(self, day=None):
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
        try:
            return _moved(self, "month", -1, None, day, "Pddt.to_prev_month")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_prev_month", "arguments", None)

    def to_next_month(self, day=None):
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
        try:
            return _moved(self, "month", 1, None, day, "Pddt.to_next_month")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_next_month", "arguments", None)

    def to_curr_weekday(self, weekday=None):
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
        try:
            return _moved(self, "weekday", 0, weekday, None, "Pddt.to_curr_weekday")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_curr_weekday", "arguments", None)

    def to_prev_weekday(self, weekday=None):
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
        try:
            return _moved(self, "weekday", -1, weekday, None, "Pddt.to_prev_weekday")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_prev_weekday", "arguments", None)

    def to_next_weekday(self, weekday=None):
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
        try:
            return _moved(self, "weekday", 1, weekday, None, "Pddt.to_next_weekday")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_next_weekday", "arguments", None)

    def to_monday(self):
        """Select this week's monday while keeping each clock.

        Returns
        -------
        Pddt
            Selected weekday dates with original resolution and missing values.
        """
        try:
            return _moved(self, "weekday", 0, 0, None, "Pddt.to_monday")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_monday", "arguments", None)

    def to_tuesday(self):
        """Select this week's tuesday while keeping each clock.

        Returns
        -------
        Pddt
            Selected weekday dates with original resolution and missing values.
        """
        try:
            return _moved(self, "weekday", 0, 1, None, "Pddt.to_tuesday")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_tuesday", "arguments", None)

    def to_wednesday(self):
        """Select this week's wednesday while keeping each clock.

        Returns
        -------
        Pddt
            Selected weekday dates with original resolution and missing values.
        """
        try:
            return _moved(self, "weekday", 0, 2, None, "Pddt.to_wednesday")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_wednesday", "arguments", None)

    def to_thursday(self):
        """Select this week's thursday while keeping each clock.

        Returns
        -------
        Pddt
            Selected weekday dates with original resolution and missing values.
        """
        try:
            return _moved(self, "weekday", 0, 3, None, "Pddt.to_thursday")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_thursday", "arguments", None)

    def to_friday(self):
        """Select this week's friday while keeping each clock.

        Returns
        -------
        Pddt
            Selected weekday dates with original resolution and missing values.
        """
        try:
            return _moved(self, "weekday", 0, 4, None, "Pddt.to_friday")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_friday", "arguments", None)

    def to_saturday(self):
        """Select this week's saturday while keeping each clock.

        Returns
        -------
        Pddt
            Selected weekday dates with original resolution and missing values.
        """
        try:
            return _moved(self, "weekday", 0, 5, None, "Pddt.to_saturday")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_saturday", "arguments", None)

    def to_sunday(self):
        """Select this week's sunday while keeping each clock.

        Returns
        -------
        Pddt
            Selected weekday dates with original resolution and missing values.
        """
        try:
            return _moved(self, "weekday", 0, 6, None, "Pddt.to_sunday")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_sunday", "arguments", None)

    def to_yesterday(self):
        """Move one calendar day backward, keeping the clock.

        Returns
        -------
        Pddt
            New dates with original resolution, name and missing positions.
        """
        try:
            return _moved(self, "day", -1, None, None, "Pddt.to_yesterday")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_yesterday", "arguments", None)

    def to_tomorrow(self):
        """Move one calendar day forward, keeping the clock.

        Returns
        -------
        Pddt
            New dates with original resolution, name and missing positions.
        """
        try:
            return _moved(self, "day", 1, None, None, "Pddt.to_tomorrow")
        except Exception as error:
            _raise_argument_context(error, "Pddt.to_tomorrow", "arguments", None)


    def __add__(self, other):
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
        try:
            return _binary(self, other)
        except Exception as error:
            _raise_argument_context(error, "Pddt.__add__", "other", other)

    def __radd__(self, other):
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
        try:
            return _binary(self, other, reflected=True)
        except Exception as error:
            _raise_argument_context(error, "Pddt.__radd__", "other", other)

    def __sub__(self, other):
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
        try:
            return _binary(self, other, subtract=True)
        except Exception as error:
            _raise_argument_context(error, "Pddt.__sub__", "other", other)

    def to_first_of(self, unit):
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
        try:
            return _period(self,unit,0,False,"Pddt.to_first_of")
        except Exception as error:
            _raise_argument_context(error,"Pddt.to_first_of","unit",unit)

    def is_first_of(self, unit):
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
        try:
            return _period(self,unit,0,True,"Pddt.is_first_of")
        except Exception as error:
            _raise_argument_context(error,"Pddt.is_first_of","unit",unit)

    def to_last_of(self, unit):
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
        try:
            return _period(self,unit,1,False,"Pddt.to_last_of")
        except Exception as error:
            _raise_argument_context(error,"Pddt.to_last_of","unit",unit)

    def is_last_of(self, unit):
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
        try:
            return _period(self,unit,1,True,"Pddt.is_last_of")
        except Exception as error:
            _raise_argument_context(error,"Pddt.is_last_of","unit",unit)

    def to_start_of(self, unit):
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
        try:
            return _period(self,unit,2,False,"Pddt.to_start_of")
        except Exception as error:
            _raise_argument_context(error,"Pddt.to_start_of","unit",unit)

    def is_start_of(self, unit):
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
        try:
            return _period(self,unit,2,True,"Pddt.is_start_of")
        except Exception as error:
            _raise_argument_context(error,"Pddt.is_start_of","unit",unit)

    def to_end_of(self, unit):
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
        try:
            return _period(self,unit,3,False,"Pddt.to_end_of")
        except Exception as error:
            _raise_argument_context(error,"Pddt.to_end_of","unit",unit)

    def is_end_of(self, unit):
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
        try:
            return _period(self,unit,3,True,"Pddt.is_end_of")
        except Exception as error:
            _raise_argument_context(error,"Pddt.is_end_of","unit",unit)


    def normalize(self):
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
        try:
            return _period(self,"D",2,False,"Pddt.normalize")
        except Exception as error:
            _raise_argument_context(error,"Pddt.normalize","arguments",None)

    def fsp(self, precision):
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
        try:
            precision=_integer_arg(precision,"Pddt.fsp","precision")
            if precision<0:
                raise _own_error(ValueError("must be nonnegative"),"precision",precision)
            if precision>=9:
                return self
            packed,changed=_pddt_fsp(self.asi8.tobytes(),self.unit,self.tz,precision,"Pddt.fsp")
            if not changed:
                return self
            array=_date_array(np.frombuffer(packed,dtype=f"datetime64[{self.unit}]"),self.tz)
            validated_freq=_range_attach_frequency(array,self.freq)
            return _finish(type(self),array,name=self.name,freq=validated_freq)
        except Exception as error:
            _raise_argument_context(error,"Pddt.fsp","precision",precision)

    def round(self, freq="s"):
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
        try:
            return _rounded(self,freq,0,"Pddt.round")
        except Exception as error:
            _raise_argument_context(error,"Pddt.round","freq",freq)

    def ceil(self, freq="s"):
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
        try:
            return _rounded(self,freq,1,"Pddt.ceil")
        except Exception as error:
            _raise_argument_context(error,"Pddt.ceil","freq",freq)

    def floor(self, freq="s"):
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
        try:
            return _rounded(self,freq,2,"Pddt.floor")
        except Exception as error:
            _raise_argument_context(error,"Pddt.floor","freq",freq)


    def snap(self, unit="s"):
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
        try:
            if not isinstance(unit,str):
                raise _own_error(TypeError("must be a unit or stored month/weekday name"),"unit",unit)
            packed,changed=_pddt_snap(self.asi8.tobytes(),self.unit,self.tz,unit,"Pddt.snap")
            if not changed:
                return self
            array=_date_array(np.frombuffer(packed,dtype=f"datetime64[{self.unit}]"),self.tz)
            validated_freq=_range_attach_frequency(array,self.freq)
            return _finish(type(self),array,name=self.name,freq=validated_freq)
        except Exception as error:
            _raise_argument_context(error,"Pddt.snap","unit",unit)

    def isoyear(self):
        """Return the signed ISO week year.

        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        try:
            return _calendar_query(self,0,"Pddt.isoyear")
        except Exception as error:
            _raise_argument_context(error,"Pddt.isoyear","arguments",None)

    def isoweek(self):
        """Return the ISO week number, starting at one.

        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        try:
            return _calendar_query(self,1,"Pddt.isoweek")
        except Exception as error:
            _raise_argument_context(error,"Pddt.isoweek","arguments",None)

    def isoweekday(self):
        """Return the ISO weekday, Monday one through Sunday seven.

        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        try:
            return _calendar_query(self,2,"Pddt.isoweekday")
        except Exception as error:
            _raise_argument_context(error,"Pddt.isoweekday","arguments",None)

    def days_in_year(self):
        """Return the number of days in the calendar year.

        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        try:
            return _calendar_query(self,3,"Pddt.days_in_year")
        except Exception as error:
            _raise_argument_context(error,"Pddt.days_in_year","arguments",None)

    def days_bf_year(self):
        """Count days before this year, relative to 0001-01-01.

        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        try:
            return _calendar_query(self,4,"Pddt.days_bf_year")
        except Exception as error:
            _raise_argument_context(error,"Pddt.days_bf_year","arguments",None)

    def days_in_quarter(self):
        """Return the number of days in the calendar quarter.

        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        try:
            return _calendar_query(self,5,"Pddt.days_in_quarter")
        except Exception as error:
            _raise_argument_context(error,"Pddt.days_in_quarter","arguments",None)

    def days_bf_quarter(self):
        """Count calendar-year days preceding this quarter.

        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        try:
            return _calendar_query(self,6,"Pddt.days_bf_quarter")
        except Exception as error:
            _raise_argument_context(error,"Pddt.days_bf_quarter","arguments",None)

    def day_of_quarter(self):
        """Return the one-based day position within the quarter.

        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        try:
            return _calendar_query(self,7,"Pddt.day_of_quarter")
        except Exception as error:
            _raise_argument_context(error,"Pddt.day_of_quarter","arguments",None)

    def days_bf_month(self):
        """Count calendar-year days preceding this month.

        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        try:
            return _calendar_query(self,8,"Pddt.days_bf_month")
        except Exception as error:
            _raise_argument_context(error,"Pddt.days_bf_month","arguments",None)

    def day_of_month(self):
        """Return the one-based day position within the month.

        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        try:
            return _calendar_query(self,9,"Pddt.day_of_month")
        except Exception as error:
            _raise_argument_context(error,"Pddt.day_of_month","arguments",None)

    @property
    def millisecond(self):
        """Return the 0–999 millisecond part within each second.

        Returns
        -------
        pandas.Index
            Nullable Int64 values, with pd.NA at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        try:
            return _calendar_query(self,10,"Pddt.millisecond")
        except Exception as error:
            _raise_argument_context(error,"Pddt.millisecond","arguments",None)

    def is_long_year(self):
        """Test whether the calendar year has 53 ISO weeks.

        Returns
        -------
        pandas.Index
            Boolean values, with False at original NaT positions.
            Uses actual local calendar fields; no Pydt objects are constructed.
        """
        try:
            return _calendar_query(self,105,"Pddt.is_long_year")
        except Exception as error:
            _raise_argument_context(error,"Pddt.is_long_year","arguments",None)

    def is_year(self, year):
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
        try:
            return _calendar_query(self,100,"Pddt.is_year",year,"year",0)
        except Exception as error:
            _raise_argument_context(error,"Pddt.is_year","year",year)

    def is_quarter(self, quarter):
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
        try:
            return _calendar_query(self,101,"Pddt.is_quarter",quarter,"quarter",0)
        except Exception as error:
            _raise_argument_context(error,"Pddt.is_quarter","quarter",quarter)

    def is_month(self, month):
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
        try:
            return _calendar_query(self,102,"Pddt.is_month",month,"month",1)
        except Exception as error:
            _raise_argument_context(error,"Pddt.is_month","month",month)

    def is_weekday(self, weekday):
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
        try:
            return _calendar_query(self,103,"Pddt.is_weekday",weekday,"weekday",2)
        except Exception as error:
            _raise_argument_context(error,"Pddt.is_weekday","weekday",weekday)

    def is_day(self, day):
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
        try:
            return _calendar_query(self,104,"Pddt.is_day",day,"day",0)
        except Exception as error:
            _raise_argument_context(error,"Pddt.is_day","day",day)

    def leap_bt_year(self, year):
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
        try:
            return _calendar_query(self,11,"Pddt.leap_bt_year",year,"year",0)
        except Exception as error:
            _raise_argument_context(error,"Pddt.leap_bt_year","year",year)


    @property
    def year(self):
        """Calendar years, preserving signed wide years and pandas missing values.

        Returns
        -------
        pandas.Index
            Standard int32 years when representable, int64 for wider years,
            or float64 with NaN at missing positions. The source name is retained.
        """
        try:
            return _calendar_query(self,200,"Pddt.year")
        except Exception as error:
            _raise_argument_context(error,"Pddt.year","arguments",None)

    def isocalendar(self):
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
        try:
            return _calendar_query(self,201,"Pddt.isocalendar")
        except Exception as error:
            _raise_argument_context(error,"Pddt.isocalendar","data",self)

    def is_dst(self):
        """Test whether each local date has a nonzero daylight-saving offset.

        Returns
        -------
        pandas.Index
            A bool index of the same length. Naive and missing dates return False; negative DST also counts as DST.
        """
        try:
            return _calendar_query(self,106,"Pddt.is_dst")
        except Exception as error:
            _raise_argument_context(error,"Pddt.is_dst","data",self)

    def utcoffset_seconds(self):
        """Return each actual UTC offset, rounded down to whole seconds.

        Returns
        -------
        pandas.Index
            A Int64 index of the same length. Naive and missing dates return pd.NA. Fractional negative offsets round toward the earlier second.
        """
        try:
            return _calendar_query(self,12,"Pddt.utcoffset_seconds")
        except Exception as error:
            _raise_argument_context(error,"Pddt.utcoffset_seconds","data",self)

    def is_past(self):
        """Test whether dates precede one current clock reading.

        Returns
        -------
        pandas.Index
            A bool index of the same length. Aware dates compare actual instants; naive dates compare local wall clocks. Equal and missing dates return False.
        """
        try:
            return _calendar_query(self,107,"Pddt.is_past")
        except Exception as error:
            _raise_argument_context(error,"Pddt.is_past","data",self)

    def is_future(self):
        """Test whether dates follow one current clock reading.

        Returns
        -------
        pandas.Index
            A bool index of the same length. Aware dates compare actual instants; naive dates compare local wall clocks. Equal and missing dates return False.
        """
        try:
            return _calendar_query(self,108,"Pddt.is_future")
        except Exception as error:
            _raise_argument_context(error,"Pddt.is_future","data",self)

    def diff(self,dtobj,unit,absolute=False,inclusive="one"):
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
        try:
            return _difference(self,dtobj,unit,absolute,inclusive)
        except Exception as error:
            _raise_argument_context(error,"Pddt.diff","arguments",None)

    @property
    def values_naive(self):
        """Return a datetime64 array containing local wall-clock values.

        Returns
        -------
        numpy.ndarray
            The current unit and missing positions are retained. Removing a
            timezone preserves the local clock, rather than exposing UTC ticks.
            An unrepresentable local clock requires an explicit as_unit().
        """
        try:
            return _wall_values(self.array,"Pddt.values_naive")
        except Exception as error:
            _raise_argument_context(error,"Pddt.values_naive","data",self)





    def toseconds(self,utc=False):
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
        try:
            return _numeric_export(self,0,"Pddt.toseconds",_boolean(utc,"Pddt.toseconds","utc"))
        except Exception as error:
            _raise_argument_context(error,"Pddt.toseconds","utc",utc)

    def tomicroseconds(self,utc=False):
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
        try:
            return _numeric_export(self,1,"Pddt.tomicroseconds",_boolean(utc,"Pddt.tomicroseconds","utc"))
        except Exception as error:
            _raise_argument_context(error,"Pddt.tomicroseconds","utc",utc)

    def toordinal(self):
        """Return local Gregorian day numbers, with 0001-01-01 as day one.

        Returns
        -------
        pandas.Index
            Nullable Int64 ordinals, retaining missing dates and wide years.
        """
        try:
            return _numeric_export(self,2,"Pddt.toordinal")
        except Exception as error:
            _raise_argument_context(error,"Pddt.toordinal","data",self)

    def timestamp(self):
        """Return actual UTC epoch seconds, interpreting naive dates locally.

        Returns
        -------
        pandas.Index
            Float64 seconds with NaN for missing dates. Naive repeated or
            nonexistent local times require tz_localize() with explicit policies
            before this conversion. Already-aware dates keep their instants.
        """
        try:
            return _numeric_export(self,3,"Pddt.timestamp")
        except Exception as error:
            _raise_argument_context(error,"Pddt.timestamp","data",self)

    def timedf(self):
        """Return nine local calendar/clock fields in struct_time order.

        Returns
        -------
        pandas.DataFrame
            A positional table with nullable Int64 year, Int16 day-of-year and
            seven Int8 columns. tm_isdst is -1 when DST is unspecified, otherwise
            zero or one. A missing date fills all nine cells with pd.NA.
        """
        try:
            return _numeric_export(self,4,"Pddt.timedf")
        except Exception as error:
            _raise_argument_context(error,"Pddt.timedf","data",self)

    def utctimedf(self):
        """Return nine UTC calendar/clock fields, with tm_isdst equal to zero.

        Returns
        -------
        pandas.DataFrame
            The same nullable columns and positional index as timedf(). Aware
            dates use UTC; naive dates retain their clock without guessing local
            timezone. Missing dates fill all nine cells with pd.NA.
        """
        try:
            return _numeric_export(self,5,"Pddt.utctimedf")
        except Exception as error:
            _raise_argument_context(error,"Pddt.utctimedf","data",self)

    def isoformat(self,sep="T",timespec="auto"):
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
        try:
            for name,value in (("sep",sep),("timespec",timespec)):
                if not isinstance(value,str):
                    raise _own_error(TypeError("must be a string"),name,value)
            return _object_export(self,5,"Pddt.isoformat",sep,timespec)
        except Exception as error:
            _raise_argument_context(error,"Pddt.isoformat","options",(sep,timespec))

    def strftime(self,format):
        """Format with complete system rules and exact fractional directives.

        Parameters
        ----------
        format : str
            An empty string is valid. ``%f`` uses nine digits for ns and six
            for s/ms/us. ``%.0f`` emits nothing; ``%.1f`` through ``%.9f``
            include a dot and truncate or right-pad without changing dates.
            Remaining directives retain pandas' system/platform behavior.

        Returns
        -------
        pandas.Index
            Strings with the source name and missing positions. System
            directives and their wide-year limits depend on the platform.

        Examples
        --------
        >>> Pddt(["2024-01-01T12:34:56.123456789"]).strftime("%f %.3f").tolist()
        ['123456789 .123']
        """
        try:
            if not isinstance(format,str):
                raise _own_error(TypeError("must be a string; an empty string is allowed"),"format",format)
            prepared = _strftime_prepare(format)
            if prepared.modified():
                values = _pddt_strftime(self.asi8.tobytes(), self.unit, self.tz, prepared)
                return pd.Index(values, dtype=object, name=self.name)
            try:
                return pd.DatetimeIndex.strftime(self,format)
            except Exception as error:
                raise _external_error(error)
        except Exception as error:
            _raise_argument_context(error,"Pddt.strftime","format",format)

    def datetime(self):
        """Return an object array of Pydt dates.

        Returns
        -------
        numpy.ndarray
            Each valid date becomes a Pydt with actual timezone and fold; missing dates are pd.NaT. Nanoseconds are floored to microseconds only at this output. Dates outside years 1 through 9999 raise the target error.
        """
        try:
            return _object_export(self,0,"Pddt.datetime")
        except Exception as error:
            _raise_argument_context(error,"Pddt.datetime","data",self)

    @property

    def date(self):
        """Return an object array of Python dates.

        Returns
        -------
        numpy.ndarray
            Local calendar dates are exported; missing dates are pd.NaT. Python date capacity is checked at this output.
        """
        try:
            return _object_export(self,1,"Pddt.date")
        except Exception as error:
            _raise_argument_context(error,"Pddt.date","data",self)

    @property

    def time(self):
        """Return local Python times without attached timezone.

        Returns
        -------
        numpy.ndarray
            Clock fields and fold are retained, with microsecond precision. Missing dates are pd.NaT.
        """
        try:
            return _object_export(self,2,"Pddt.time")
        except Exception as error:
            _raise_argument_context(error,"Pddt.time","data",self)

    @property

    def timetz(self):
        """Return local Python times retaining timezone and fold.

        Returns
        -------
        numpy.ndarray
            The actual clock, timezone and fold are retained at microsecond precision. Missing dates are pd.NaT.
        """
        try:
            return _object_export(self,3,"Pddt.timetz")
        except Exception as error:
            _raise_argument_context(error,"Pddt.timetz","data",self)

    def tzname(self):
        """Return actual timezone names for each represented date.

        Returns
        -------
        pandas.Index
            Winter and summer names may differ. Naive or missing dates return None.
        """
        try:
            return _object_export(self,4,"Pddt.tzname")
        except Exception as error:
            _raise_argument_context(error,"Pddt.tzname","data",self)

    def ctime(self):
        """Return standard English ctime strings.

        Returns
        -------
        pandas.Index
            Day numbers are space-padded, for example Tue Oct  1 08:19:05 2024. Fractions and timezone text are omitted; dates are unchanged.
        """
        try:
            return _object_export(self,6,"Pddt.ctime")
        except Exception as error:
            _raise_argument_context(error,"Pddt.ctime","data",self)

    def month_name(self,locale=None):
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
        try:
            return _object_export(self,7,"Pddt.month_name",locale)
        except Exception as error:
            _raise_argument_context(error,"Pddt.month_name","locale",locale)

    def weekday_name(self,locale=None):
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
        try:
            return _object_export(self,8,"Pddt.weekday_name",locale)
        except Exception as error:
            _raise_argument_context(error,"Pddt.weekday_name","locale",locale)

    def copy(self,name=None,deep=False):
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
        try:
            deep=_boolean(deep,"Pddt.copy","deep")
            return _copy_value(self,Pddt,_restore_pddt_copy,deep,{} if deep else None,name,True)
        except Exception as error:
            _raise_argument_context(error,"Pddt.copy","deep",deep)

    def __copy__(self):
        """Make a shallow copy using the actual Python state/reduction hooks.

        Returns
        -------
        Pddt
            A fresh shell with shared business references under the default
            protocol; business constructors are not rerun.
        """
        return _copy_value(self,Pddt,_restore_pddt_copy,False)

    def __deepcopy__(self,memo):
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
        return _copy_value(self,Pddt,_restore_pddt_copy,True,memo)

    def __getstate__(self):
        """Return an independent snapshot of business dictionary and slots.

        Returns
        -------
        object
            Ordinary business state only; the date core is saved separately.
            User-defined state hooks retain their normal Python meaning.
        """
        return _capture_state(self)

    def __setstate__(self,state):
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
        _apply_state(self,state)

    def __reduce__(self):
        """Return the new versioned Pddt pickle recipe and business state.

        Returns
        -------
        tuple
            A trusted-data reconstruction recipe. Legacy Pddt pickle formats
            are not imported or automatically migrated.
        """
        return _pickle_recipe(self,_restore_pddt)

    def __reduce_ex__(self,protocol):
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
        if _state_definition(type(self),"__reduce__") is not Pddt.__reduce__:
            try:
                return self.__reduce__()
            except Exception as error:
                raise _external_error(error)
        return Pddt.__reduce__(self)


class _PddtNamespace:
    """Pddt-only date-field operations, separate from pandas value replacement.

    Parameters
    ----------
    index : Pddt
        The owning immutable date index. Only Pddt.pddt creates this namespace;
        no accessor is registered on ordinary pandas DatetimeIndex objects.
    """
    __slots__ = ("_index",)

    def __init__(self, index):
        self._index = index

    def replace(self, year=None, month=None, day=None, hour=None, minute=None,
                second=None, microsecond=None, nanosecond=None, tzinfo=_UNSET, *,
                ambiguous="raise", nonexistent="raise"):
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
        try:
            return _fields(self._index, (year,month,day,hour,minute,second,microsecond,nanosecond),
                "Pddt.pddt.replace", True, tzinfo, ambiguous, nonexistent)
        except Exception as error:
            _raise_argument_context(error, "Pddt.pddt.replace", "arguments", None)

