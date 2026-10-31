"""Small static class-definition lookup for real reconstruction protocols."""


def definition(cls, name):
    """Read an actual MRO definition without invoking a descriptor twice."""
    for base in type.__getattribute__(cls, "__mro__"):
        values = type.__getattribute__(base, "__dict__")
        if name in values:
            return values[name]
    return None
