"""Versioned Pldt date cores and Python's actual business-state protocols.

Only explicit copy/save operations enter here. Ordinary date kernels do not
inspect business dictionaries, slots, reduction hooks or namespace caches.
"""
from copy import _reconstruct

from ._optional import POLARS as pl
from ._native import _pldt_core, _pldt_restore_core, _pldt_copy_core
from ._class_protocol import definition
from ._polars import plain_series
from .errors import _own_error, _external_error

_BASE = None
_NAMESPACE_DESCRIPTOR = pl.api.NameSpace


def register(base):
    global _BASE
    _BASE = base


def _is_namespace_cache(cls, key, value):
    descriptor = definition(cls, key)
    return isinstance(descriptor, _NAMESPACE_DESCRIPTOR) and isinstance(value, descriptor._ns)


def capture(value):
    """Capture dictionary/initialized slots, excluding actual native caches."""
    state = object.__getstate__(value)
    if state is None:
        return None
    dictionary, slots = state if isinstance(state, tuple) else (state, None)
    cls = type(value)
    def saved(part):
        if part is None:
            return None
        return {key: item for key, item in dict.items(part)
                if key != '_s' and not _is_namespace_cache(cls, key, item)}
    dictionary, slots = saved(dictionary), saved(slots)
    return (dictionary or None, slots) if slots else dictionary or None


def apply(value, state):
    """Apply ordinary state after core restoration, leaving its buffer intact."""
    if state is None:
        return
    if isinstance(state, tuple):
        if len(state) != 2:
            raise _own_error(ValueError('business state must be a dictionary or dictionary/slots pair'), 'state', state)
        dictionary, slots = state
    else:
        dictionary, slots = state, None
    for label, part in (('dictionary', dictionary), ('slots', slots)):
        if part is not None and not isinstance(part, dict):
            raise _own_error(TypeError('must be a dictionary or None'), 'state.' + label, part)
        if part is not None and '_s' in part:
            raise _own_error(ValueError('business state cannot replace the validated native date core'), 'state.' + label, part)
    if slots is not None and any(not isinstance(key, str) for key in dict.keys(slots)):
        raise _own_error(TypeError('slot names must be strings'), 'state.slots', slots)
    try:
        if dictionary is not None:
            object.__getattribute__(value, '__dict__').update(dictionary)
        if slots is not None:
            for key, item in dict.items(slots):
                setattr(value, key, item)
    except Exception as error:
        raise _external_error(error)


def _class(cls):
    if not isinstance(cls, type) or _BASE is None or not issubclass(cls, _BASE):
        raise _own_error(TypeError('must be Pldt or its real subclass'), 'state.class', cls)


def _sorted(value):
    flags = pl.Series.flags.fget(value)
    return 1 if flags['SORTED_ASC'] else 2 if flags['SORTED_DESC'] else 0


def _mark_sorted(carrier, flag):
    return carrier.set_sorted(descending=flag == 2) if flag else carrier


def _shell(cls, carrier):
    value = object.__new__(cls)
    object.__setattr__(value, '_s', carrier._s)
    return value


def restore(cls, marker, version, data, validity, unit, zone, name, sorted):
    """Validate the explicit core, without running business new/init."""
    _class(cls)
    if type(marker) is not str or marker != 'rstimes.pldt':
        raise _own_error(ValueError('unsupported state marker; only the current Pldt core is accepted'), 'state.marker', marker)
    if type(version) is not int:
        raise _own_error(TypeError('must be an exact integer'), 'state.version', version)
    if version != 1:
        raise _own_error(ValueError('unsupported core version; only version 1 is supported'), 'state.version', version)
    for key, value in (('values', data), ('validity', validity)):
        if type(value) is not bytes:
            raise _own_error(TypeError('must be immutable bytes'), 'state.' + key, value)
    if type(sorted) is not int:
        raise _own_error(TypeError('must be an exact integer'), 'state.sorted', sorted)
    if sorted not in (0, 1, 2):
        raise _own_error(ValueError('must be zero, one or two'), 'state.sorted', sorted)
    if not isinstance(unit, str) or not isinstance(name, str) or zone is not None and not isinstance(zone, str):
        raise _own_error(TypeError('unit/name must be strings and timezone a string or None'), 'state.metadata', None)
    carrier, flag = _pldt_restore_core(data, validity, unit, zone, name, sorted, pl.Series)
    return _shell(cls, _mark_sorted(carrier, flag))


def _restore_copy(cls, source, deep, sorted):
    _class(cls)
    carrier, flag = _pldt_copy_core(source, deep, sorted, pl.Series)
    return _shell(cls, _mark_sorted(carrier, flag))


def recipe(value):
    """Keep the independent-validity core separate from real user state."""
    core = _pldt_core(plain_series(value), _sorted(value))
    try:
        state = value.__getstate__()
    except Exception as error:
        raise _external_error(error)
    return restore, (type(value), 'rstimes.pldt', 1, *core), state


def copy_value(value, deep, memo=None, *, name=None, honor_copy=False):
    """Reuse standard reconstruction/memo and the actual reduction hooks."""
    cls = type(value)
    if deep and memo is None:
        memo = {}
    hook = '__deepcopy__' if deep else '__copy__'
    if honor_copy and definition(cls, hook) is not definition(_BASE, hook):
        try:
            result = getattr(value, hook)(memo) if deep else getattr(value, hook)()
        except Exception as error:
            raise _external_error(error)
        return _named_result(value, result, name)
    custom = (definition(cls, '__reduce_ex__') is not _BASE.__reduce_ex__
              or definition(cls, '__reduce__') is not _BASE.__reduce__)
    if custom:
        try:
            reduction = value.__reduce_ex__(4)
        except Exception as error:
            raise _external_error(error)
    else:
        sorted = _sorted(value)
        core = plain_series(value)
        try:
            state = value.__getstate__()
        except Exception as error:
            raise _external_error(error)
        reduction = _restore_copy, (cls, core, deep, sorted), state
    result = value if isinstance(reduction, str) else _reconstruct(value, memo if deep else None, *reduction)
    return _named_result(value, result, name)


def _named_result(source, result, name):
    if name is not None:
        if result is source and pl.Series.name.fget(source) != name:
            raise _own_error(ValueError('the copy hook returned the original object; it cannot be renamed without changing the source'), 'name', name)
        try:
            if isinstance(result, pl.Series):
                carrier = plain_series(result).rename(name)
                object.__setattr__(result, '_s', carrier._s)
            else:
                result.name = name
        except Exception as error:
            raise _external_error(error)
    return result
