"""Small static class-definition lookup for real reconstruction protocols."""
from types import MethodType

_TYPE_MRO = type.__dict__["__mro__"]
_TYPE_DICT = type.__dict__["__dict__"]


def definition(cls, name):
    """Read an actual MRO definition without invoking a descriptor twice."""
    # Calling type.__getattribute__ can still invoke a metaclass descriptor.
    # These canonical descriptors expose the live class storage directly.
    for base in _TYPE_MRO.__get__(cls):
        values = _TYPE_DICT.__get__(base)
        if name in values:
            return values[name]
    return None


def copy_hook(value, base, deep):
    """Bind the standard copy hook once, excluding this library's own wrapper."""
    hook = "__deepcopy__" if deep else "__copy__"
    copier = getattr(value if deep else type(value), hook, None)
    if deep:
        if (type(copier) is MethodType and copier.__self__ is value
                and copier.__func__ is getattr(base, hook)):
            return None
    elif copier is getattr(base, hook):
        return None
    return copier
