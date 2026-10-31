"""Clear failures for date parsing and configuration.

Import these classes from ``rstimes.errors``. Other failures use standard
Python exceptions. A user callback keeps its original exception object; an
entry note may explain which public call was being performed.
"""
from concurrent.futures import CancelledError as _CancelledError


class RstimesError(Exception):
    """Base class for rsTimes-specific parsing and configuration failures.

    Parameters
    ----------
    *args : object
        Details describing the failure, as for a standard exception.

    Notes
    -----
    This class does not catch every error raised during a library call.
    TypeError, ValueError, OverflowError and callback exceptions retain their
    usual meanings unless they are one of the domain errors below.
    """


class ParseError(RstimesError, ValueError):
    """The parser could not interpret text under the requested rules.

    Parameters
    ----------
    *args : object
        Details naming the failed call and the known field or input.

    Notes
    -----
    Invalid strict fields, conflicting fields and missing required date
    information use this class. A failure inside the chosen result constructor
    retains that constructor's exception instead.
    """


class ConfigError(RstimesError, ValueError):
    """A configuration token, rule or value cannot be used.

    Parameters
    ----------
    *args : object
        Details describing the invalid rule and, when known, how to fix it.

    Notes
    -----
    An unsupported object type raises TypeError. Errors inside user callbacks
    keep their original exception; they are not automatically ConfigError.
    """


__all__ = ["RstimesError", "ParseError", "ConfigError"]

# Error-only ownership, recorded at a library failure's creation site. Never
# infer ownership from the exception type: callbacks may raise these classes.
# This metadata is private implementation state, not a user-facing error code.
_OWN_TOKEN = object()
_ORIGIN_KEY = "_rstimes_failure_origin"
_EXCEPTION_DICT = BaseException.__dict__["__dict__"]
_EXCEPTION_ARGS = BaseException.__dict__["args"]


def _critical(error):
    """Avoid all explanatory work for memory, cancellation and exit signals."""
    return not issubclass(type(error), Exception) or issubclass(
        type(error), (MemoryError, _CancelledError)
    )


def _preview(value, original_length=None):
    """Display a bounded builtin value without invoking user display hooks."""
    kind = type(value)
    name = type.__getattribute__(kind, "__name__")
    if kind is str:
        size = len(value) if original_length is None else original_length
        shown = repr(value[:96])
        suffix = f"... (length {size})" if size > 96 or len(shown) > 120 else ""
        return shown[:120 - len(suffix)] + suffix
    if kind is int:
        bits = int.bit_length(value)
        return repr(value) if bits <= 256 else f"<int, {bits} bits>"
    if kind is float or kind is bool or kind is type(None):
        return repr(value)
    if any(kind is builtin for builtin in (list, tuple, dict, set, frozenset, bytes, bytearray)):
        return f"<{name}, length {len(value)}>"
    # Type names themselves may be long; no object str/repr/len is needed.
    return ("<" + name[:116] + ("..." if len(name) > 116 else "") + ">")[:120]


def _own_error(error, parameter=None, value=None):
    """Mark a library-created failure, while its origin is still certain."""
    if _critical(error):
        return error
    args = _EXCEPTION_ARGS.__get__(error)
    detail = args[0] if len(args) == 1 and type(args[0]) is str else "operation failed"
    preview = None if parameter is None else _preview(value)
    dict.__setitem__(_EXCEPTION_DICT.__get__(error), _ORIGIN_KEY, (_OWN_TOKEN, detail, parameter, preview))
    return error


