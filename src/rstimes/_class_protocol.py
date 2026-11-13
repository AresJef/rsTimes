"""Small static class-definition lookup for real reconstruction protocols."""
from types import MethodType
from copy import Error
from copyreg import dispatch_table

_TYPE_MRO = type.__dict__["__mro__"]
_TYPE_DICT = type.__dict__["__dict__"]
NATIVE_COPY = object()


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
    extended = getattr(value, "__reduce_ex__", None)
    if extended is not None and not (type(extended) is MethodType
            and extended.__self__ is value and extended.__func__ is defaults[0]):
        return extended(4)
    basic = getattr(value, "__reduce__", None)
    if (type(basic) is MethodType and basic.__self__ is value
            and basic.__func__ is defaults[1]):
        return NATIVE_COPY
    if basic:
        return basic()
    raise Error("un(deep)copyable object of type %s" % cls)
