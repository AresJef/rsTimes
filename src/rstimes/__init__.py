"""Exact conversions between aware datetimes and Unix milliseconds."""

from datetime import datetime, timedelta, timezone

__all__ = ["to_unix_ms", "from_unix_ms"]

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def to_unix_ms(value: datetime) -> int:
    """Return Unix milliseconds, flooring any sub-millisecond remainder.

    ``value`` must be timezone-aware and representable in UTC. For example,
    one microsecond before the epoch returns -1, not 0. All arithmetic is
    integer-based; the host's local timezone is never used.

    Raises:
        TypeError: If value is not a datetime.
        ValueError: If value is naive or outside the supported UTC range.
    """
    if not isinstance(value, datetime):
        raise TypeError("value must be a datetime")
    if value.utcoffset() is None:
        raise ValueError("value must be timezone-aware")
    try:
        delta = value.astimezone(timezone.utc) - _EPOCH
    except OverflowError as exc:
        raise ValueError("value is outside the supported UTC datetime range") from exc
    return (delta.days * 86_400 + delta.seconds) * 1_000 + delta.microseconds // 1_000


def from_unix_ms(value: int) -> datetime:
    """Return a UTC-aware datetime for integer Unix milliseconds.

    Negative values represent instants before 1970-01-01T00:00:00Z.
    The accepted range is -62135596800000 through 253402300799999, inclusive.

    Raises:
        TypeError: If value is not an int, or is a bool.
        ValueError: If value is outside Python's datetime range (years 1–9999).
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("value must be an int, not bool or another type")
    try:
        return _EPOCH + timedelta(microseconds=value * 1_000)
    except OverflowError as exc:
        raise ValueError("value is outside the supported UTC datetime range") from exc
