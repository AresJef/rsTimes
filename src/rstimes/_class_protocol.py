"""Small static class-definition lookup for real reconstruction protocols."""
from types import BuiltinMethodType, MethodDescriptorType, MethodType
import copy as _copy
from copy import Error
from copyreg import dispatch_table

_TYPE_MRO = type.__dict__["__mro__"]
_TYPE_DICT = type.__dict__["__dict__"]
NATIVE_COPY = object()
_reconstruct = getattr(_copy, "_reconstruct")


def definition(cls, name):
    """Read an actual MRO definition without invoking a descriptor twice."""
    # Calling type.__getattribute__ can still invoke a metaclass descriptor.
    # These canonical descriptors expose the live class storage directly.
    for base in _TYPE_MRO.__get__(cls):
        values = _TYPE_DICT.__get__(base)
        if name in values:
            return values[name]
    return None


def copy_reduction(value, defaults, deep):
    """Select actual reducers once; only known library methods use native copy.

    The enclosing standard copy machinery handles copy hooks. Its inherited
    library hook enters here to choose between native date copying and a real
    reducer, including descriptors, dynamic lookup and copyreg registrations.
    """
    cls = type(value)
    registered = dispatch_table.get(cls)
    if registered is not None and (not deep or registered):
        return registered(value)
    return _method_reduction(value, defaults)


def _method_reduction(value, defaults):
    """Choose actual methods after the caller has checked the live registry."""
    extended = getattr(value, "__reduce_ex__", None)
    if extended is not None and not (type(extended) is MethodType
            and extended.__self__ is value and extended.__func__ is defaults[0]
            or _native_method(value, extended, defaults[0])):
        return extended(4)
    basic = getattr(value, "__reduce__", None)
    if (type(basic) is MethodType and basic.__self__ is value
            and basic.__func__ is defaults[1]
            or _native_method(value, basic, defaults[1])):
        return NATIVE_COPY
    if basic:
        return basic()
    raise Error("un(deep)copyable object of type %s" % type(value))


def _native_method(value, method, original):
    """Compare a real PyO3 bound builtin with the retained native descriptor."""
    return (type(method) is BuiltinMethodType
            and type(original) is MethodDescriptorType
            and method == original.__get__(value, type(value)))


def reconstruct_copy(value, reduction, memo):
    """Use the same complete recipe unpacking and memo as standard copy."""
    return value if isinstance(reduction, str) else _reconstruct(value, memo, *reduction)
