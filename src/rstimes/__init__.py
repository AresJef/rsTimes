"""Calendar datetimes, deltas, configurable date parsing and Unix milliseconds.

``Pydt`` extends datetime with calendar and timezone conveniences.
``Delta`` is implemented by the Rust extension and exported here and from
``rstimes.delta`` as the same class. The two timestamp helpers use integer
arithmetic, require explicit UTC offsets, and never consult local timezone
settings. See each object's docstring for accepted inputs and errors.
"""

from datetime import datetime, timedelta, timezone
from .pydt import Pydt
from .delta import Delta
from .parser import Configs, parse_str, parse, parse_to_epoch
from .errors import _own_error, _external_error, _raise_argument_context

__all__ = ["Pddt", "Pldt", "Pydt", "Delta", "Configs", "parse_str", "parse", "parse_to_epoch", "to_unix_ms", "from_unix_ms"]

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def to_unix_ms(value: datetime) -> int:
    """Return Unix milliseconds, flooring any sub-millisecond remainder.

    ``value`` must be timezone-aware and representable in UTC. For example,
    one microsecond before the epoch returns -1, not 0. All arithmetic is
    integer-based; the host's local timezone is never used.

    Args:
        value (datetime): A timezone-aware datetime, including datetime subclasses.

    Returns:
        int: Milliseconds since 1970-01-01T00:00:00Z, rounded toward negative
        infinity when the input has a fractional millisecond.

    Raises:
        TypeError: If value is not a datetime.
        ValueError: If value is timezone-naive.
        OverflowError: If conversion exceeds the supported UTC datetime range.

    Examples:
        >>> to_unix_ms(datetime(1970, 1, 1, tzinfo=timezone.utc))
        0
        >>> to_unix_ms(datetime(1969, 12, 31, 23, 59, 59, 999999,
        ...                     tzinfo=timezone.utc))
        -1
    """
    try:
        if not issubclass(type(value), datetime):
            raise _own_error(TypeError("value must be a datetime"))
        try:
            offset = value.utcoffset()
        except Exception as error:
            raise _external_error(error)
        if offset is None:
            raise _own_error(ValueError("value must be timezone-aware"))
        try:
            delta = value.astimezone(timezone.utc) - _EPOCH
            return (delta.days * 86_400 + delta.seconds) * 1_000 + delta.microseconds // 1_000
        except Exception as error:
            raise _external_error(error)
    except Exception as error:
        _raise_argument_context(error, "to_unix_ms", "value", value)


def from_unix_ms(value: int) -> datetime:
    """Return a UTC-aware datetime for integer Unix milliseconds.

    Negative values represent instants before 1970-01-01T00:00:00Z.
    The accepted range is -62135596800000 through 253402300799999, inclusive.

    Args:
        value (int): Unix milliseconds; bool is explicitly rejected.

    Returns:
        datetime: An aware builtin datetime whose timezone is UTC.

    Raises:
        TypeError: If value is not an int, or is a bool.
        OverflowError: If value is outside Python's datetime range (years 1–9999).

    Examples:
        >>> from_unix_ms(0).isoformat()
        '1970-01-01T00:00:00+00:00'
        >>> to_unix_ms(from_unix_ms(-1))
        -1
    """
    try:
        if issubclass(type(value), bool) or not issubclass(type(value), int):
            raise _own_error(TypeError("value must be an int; bool is not accepted"))
        try:
            return _EPOCH + timedelta(microseconds=value * 1_000)
        except Exception as error:
            raise _external_error(error)
    except Exception as error:
        _raise_argument_context(error, "from_unix_ms", "value", value)


def __getattr__(name):
    if name == "Pldt":
        from .pldt import Pldt
        globals()[name] = Pldt
        return Pldt
    if name == "Pddt":
        from .pddt import Pddt
        globals()[name] = Pddt
        return Pddt
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
