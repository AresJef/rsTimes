"""Stable builtin storage for default copy/restore state, separate from hooks."""


def snapshot(part: dict[object, object] | None) -> dict[object, object] | None:
    """Shallow-copy a validated dict/None without virtual mapping export.

    Arguments:
        part: A dict or real dict subclass already checked by the caller, or None.
    Returns:
        A plain dictionary containing the stored entries, or None.
    """
    if part is None:
        return None
    if type(part) is dict:
        return part.copy()
    # dict.copy/update can dispatch overridden keys/getitem for a subclass.
    # Materialize the builtin item view first; keys/values remain shallow refs.
    return dict(tuple(dict.items(part)))
