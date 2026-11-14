"""Stable builtin storage for default copy/restore state, separate from hooks."""
from typing import TypeVar

_Key = TypeVar("_Key")
_Value = TypeVar("_Value")

# Strict codecs may bind this immutable builtin after admitting an exact dict.
# The general reader below additionally handles None and real dict subclasses.
_snapshot_exact = dict.copy


def snapshot(part: dict[_Key, _Value] | None) -> dict[_Key, _Value] | None:
    """Shallow-copy a validated dict/None without virtual mapping export.

    Arguments:
        part: A dict or real dict subclass already checked by the caller, or None.
    Returns:
        A plain dictionary containing the stored entries, or None.
    """
    if part is None:
        return None
    if type(part) is dict:
        return _snapshot_exact(part)
    # dict.copy/update can dispatch overridden keys/getitem for a subclass.
    # Materialize the builtin item view first; keys/values remain shallow refs.
    return dict(tuple(dict.items(part)))