def _external_error(error):
    """Record a callback boundary without changing the callback exception."""
    # A callback can raise a previously caught library error. Its private origin
    # must not make the outer operation reclassify or rewrite that exception.
    if _critical(error):
        return error
    data = _EXCEPTION_DICT.__get__(error)
    origin = dict.get(data, _ORIGIN_KEY)
    if type(origin) is tuple and len(origin) == 4 and origin[0] is _OWN_TOKEN:
        dict.pop(data, _ORIGIN_KEY, None)
    notes = dict.get(data, "__notes__")
    if issubclass(type(notes), list) and list.__len__(notes):
        note = list.__getitem__(notes, -1)
        if type(note) is _EntryNote:
            # A previous library note is part of this callback's original error.
            # Retain its text and identity; the new public call gets its own note.
            note.active = False
    return error


class _EntryNote(str):
    """Metadata belongs to our own note, never to an external exception's attrs."""


def _external_note(error, entry, parameter, preview, has_value):
    """Keep one library note while an exception unwinds to its public caller."""
    data = _EXCEPTION_DICT.__get__(error)
    notes = dict.get(data, "__notes__")
    previous = (list.__getitem__(notes, -1)
                if issubclass(type(notes), list) and list.__len__(notes) else None)
    reusable = type(previous) is _EntryNote and previous.active
    if reusable and parameter in ("arguments", "operands"):
        parameter, preview, has_value = previous.field, previous.preview, previous.has_value
    prefix = f"{entry}(): " if entry else ""
    text = _EntryNote(f"{prefix}{parameter}={preview} failed" if has_value
                      else f"{prefix}processing {parameter} failed")
    text.field, text.preview, text.has_value, text.active = parameter, preview, has_value, True
    if reusable:
        list.__setitem__(notes, -1, text)
    else:
        # Use the standard descriptor, bypassing an exception's add_note override.
        # A genuine failure here propagates, including malformed __notes__.
        BaseException.add_note(error, text)
    return error


def _argument_error(error, entry, parameter, value, has_value=True, prepared_preview=None):
    """Finish a known library failure, or note an untouched external failure."""
    if _critical(error):
        return error
    origin = dict.get(_EXCEPTION_DICT.__get__(error), _ORIGIN_KEY)
    prefix = f"{entry}(): " if entry else ""
    if type(origin) is tuple and len(origin) == 4 and origin[0] is _OWN_TOKEN:
        _, detail, field, preview = origin
        indexed = parameter.startswith(("values[", "data[")) and parameter.endswith("]")
        if (field is None or indexed) and parameter not in ("arguments", "operands"):
            field, preview = parameter, (prepared_preview if prepared_preview is not None
                                          else _preview(value)) if has_value else None
            dict.__setitem__(_EXCEPTION_DICT.__get__(error), _ORIGIN_KEY,
                             (_OWN_TOKEN, detail, field, preview))
        if field is not None:
            detail = ((f"{field}={preview}: " if preview is not None else f"{field}: ")
                      + detail)
        if parameter == "operands" and field is None:
            detail = "operands: " + detail
        _EXCEPTION_ARGS.__set__(error, (prefix + detail,))
        return error
    # Calling the standard descriptor bypasses a user override of add_note.
    # A genuine failure here propagates; do not hide it behind the old error.
    has_value = has_value and parameter != "arguments"
    return _external_note(error, entry, parameter,
                          (prepared_preview if prepared_preview is not None
                           else _preview(value)) if has_value else None, has_value)


def _raise_argument_context(error, entry, parameter, value):
    """Raise one completed error without reconstructing the exception object."""
    raise _argument_error(error, entry, parameter, value)


def _location_error(error, entry, parameter):
    """Report a known index without re-reading a callback-invalidated slot."""
    return _argument_error(error, entry, parameter, None, False)


def _binary_error(error, entry, left, right):
    """Describe both live operands only after an arithmetic operation fails."""
    if _critical(error):
        return error
    origin = dict.get(_EXCEPTION_DICT.__get__(error), _ORIGIN_KEY)
    if type(origin) is tuple and len(origin) == 4 and origin[0] is _OWN_TOKEN:
        return _argument_error(error, entry, "operands", None)
    return _external_note(error, entry, "operands",
                          f"left={_preview(left)}, right={_preview(right)}", True)
